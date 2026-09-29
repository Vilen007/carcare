from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Bundle, BundleItem, Category, Product, ProductImage
from apps.content.models import HeroSlide, Page, SiteSettings
from apps.orders.models import City, Province


CATALOG = {
    "Exterior Care": [
        ("Ceramic Wash Shampoo", "EXT-SHM-500", "A pH-balanced, high-foam wash that leaves a slick hydrophobic finish.", 1650),
        ("Graphene Quick Detailer", "EXT-GQD-500", "Instant gloss and water repellency for paint, glass and trim.", 2200),
        ("Signature Hard Wax", "EXT-WAX-180", "Deep wet-look protection with premium carnauba and polymers.", 1950),
    ],
    "Interior Care": [
        ("Cabin All-Purpose Cleaner", "INT-APC-500", "Low-foam cleaner for dashboards, vinyl, fabric and plastics.", 1100),
        ("Leather Clean & Guard", "INT-LTH-300", "Gently cleans and conditions finished automotive leather.", 1750),
        ("Fabric & Carpet Shield", "INT-FAB-500", "Lifts stains and adds an invisible spill-resistant barrier.", 1450),
    ],
    "Engine Care": [
        ("Engine Degreaser Pro", "ENG-DEG-500", "Fast-acting degreaser that cuts oil and road grime safely.", 1200),
        ("Long-Life Coolant", "ENG-CLT-1L", "Ready-to-use coolant formulated for year-round protection.", 950),
    ],
    "Tire & Wheel": [
        ("Satin Tire Dressing", "TIR-DRS-500", "A dry-touch satin finish with durable UV protection.", 900),
        ("Iron Fallout Remover", "WHL-IRON-500", "Color-changing wheel cleaner that dissolves embedded fallout.", 1850),
    ],
    "Fragrances": [
        ("Noir Cabin Fragrance", "FRA-NOIR-60", "A refined blend of cedar, leather and fresh citrus.", 850),
    ],
    "Accessories": [
        ("Edgeless Microfiber Duo", "ACC-MF-2PK", "Two ultra-plush, laser-cut detailing towels.", 1250),
    ],
}

PROVINCES = {
    "Punjab": {
        "fee": 250,
        "cities": [
            "Attock", "Bahawalnagar", "Bahawalpur", "Bhakkar", "Chakwal", "Chiniot",
            "Dera Ghazi Khan", "Faisalabad", "Gujranwala", "Gujrat", "Hafizabad",
            "Jhang", "Jhelum", "Kasur", "Khanewal", "Khushab", "Lahore", "Layyah",
            "Lodhran", "Mandi Bahauddin", "Mianwali", "Multan", "Muzaffargarh",
            "Narowal", "Nankana Sahib", "Okara", "Pakpattan", "Rahim Yar Khan",
            "Rajanpur", "Rawalpindi", "Sahiwal", "Sargodha", "Sheikhupura",
            "Sialkot", "Toba Tek Singh", "Vehari", "Wazirabad",
        ],
    },
    "Sindh": {
        "fee": 280,
        "cities": [
            "Badin", "Dadu", "Ghotki", "Hyderabad", "Jacobabad", "Jamshoro",
            "Karachi", "Kashmore", "Khairpur", "Larkana", "Matiari",
            "Mirpur Khas", "Naushahro Feroze", "Qambar Shahdadkot", "Sanghar",
            "Shaheed Benazirabad", "Shikarpur", "Sujawal", "Sukkur",
            "Tando Allahyar", "Tando Muhammad Khan", "Thatta", "Umerkot",
        ],
    },
    "Khyber Pakhtunkhwa": {
        "fee": 320,
        "cities": [
            "Abbottabad", "Bannu", "Batkhela", "Battagram", "Charsadda", "Chitral",
            "Daggar", "Dera Ismail Khan", "Hangu", "Haripur", "Karak", "Kohat",
            "Lakki Marwat", "Mansehra", "Mardan", "Mingora", "Nowshera", "Parachinar",
            "Peshawar", "Swabi", "Tank", "Timergara", "Topi",
        ],
    },
    "Balochistan": {
        "fee": 380,
        "cities": [
            "Awaran", "Barkhan", "Chaman", "Dera Allah Yar", "Dera Murad Jamali",
            "Duki", "Gwadar", "Harnai", "Hub", "Jiwani", "Kalat", "Kharan",
            "Khuzdar", "Killa Abdullah", "Killa Saifullah", "Kohlu", "Lasbela",
            "Loralai", "Mastung", "Musakhel", "Nushki", "Panjgur", "Pasni",
            "Pishin", "Quetta", "Sibi", "Surab", "Turbat", "Usta Muhammad",
            "Zhob", "Ziarat",
        ],
    },
    "Islamabad Capital Territory": {"fee": 220, "cities": ["Islamabad"]},
    "Gilgit-Baltistan": {
        "fee": 450,
        "cities": ["Aliabad", "Astore", "Chilas", "Gahkuch", "Gilgit", "Khaplu", "Shigar", "Skardu"],
    },
    "Azad Jammu & Kashmir": {
        "fee": 380,
        "cities": [
            "Athmuqam", "Bagh", "Bhimber", "Hattian Bala", "Haveli", "Kotli",
            "Mirpur", "Muzaffarabad", "Pallandri", "Rawalakot",
        ],
    },
}


