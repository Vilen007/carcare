from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import Coupon, SaleCampaign
from apps.cart.services import Cart
from apps.catalog.models import Bundle, BundleItem, Category, InventoryAdjustment, Product
from apps.orders.forms import CheckoutForm
from apps.orders.models import City, Order, OrderItem, Province, TrackingEvent
from apps.reviews.models import Review


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class StoreFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Exterior", slug="exterior")
        cls.product = Product.objects.create(
            category=cls.category,
            name="Ceramic Shampoo",
            slug="ceramic-shampoo",
            sku="SHAMPOO-1",
            short_description="Safe wash",
            description="A pH-neutral shampoo.",
            price=Decimal("100.00"),
            compare_at_price=Decimal("150.00"),
            stock=20,
            status=Product.Status.ACTIVE,
        )
        cls.second_product = Product.objects.create(
            category=cls.category,
            name="Detailing Brush",
            slug="detailing-brush",
            sku="BRUSH-1",
            short_description="Soft brush",
            description="For interior and exterior details.",
            price=Decimal("50.00"),
            stock=10,
            status=Product.Status.ACTIVE,
        )
        cls.bundle = Bundle.objects.create(
            name="Wash Kit",
            slug="wash-kit",
            description="Shampoo and two brushes.",
            discount_percent=10,
        )
        BundleItem.objects.create(bundle=cls.bundle, product=cls.product, quantity=2)
        BundleItem.objects.create(bundle=cls.bundle, product=cls.second_product, quantity=1)


class PricingTests(StoreFixtureMixin, TestCase):
    def test_product_discount_and_bundle_prices_are_decimal_and_quantity_aware(self):
        self.assertEqual(self.product.discount_percent, 33)
        self.assertEqual(self.bundle.original_price, Decimal("250.00"))
        self.assertEqual(self.bundle.price, Decimal("225.00"))

    def test_bundle_price_rounds_to_currency_precision(self):
        self.bundle.discount_percent = 7
        self.bundle.save(update_fields=["discount_percent"])
        self.assertEqual(self.bundle.price, Decimal("232.50"))

    def test_active_storewide_sale_automatically_changes_product_price(self):
        SaleCampaign.objects.create(
            name="Launch sale", discount_percent=20,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=1),
            applies_to_all=True,
        )

        self.assertEqual(self.product.current_price, Decimal("80.00"))
        self.assertEqual(self.product.display_compare_price, Decimal("150.00"))
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, "PKR 80")


class SessionCartTests(StoreFixtureMixin, TestCase):
    def test_session_cart_totals_products_and_bundles(self):
        self.client.post(reverse("cart:add_product", args=[self.product.pk]), {"quantity": 2})
        self.client.post(reverse("cart:add_bundle", args=[self.bundle.pk]))

        cart = Cart(SimpleNamespace(session=self.client.session))

        self.assertEqual(cart.count, 3)
        self.assertEqual(cart.subtotal, Decimal("425.00"))
        self.assertEqual(
            {line.key: line.total for line in cart.lines()},
            {
                f"product:{self.product.pk}": Decimal("200.00"),
                f"bundle:{self.bundle.pk}": Decimal("225.00"),
            },
        )

    def test_valid_coupon_is_applied_to_cart_total(self):
        coupon = Coupon.objects.create(
            code="SHINE10", discount_percent=10,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=1),
        )
        self.client.post(reverse("cart:add_product", args=[self.product.pk]), {"quantity": 2})
        response = self.client.post(reverse("cart:apply_coupon"), {"code": "shine10"})
        cart = Cart(SimpleNamespace(session=self.client.session))

        self.assertRedirects(response, reverse("cart:detail"), fetch_redirect_response=False)
        self.assertEqual(cart.coupon, coupon)
        self.assertEqual(cart.discount, Decimal("20.00"))
        self.assertEqual(cart.total, Decimal("180.00"))

    def test_cannot_add_more_than_stock_in_one_request(self):
        self.product.stock = 6
        self.product.save(update_fields=["stock"])
        response = self.client.post(
            reverse("cart:add_product", args=[self.product.pk]),
            {"quantity": 8},
            follow=True,
        )
        cart = Cart(SimpleNamespace(session=self.client.session))
        self.assertEqual(cart.product_quantity(self.product.pk), 0)
        self.assertContains(response, "Only 6 more")

    def test_cannot_stack_cart_past_stock(self):
        self.product.stock = 6
        self.product.save(update_fields=["stock"])
        self.client.post(reverse("cart:add_product", args=[self.product.pk]), {"quantity": 5})
        response = self.client.post(
            reverse("cart:add_product", args=[self.product.pk]),
            {"quantity": 3},
            follow=True,
        )
        cart = Cart(SimpleNamespace(session=self.client.session))
        self.assertEqual(cart.product_quantity(self.product.pk), 5)
        self.assertContains(response, "Only 1 more")

    def test_product_page_shows_stock_and_limits_quantity(self):
        self.product.stock = 6
        self.product.save(update_fields=["stock"])
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, "6 in stock")
        self.assertContains(response, 'max="6"')


class ShippingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.create(
            name="Punjab",
            shipping_fee=Decimal("250.00"),
            cod_fee=Decimal("50.00"),
            free_shipping_threshold=Decimal("2000.00"),
        )

    def test_shipping_is_charged_below_free_threshold(self):
        self.assertEqual(
            self.province.calculate(Decimal("1999.99")),
            (Decimal("250.00"), Decimal("50.00")),
        )

    def test_shipping_is_free_at_threshold_but_cod_fee_remains(self):
        self.assertEqual(
            self.province.calculate(Decimal("2000.00")),
            (Decimal("0"), Decimal("50.00")),
        )


class DeliveryLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.punjab = Province.objects.create(name="Punjab", shipping_fee=250)
        cls.sindh = Province.objects.create(name="Sindh", shipping_fee=280)
        cls.gujranwala = City.objects.create(province=cls.punjab, name="Gujranwala")
        cls.karachi = City.objects.create(province=cls.sindh, name="Karachi")

    def test_checkout_uses_only_managed_province_and_city_fields(self):
        form = CheckoutForm(initial={"delivery_province": self.punjab})

        self.assertNotIn("province", form.fields)
        self.assertNotIn("city", form.fields)
        self.assertIn("delivery_province", form.fields)
        self.assertQuerySetEqual(form.fields["delivery_city"].queryset, [self.gujranwala])

    def test_city_endpoint_returns_only_selected_province_cities(self):
        response = self.client.get(reverse("orders:cities"), {"province": self.punjab.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"cities": [{"id": self.gujranwala.pk, "name": "Gujranwala"}]})


