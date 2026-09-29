from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Category, InventoryAdjustment, Product
from apps.content.models import ContactMessage
from apps.orders.models import Order
from apps.reviews.models import Review


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class DashboardAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="ops",
            email="ops@carcare.pk",
            password="test-password",
            is_staff=True,
        )
        cls.customer = User.objects.create_user(
            username="shopper",
            email="shopper@example.com",
            password="test-password",
        )

    def test_anonymous_user_is_redirected_to_dashboard_login(self):
        response = self.client.get(reverse("dashboard:overview"))
        self.assertRedirects(
            response,
            f"{reverse('dashboard:login')}?next={reverse('dashboard:overview')}",
        )

    def test_non_staff_user_is_sent_to_storefront(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("dashboard:overview"))
        self.assertRedirects(response, reverse("core:home"))

    def test_staff_can_open_core_dashboard_pages(self):
        self.client.force_login(self.staff)
        for name in (
            "dashboard:overview",
            "dashboard:orders",
            "dashboard:products",
            "dashboard:categories",
            "dashboard:inventory",
            "dashboard:bundles",
            "dashboard:promotions",
            "dashboard:shipping",
            "dashboard:reviews",
            "dashboard:customers",
            "dashboard:content",
            "dashboard:inbox",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class DashboardWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="ops2",
            email="ops2@carcare.pk",
            password="test-password",
            is_staff=True,
        )
        cls.category = Category.objects.create(name="Exterior", slug="exterior-ops")
        cls.product = Product.objects.create(
            category=cls.category,
            name="Ops Polish",
            slug="ops-polish",
            sku="OPS-POLISH-1",
            short_description="Polish",
            description="Polish description",
            price=Decimal("200.00"),
            stock=5,
            low_stock_threshold=10,
            status=Product.Status.ACTIVE,
        )
        cls.order = Order.objects.create(
            email="buyer@example.com",
            phone="03001234567",
            full_name="Buyer One",
            address_line_1="Street 1",
            city="Lahore",
            province="Punjab",
            subtotal=Decimal("200.00"),
            total=Decimal("250.00"),
            status=Order.Status.PENDING,
        )
        cls.review = Review.objects.create(
            product=cls.product,
            name="Reviewer",
            email="reviewer@example.com",
            rating=5,
            title="Great",
            body="Works well",
            is_approved=False,
        )
        cls.contact = ContactMessage.objects.create(
            name="Caller",
            email="caller@example.com",
            subject="Help",
            message="Need support",
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.staff)

    def test_bulk_confirm_moves_pending_order_and_adds_tracking(self):
        response = self.client.post(
            reverse("dashboard:orders_confirm"),
            {"order_ids": [str(self.order.pk)]},
        )
        self.assertRedirects(response, reverse("dashboard:orders"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertTrue(self.order.tracking_events.filter(status=Order.Status.CONFIRMED).exists())

    def test_inventory_adjust_updates_stock_and_ledger(self):
        response = self.client.post(
            reverse("dashboard:inventory_adjust"),
            {
                "product": self.product.pk,
                "quantity": 7,
                "reason": InventoryAdjustment.Reason.PURCHASE,
                "reference": "PO-1",
                "note": "Restock",
            },
        )
        self.assertRedirects(response, reverse("dashboard:inventory"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 12)
        entry = InventoryAdjustment.objects.get(product=self.product)
        self.assertEqual(entry.quantity, 7)
        self.assertEqual(entry.created_by, self.staff)

    def test_inventory_damage_decreases_stock(self):
        response = self.client.post(
            reverse("dashboard:inventory_adjust"),
            {
                "product": self.product.pk,
                "quantity": 2,
                "reason": InventoryAdjustment.Reason.DAMAGE,
            },
        )
        self.assertRedirects(response, reverse("dashboard:inventory"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        entry = InventoryAdjustment.objects.filter(product=self.product, reason=InventoryAdjustment.Reason.DAMAGE).latest("pk")
        self.assertEqual(entry.quantity, -2)

    def test_inventory_correction_can_remove_stock(self):
        response = self.client.post(
            reverse("dashboard:inventory_adjust"),
            {
                "product": self.product.pk,
                "quantity": 1,
                "reason": InventoryAdjustment.Reason.CORRECTION,
                "direction": "remove",
            },
        )
        self.assertRedirects(response, reverse("dashboard:inventory"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_review_approve_from_dashboard(self):
        response = self.client.post(reverse("dashboard:review_approve", args=[self.review.pk]))
        self.assertRedirects(response, reverse("dashboard:reviews"))
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_approved)

    def test_contact_resolve_from_inbox(self):
        response = self.client.post(reverse("dashboard:contact_resolve", args=[self.contact.pk]))
        self.assertRedirects(response, reverse("dashboard:inbox"))
        self.contact.refresh_from_db()
        self.assertTrue(self.contact.is_resolved)

    def test_product_new_form_renders(self):
        response = self.client.get(reverse("dashboard:product_new"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New product")

    def test_category_new_form_renders(self):
        response = self.client.get(reverse("dashboard:category_new"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New category")

    def test_staff_login_rejects_non_staff(self):
        self.client.logout()
        get_user_model().objects.create_user(
            username="plain",
            email="plain@example.com",
            password="test-password",
        )
        response = self.client.post(
            reverse("dashboard:login"),
            {"username": "plain", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff access is required")