class Command(BaseCommand):
    help = "Create a complete, repeatable demonstration storefront."

    def handle(self, *args, **options):
        SiteSettings.objects.update_or_create(pk=1, defaults={
            "store_name": "Carcare",
            "announcement": "Complimentary delivery above Rs. 5,000 · Cash on delivery nationwide",
            "support_email": "hello@carcare.pk",
            "support_phone": "+92 300 0000000",
        })
        hero, _ = HeroSlide.objects.update_or_create(pk=1, defaults={
            "eyebrow": "Precision detailing, refined",
            "title": "Preserve the machine. Elevate every drive.",
            "subtitle": "Professional-grade formulas designed for Pakistan's roads, climate and enthusiasts.",
            "cta_label": "Explore the collection",
            "cta_url": "/shop/",
            "is_active": True,
        })
        self._attach(hero, "image", settings.BASE_DIR / "static" / "img" / "hero.webp", "carcare-hero.webp")

        categories = {}
        for order, (name, products) in enumerate(CATALOG.items()):
            category, _ = Category.objects.update_or_create(
                slug=name.lower().replace(" & ", "-").replace(" ", "-"),
                defaults={"name": name, "description": f"Premium {name.lower()} developed for lasting results.", "sort_order": order},
            )
            categories[name] = category
            for index, (product_name, sku, description, price) in enumerate(products):
                product, created = Product.objects.update_or_create(sku=sku, defaults={
                    "category": category,
                    "name": product_name,
                    "slug": product_name.lower().replace("&", "and").replace(" ", "-"),
                    "short_description": description,
                    "description": f"{description}\n\nEngineered for effortless application and a consistently refined finish.",
                    "usage": "Test on an inconspicuous area. Apply to a cool surface and follow the product-specific directions.",
                    "specifications": {"Finish": "Professional", "Origin": "Pakistan", "Suitable for": name},
                    "price": Decimal(price),
                    "compare_at_price": Decimal(price) * Decimal("1.15") if index == 0 else None,
                    "stock": 30 + index * 5,
                    "status": Product.Status.ACTIVE,
                    "is_featured": index < 2,
                    "is_new": index == 0,
                })
                if not product.images.exists():
                    image = ProductImage(product=product, is_primary=True, alt_text=product.name)
                    self._attach(image, "image", settings.BASE_DIR / "static" / "img" / "products.webp", f"{product.slug}.webp")

        starter, _ = Bundle.objects.update_or_create(slug="essential-detailing-kit", defaults={
            "name": "Essential Detailing Kit",
            "description": "The core routine for a pristine exterior and refined cabin.",
            "discount_percent": 10,
            "is_active": True,
        })
        BundleItem.objects.filter(bundle=starter).delete()
        for product in Product.objects.filter(sku__in=["EXT-SHM-500", "EXT-GQD-500", "INT-APC-500"]):
            BundleItem.objects.create(bundle=starter, product=product)
        builder, _ = Bundle.objects.update_or_create(slug="build-your-ritual", defaults={
            "name": "Build Your Ritual",
            "description": "Select any three to six essentials and save 12%.",
            "discount_percent": 12,
            "is_active": True,
            "is_custom_builder": True,
            "minimum_items": 3,
            "maximum_items": 6,
        })
        builder.eligible_categories.set(categories.values())

        for name, data in PROVINCES.items():
            province, _ = Province.objects.update_or_create(name=name, defaults={
                "shipping_fee": data["fee"], "cod_fee": 0,
                "free_shipping_threshold": 5000, "estimated_days": "2–5 business days",
                "is_active": True,
            })
            for city_name in data["cities"]:
                City.objects.update_or_create(
                    province=province, name=city_name, defaults={"is_active": True}
                )
        for slug, title in [
            ("about", "Our Standard"), ("shipping-policy", "Shipping Policy"),
            ("returns", "Returns & Refunds"), ("privacy", "Privacy Policy"), ("terms", "Terms & Conditions"),
        ]:
            Page.objects.update_or_create(slug=slug, defaults={
                "title": title,
                "body": f"{title}\n\nThis demonstration content is editable from the Carcare administration portal. Replace it with your approved business policy before launch.",
            })
        self.stdout.write(self.style.SUCCESS("Carcare demo catalog, content, provinces and cities are ready."))

    def _attach(self, instance, field_name, source, filename):
        if Path(source).exists() and not getattr(instance, field_name):
            with open(source, "rb") as handle:
                getattr(instance, field_name).save(filename, File(handle), save=True)