class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="ExistingUser", email="existing@example.com", password="StrongPass123!"
        )

    def registration_data(self, **overrides):
        data = {
            "username": "newcustomer",
            "first_name": "New",
            "last_name": "Customer",
            "email": "new@example.com",
            "password1": "SecureCheckout789!",
            "password2": "SecureCheckout789!",
        }
        data.update(overrides)
        return data

    def test_duplicate_username_is_a_friendly_case_insensitive_form_error(self):
        response = self.client.post(
            reverse("customers:register"),
            self.registration_data(username="existinguser"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this username already exists.")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_duplicate_email_is_a_friendly_case_insensitive_form_error(self):
        response = self.client.post(
            reverse("customers:register"),
            self.registration_data(email="EXISTING@example.com"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_database_uniqueness_race_becomes_form_error_instead_of_500(self):
        with patch("apps.customers.views.RegistrationForm.save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("customers:register"), self.registration_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That account was just registered. Try signing in instead.")

    def test_ajax_validation_returns_structured_errors_without_page_reload(self):
        response = self.client.post(
            reverse("customers:register"),
            self.registration_data(password2="DifferentPassword789!"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password2", response.json()["errors"])

    def test_successful_ajax_registration_returns_redirect_and_welcome_alert(self):
        response = self.client.post(
            reverse("customers:register"),
            self.registration_data(),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        account = self.client.get(response.json()["redirect"])
        self.assertContains(account, "Your account is ready.")


class FormFeedbackTests(TestCase):
    def test_csrf_token_endpoint_sets_cookie_and_returns_fresh_token(self):
        response = self.client.get(reverse("core:csrf_token"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["token"])
        self.assertIn("csrftoken", response.cookies)

    def test_csrf_failure_redirects_back_with_friendly_alert(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("content:newsletter"),
            {"email": "person@example.com", "next": "/"},
            HTTP_REFERER="http://testserver/",
        )

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        follow = client.get("/")
        self.assertContains(follow, "Your secure session expired")

    def test_newsletter_distinguishes_success_and_existing_subscription(self):
        response = self.client.post(
            reverse("content:newsletter"), {"email": "Fan@Example.com", "next": "/"}
        )
        self.assertIn("Thanks for subscribing", " ".join(str(message) for message in get_messages(response.wsgi_request)))

        response = self.client.post(
            reverse("content:newsletter"), {"email": "fan@example.com", "next": "/"}
        )
        self.assertIn("already subscribed", " ".join(str(message) for message in get_messages(response.wsgi_request)))

    def test_successful_login_has_welcome_alert(self):
        get_user_model().objects.create_user(username="driver", password="SecureLogin789!")

        response = self.client.post(
            reverse("customers:login"),
            {"username": "driver", "password": "SecureLogin789!"},
        )

        self.assertIn("Welcome back", " ".join(str(message) for message in get_messages(response.wsgi_request)))


class GuestCheckoutTests(StoreFixtureMixin, TestCase):
    def setUp(self):
        self.province = Province.objects.create(
            name="Punjab",
            shipping_fee=Decimal("200.00"),
            cod_fee=Decimal("25.00"),
            free_shipping_threshold=Decimal("1000.00"),
        )
        self.city = City.objects.create(province=self.province, name="Gujranwala")

    def test_cod_guest_checkout_decrements_inventory_and_snapshots_order_line(self):
        self.client.post(reverse("cart:add_product", args=[self.product.pk]), {"quantity": 2})
        response = self.client.post(
            reverse("orders:checkout"),
            {
                "email": "guest@example.com",
                "phone": "03001234567",
                "full_name": "Guest Buyer",
                "address_line_1": "1 Test Street",
                "address_line_2": "",
                "delivery_province": self.province.pk,
                "delivery_city": self.city.pk,
                "postal_code": "74000",
                "customer_note": "Call before delivery",
            },
        )

        order = Order.objects.get()
        item = OrderItem.objects.get(order=order)
        self.product.refresh_from_db()

        self.assertRedirects(
            response,
            reverse("orders:confirmation", args=[order.number]),
            fetch_redirect_response=False,
        )
        self.assertIsNone(order.user)
        self.assertEqual(order.province, "Punjab")
        self.assertEqual(order.city, "Gujranwala")
        self.assertEqual(order.delivery_province, self.province)
        self.assertEqual(order.delivery_city, self.city)
        self.assertEqual(order.payment_method, "cod")
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.total, Decimal("425.00"))
        self.assertEqual(self.product.stock, 18)
        self.assertEqual(item.product_name, "Ceramic Shampoo")
        self.assertEqual(item.sku, "SHAMPOO-1")
        self.assertEqual(item.unit_price, Decimal("100.00"))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.line_total, Decimal("200.00"))
        self.assertTrue(
            InventoryAdjustment.objects.filter(
                product=self.product,
                quantity=-2,
                reason=InventoryAdjustment.Reason.ORDER,
                reference=order.number,
            ).exists()
        )
        self.assertTrue(
            TrackingEvent.objects.filter(order=order, status=Order.Status.PENDING).exists()
        )
        self.assertEqual(self.client.session.get(Cart.SESSION_KEY), {})
        self.assertIn(
            "placed successfully",
            " ".join(str(message) for message in get_messages(response.wsgi_request)),
        )

    def test_checkout_rejects_city_from_another_province(self):
        other = Province.objects.create(name="Sindh", shipping_fee=Decimal("220.00"))
        karachi = City.objects.create(province=other, name="Karachi")
        self.client.post(reverse("cart:add_product", args=[self.product.pk]), {"quantity": 1})

        response = self.client.post(reverse("orders:checkout"), {
            "email": "guest@example.com", "phone": "03001234567", "full_name": "Guest Buyer",
            "address_line_1": "1 Test Street", "delivery_province": self.province.pk,
            "delivery_city": karachi.pk, "postal_code": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a city within the chosen province.")
        self.assertFalse(Order.objects.exists())

    def test_checkout_applies_coupon_and_records_usage(self):
        coupon = Coupon.objects.create(
            code="DETAIL10", discount_percent=10,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=1),
        )
        self.client.post(reverse("cart:add_product", args=[self.product.pk]), {"quantity": 2})

        response = self.client.post(reverse("orders:checkout"), {
            "email": "guest@example.com", "phone": "03001234567", "full_name": "Guest Buyer",
            "address_line_1": "1 Test Street", "delivery_province": self.province.pk,
            "delivery_city": self.city.pk, "postal_code": "", "coupon_code": "detail10",
        })

        order = Order.objects.get()
        coupon.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.discount, Decimal("20.00"))
        self.assertEqual(order.coupon_code, "DETAIL10")
        self.assertEqual(order.total, Decimal("405.00"))
        self.assertEqual(coupon.times_used, 1)


@override_settings(STORAGES=TEST_STORAGES)
class TrackingPrivacyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order = Order.objects.create(
            email="private@example.com",
            phone="03009999999",
            full_name="Private Customer",
            address_line_1="Hidden address",
            city="Lahore",
            province="Punjab",
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
        )

    def test_invalid_contact_does_not_expose_order(self):
        response = self.client.post(
            reverse("orders:track"),
            {"order_number": self.order.number, "contact": "attacker@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["order"])
        self.assertContains(response, "We could not match that order and contact detail.")
        self.assertNotContains(response, self.order.full_name)
        self.assertNotContains(response, self.order.email)
        self.assertNotContains(response, self.order.address_line_1)


@override_settings(STORAGES=TEST_STORAGES)
class ReviewTests(StoreFixtureMixin, TestCase):
    def test_product_detail_only_shows_approved_reviews(self):
        approved = Review.objects.create(
            product=self.product,
            name="Approved",
            email="approved@example.com",
            rating=5,
            title="Visible review",
            body="This should be public.",
            is_approved=True,
        )
        Review.objects.create(
            product=self.product,
            name="Pending",
            email="pending@example.com",
            rating=1,
            title="Hidden review",
            body="This must stay private until approved.",
            is_approved=False,
        )

        response = self.client.get(self.product.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(response.context["reviews"], [approved])
        self.assertContains(response, "Visible review")
        self.assertNotContains(response, "Hidden review")
        self.assertEqual(response.context["product"].avg_rating, 5)
        self.assertEqual(response.context["product"].review_count, 1)
        self.assertContains(response, "(1 review)")

    def test_homepage_shows_approved_reviews_and_product_rating(self):
        self.product.is_featured = True
        self.product.save(update_fields=["is_featured"])
        approved = Review.objects.create(
            product=self.product, name="Driver", email="driver@example.com",
            rating=4, title="Excellent finish", body="The gloss lasted for weeks.",
            is_approved=True,
        )
        Review.objects.create(
            product=self.product, name="Pending", email="pending-home@example.com",
            rating=1, title="Not public", body="Awaiting moderation.",
            is_approved=False,
        )

        response = self.client.get(reverse("core:home"))

        featured = list(response.context["products"])[0]
        self.assertEqual(featured.avg_rating, 4)
        self.assertEqual(featured.review_count, 1)
        self.assertQuerySetEqual(response.context["reviews"], [approved])
        self.assertContains(response, "Excellent finish")
        self.assertNotContains(response, "Not public")

    def test_product_reviews_are_loaded_six_at_a_time(self):
        for index in range(8):
            Review.objects.create(
                product=self.product, name=f"Driver {index}", email=f"driver{index}@example.com",
                rating=5, title=f"Review {index}", body=f"Feedback number {index}.",
                is_approved=True,
            )

        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(len(response.context["reviews"]), 6)
        self.assertTrue(response.context["reviews_page"].has_next())
        self.assertNotContains(response, "Review 0")

        more = self.client.get(
            reverse("catalog:product_reviews", args=[self.product.slug]), {"page": 2}
        )
        self.assertEqual(more.status_code, 200)
        self.assertFalse(more.json()["has_more"])
        self.assertIn("Review 0", more.json()["html"])

    def test_homepage_limits_reviews_to_latest_ten(self):
        for index in range(12):
            Review.objects.create(
                product=self.product, name=f"Owner {index}", email=f"owner{index}@example.com",
                rating=4, title=f"Owner review {index}", body="Approved feedback.",
                is_approved=True,
            )

        response = self.client.get(reverse("core:home"))

        self.assertEqual(len(response.context["reviews"]), 10)
        self.assertNotContains(response, "Owner review 0")
        self.assertContains(response, "Owner review 11")

    def test_database_rejects_second_review_for_same_product_and_email(self):
        values = {
            "product": self.product,
            "name": "Customer",
            "email": "same@example.com",
            "rating": 4,
            "title": "First",
            "body": "First review",
        }
        Review.objects.create(**values)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(**{**values, "title": "Duplicate"})


@override_settings(STORAGES=TEST_STORAGES)
class AdminAccessibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )

    def test_anonymous_user_is_redirected_to_admin_login(self):
        response = self.client.get(reverse("admin:index"))

        self.assertRedirects(
            response,
            f"{reverse('admin:login')}?next={reverse('admin:index')}",
        )

    def test_staff_user_can_open_admin_and_core_changelists(self):
        self.client.force_login(self.admin)

        for url_name in (
            "admin:index",
            "admin:catalog_product_changelist",
            "admin:catalog_bundle_changelist",
            "admin:orders_order_changelist",
            "admin:orders_province_changelist",
            "admin:orders_city_changelist",
            "admin:reviews_review_changelist",
        ):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)
