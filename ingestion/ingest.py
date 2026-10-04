#!/usr/bin/env python3
"""Ingest marketplace export files into the Goodwill database.

For each input file this script:
  1. detects the format from the file's header row (Amazon transaction report,
     eBay transaction report, or ShopGoodwill listings export),
  2. archives the untouched file under ingestion/archive/ (content-addressed),
  3. normalizes its rows into the common schema in docs/DATABASE_SPEC.md, and
  4. loads them with load_normalized.sql (insert-only; existing rows are kept).

Every record is dated by when the file says it happened (order, listing start
and end times), so each file's data lands on its own days alongside the rest
of the database.

Source files never contain every required fact. Values the files do not
supply are filled by the explicit rules in the ENRICHMENT section below, and
every run reports how many values each rule filled.

Usage (from the repository root, Python 3.9+, standard library + psql):
    set -a; source .env; set +a
    PGDATABASE=goodwill_db_test python3 ingestion/ingest.py
    python3 ingestion/ingest.py --dry-run --out /tmp/normalized   # parse only, no database

With no file arguments it ingests every CSV in test-data/{amazon,ebay,goodwill}-data/.
"""

import argparse
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER = Path(__file__).resolve().parent / "load_normalized.sql"
DEFAULT_ARCHIVE_DIR = Path(__file__).resolve().parent / "archive"
DEFAULT_INPUT_DIRS = ["test-data/amazon-data", "test-data/ebay-data", "test-data/goodwill-data"]

AMZ, EBAY, SGW = "Amazon", "eBay", "ShopGoodwill"
SOURCE_FOLDER = {AMZ: "amazon-data", EBAY: "ebay-data", SGW: "goodwill-data"}

# Goodwill Michiana's time zone (used for ingestion timestamps and reporting).
REPORT_TZ = ZoneInfo("America/Indiana/Indianapolis")

# ---------------------------------------------------------------------------
# ENRICHMENT: configured rules for facts the source files do not supply.
# These are provisional and need team sign-off (DATABASE_SPEC §9 "Missing money",
# "Timestamps"). Each use is counted and reported after every run.
# ---------------------------------------------------------------------------

# Time zone assumed when a source gives no offset (eBay says "Pacific time";
# ShopGoodwill's site runs on Pacific time).
SOURCE_TZ = {AMZ: ZoneInfo("America/Los_Angeles"), EBAY: ZoneInfo("America/Los_Angeles"),
             SGW: ZoneInfo("America/Los_Angeles")}
# eBay reports dates without a time; use this local time of day.
DATE_ONLY_TIME = time(12, 0)
# Carrier cost when a source reports none: the buyer's shipping charge if any,
# otherwise this flat per-package estimate.
ESTIMATED_SHIPPING_COST_PER_PACKAGE = Decimal("8.50")
# ShopGoodwill listing exports carry no tax or fees; estimate them.
SGW_ESTIMATED_TAX_RATE = Decimal("0.07")
SGW_COMMISSION_RATE = Decimal("0.09")
SGW_PAYMENT_RATE = Decimal("0.029")
SGW_PAYMENT_FIXED = Decimal("0.30")

# Title keywords → (root category, subcategory). Amazon and eBay reports carry
# no category; ShopGoodwill gives only a root, so a rule is used only when it
# agrees with that root (otherwise the product stays in the root category).
CATEGORY_RULES = [
    (r"film camera|35mm|polaroid|\bae-1\b|k1000", "Cameras & Photo", "Film Cameras"),
    (r"digital camera|\bdslr\b|powershot|coolpix|cyber-shot", "Cameras & Photo", "Digital Cameras"),
    (r"\blens\b", "Cameras & Photo", "Lenses"),
    (r"pyrex|le creuset|dutch oven|mixing bowl|skillet|casserole|kitchenaid|dinnerware|corningware",
     "Home", "Kitchen & Dining"),
    (r"\blamp\b|chandelier", "Home", "Lamps & Lighting"),
    (r"\bsofa\b|\bcouch\b|dresser|\btable\b|\bchair\b|bookcase|nightstand", "Home", "Furniture"),
    (r"\brug\b|\bquilt\b|blanket|bedspread", "Home", "Rugs & Textiles"),
    (r"\bipod\b|\biphone\b|\bipad\b|kindle|galaxy|tablet", "Electronics", "Phones & Tablets"),
    (r"speaker|headphone|soundlink|airpods|receiver|turntable", "Electronics", "Audio & Headphones"),
    (r"macbook|laptop|thinkpad|chromebook|\bimac\b", "Electronics", "Computers & Laptops"),
    (r"game boy|playstation|\bxbox\b|console|nintendo 64|\bwii\b", "Video Games", "Consoles"),
    (r"funko|figurine|hummel|precious moments|lladro", "Collectibles", "Figurines"),
    (r"pokemon|trading card|baseball card|yu-gi-oh|magic the gathering", "Collectibles", "Trading Cards"),
    (r"\bvinyl\b|\blp\b", "Collectibles", "Vinyl Records"),
    (r"\bcoins?\b|silver dollar|penny|proof set", "Collectibles", "Coins & Currency"),
    (r"\bwatch\b|seiko|citizen|timex|omega|bulova", "Jewelry & Gemstones", "Watches"),
    (r"\bsterling\b|\b925\b", "Jewelry & Gemstones", "Sterling Silver"),
    (r"\b(10|14|18)k\b|\bgold\b|diamond", "Jewelry & Gemstones", "Fine Jewelry"),
    (r"brooch|costume jewelry|clip earrings|rhinestone", "Jewelry & Gemstones", "Costume Jewelry"),
    (r"hot wheels|barbie|action figure|american girl|transformers|\bdoll\b", "Toys & Games", "Dolls & Action Figures"),
    (r"\blego\b", "Toys & Games", "LEGO"),
    (r"board game|monopoly|scrabble|catan|puzzle", "Toys & Games", "Board Games"),
    (r"cookbook|cooking|first edition|antique.*book|\bbible\b", "Books", "Vintage & Rare Books"),
    (r"harry potter|hardcover|\bnovels?\b|stephen king|grisham|agatha christie|tolkien", "Books", "Hardcover Fiction"),
    (r"\bwomen'?s\b|\bdress\b|blouse|skirt|leggings", "Clothing", "Women's Clothing"),
    (r"\bjacket\b|fleece|sweater|\bjeans\b|\bshirt\b|flannel|\bcoat\b", "Clothing", "Men's Clothing"),
    (r"\bboots?\b|sneakers?|sandals?|\bshoes?\b", "Clothing", "Shoes"),
    (r"handbag|purse|\btote\b|wallet|crossbody|satchel|sunglasses", "Clothing", "Handbags & Accessories"),
    (r"oil on canvas|painting|watercolor|acrylic", "Art", "Paintings"),
    (r"\bprint\b|lithograph|poster", "Art", "Prints & Posters"),
    (r"pottery|\bvase\b|art glass|depression glass|murano", "Art", "Pottery & Glass"),
    (r"guitar", "Musical Instruments", "Guitars"),
    (r"keyboard|piano|synthesizer", "Musical Instruments", "Keyboards"),
    (r"trumpet|clarinet|flute|trombone|saxophone", "Musical Instruments", "Brass & Woodwind"),
    (r"\bgolf\b|putter", "Sporting Goods", "Golf"),
    (r"\btent\b|lantern|backpack|sleeping bag|fishing", "Sporting Goods", "Outdoor & Camping"),
    (r"dumbbell|kettlebell|\byoga\b", "Sporting Goods", "Fitness"),
]

TZ_ABBREVIATIONS = {"PDT": -7, "PST": -8, "MDT": -6, "MST": -7, "CDT": -5, "CST": -6,
                    "EDT": -4, "EST": -5, "UTC": 0, "GMT": 0}
CENT = Decimal("0.01")
ZERO = Decimal("0")


class IngestError(Exception):
    pass


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def money(value):
    """Parse a money cell; None when the source leaves it blank or '--'."""
    v = (value or "").strip().replace("$", "").replace(",", "")
    if v in ("", "--"):
        return None
    return Decimal(v)


def amount(value):
    """Money cell where blank/'--' means 'not charged' (a known zero)."""
    return money(value) or ZERO


def cents(d):
    return d.quantize(CENT, rounding=ROUND_HALF_UP) + ZERO  # + ZERO turns -0.00 into 0.00


def parse_amazon_time(text):
    """'Sep 26, 2026 3:01:22 AM PDT' → aware datetime, honoring the stated zone."""
    stamp, abbr = text.strip().rsplit(" ", 1)
    naive = datetime.strptime(stamp, "%b %d, %Y %I:%M:%S %p")
    if abbr not in TZ_ABBREVIATIONS:
        raise IngestError(f"Unknown time zone abbreviation {abbr!r} in {text!r}")
    return naive.replace(tzinfo=timezone(timedelta(hours=TZ_ABBREVIATIONS[abbr])))


def parse_month_day_year(text):
    return datetime.strptime(text.strip(), "%b %d, %Y").date()


def split_name(full):
    full = (full or "").strip()
    if not full or full == "--":
        return None, None
    first, _, last = full.partition(" ")
    return first, (last or None)


def blank(value):
    v = (value or "").strip()
    return None if v in ("", "--") else v


# ---------------------------------------------------------------------------
# Normalized result
# ---------------------------------------------------------------------------

class Normalized:
    """Rows for every table, keyed by natural keys, plus an enrichment tally."""

    def __init__(self):
        self.batches = []
        self.products = {}  # sku → row
        self.listings = {}  # (source, listing id) → row
        self.customers = {}  # (source, customer id) → row
        self.orders = {}  # (source, order id) → row with "lines"
        self.categories = set()  # (name, parent name or None)
        self.enriched = Counter()
        self.skipped = Counter()
        self.unmapped_titles = []

    def categorize(self, title, root=None):
        """Map a title to (category, parent) using CATEGORY_RULES."""
        for pattern, rule_root, child in CATEGORY_RULES:
            if re.search(pattern, title, re.IGNORECASE) and (root is None or root == rule_root):
                self.categories.update({(rule_root, None), (child, rule_root)})
                return child, rule_root
        if root:
            self.categories.add((root, None))
            return root, None
        self.unmapped_titles.append(title)
        return None, None

    def add_product(self, sku, name, category, parent):
        self.products.setdefault(sku, dict(sku_number=sku, product_name=name,
                                           category_name=category, parent_category_name=parent))

    def estimate_shipping_cost(self, source, charge, packages=1):
        if charge > 0:
            self.enriched[f"{source}: carrier cost estimated from the buyer's shipping charge"] += 1
            return charge
        self.enriched[f"{source}: carrier cost estimated at ${ESTIMATED_SHIPPING_COST_PER_PACKAGE} per package"] += 1
        return ESTIMATED_SHIPPING_COST_PER_PACKAGE * packages


def finish_order(order):
    """Set order status from its lines and check money facts are non-negative."""
    lines = order["lines"]
    fully_refunded = all(l["refund_amount"] >= l["unit_price"] * l["quantity"] - l["discount_amount"] for l in lines)
    order["status"] = "REFUNDED" if lines and fully_refunded else "COMPLETED"
    for field in ("shipping_charge_amount", "shipping_cost_amount", "tax_amount", "operation_fee_amount"):
        order[field] = cents(order[field])
        if order[field] < 0:
            raise IngestError(f"{order['source_name']} order {order['source_order_id']}: negative {field}")


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def read_lines(path):
    return Path(path).read_text(encoding="utf-8-sig").splitlines()


def detect(lines):
    """Return (source, header row index) from the file's header row."""
    for i, line in enumerate(lines[:20]):
        if line.startswith('"date/time","settlement id"'):
            return AMZ, i
        if line.startswith("Transaction creation date,Type,Order number"):
            return EBAY, i
        if line.startswith("Product SKU,Channel ID"):
            return SGW, i
    raise IngestError("Unrecognized file format (no Amazon, eBay, or ShopGoodwill header row)")


def rows_from(lines, header_index):
    """Data rows under the header; footer lines (e.g. eBay's "34 record(s)
    downloaded") have too few columns and are dropped."""
    reader = csv.DictReader(lines[header_index:])
    return [r for r in reader if None not in r.values() and None not in r]


def file_period(source, path, lines):
    """Reporting period stated by the file (name or preamble), if any."""
    name = Path(path).name
    if source == AMZ:
        m = re.search(r"(\d{4})([A-Z][a-z]{2})(\d{1,2})-(\d{4})([A-Z][a-z]{2})(\d{1,2})", name)
        if m:
            start = datetime.strptime(f"{m[2]} {m[3]} {m[1]}", "%b %d %Y").date()
            end = datetime.strptime(f"{m[5]} {m[6]} {m[4]}", "%b %d %Y").date()
            return start, end
    elif source == EBAY and len(lines) > 1:
        m = re.match(r'"?([A-Z][a-z]{2} \d{1,2}, \d{4}) - ([A-Z][a-z]{2} \d{1,2}, \d{4})"?', lines[1])
        if m:
            return parse_month_day_year(m[1]), parse_month_day_year(m[2])
    else:
        m = re.search(r"_(\d{8})_(\d{8})", name)
        if m:
            return datetime.strptime(m[1], "%Y%m%d").date(), datetime.strptime(m[2], "%Y%m%d").date()
    return None, None


# ---------------------------------------------------------------------------
# Amazon: Custom Transaction report
# ---------------------------------------------------------------------------

AMAZON_FEE_COLUMNS = ["selling fees", "fba fees", "other transaction fees", "Regulatory Fee", "Tax On Regulatory Fee"]
AMAZON_TAX_COLUMNS = ["product sales tax", "shipping credits tax", "giftwrap credits tax"]


def parse_amazon(rows, batch_path, norm):
    order_rows, refunds = defaultdict(list), []
    for r in rows:
        kind = r["type"].strip()
        if kind == "Order":
            order_rows[r["order id"]].append(r)
        elif kind == "Refund":
            refunds.append(r)
        else:
            norm.skipped[f"Amazon {kind} rows (account-level; no table for them)"] += 1

    for order_id, lines in order_rows.items():
        ordered_at = max(parse_amazon_time(r["date/time"]) for r in lines)
        order = dict(source_name=AMZ, source_order_id=order_id, source_customer_id=None, ordered_at=ordered_at,
                     shipping_charge_amount=ZERO, shipping_cost_amount=ZERO, tax_amount=ZERO,
                     operation_fee_amount=ZERO, batch_archived_path=batch_path, lines=[])
        for r in lines:
            sku, qty = r["sku"].strip(), int(r["quantity"])
            title = re.sub(r"\s+-\s+(Used|New|Collectible|Refurbished)$", "", r["description"].strip())
            sales = amount(r["product sales"])
            discount = -amount(r["promotional rebates"])  # rebates are reported as negatives
            order["shipping_charge_amount"] += amount(r["shipping credits"])
            order["tax_amount"] += sum(amount(r[c]) for c in AMAZON_TAX_COLUMNS)
            order["operation_fee_amount"] += -sum(amount(r[c]) for c in AMAZON_FEE_COLUMNS)

            category, parent = norm.categorize(title)
            norm.add_product(sku, title, category, parent)
            # The seller SKU identifies the Amazon offer; the report has no listing start.
            norm.listings[(AMZ, sku)] = dict(source_name=AMZ, source_listing_id=sku, sku_number=sku,
                                             listed_at=ordered_at, ended_at=ordered_at, status="SOLD",
                                             batch_archived_path=batch_path)
            norm.enriched["Amazon: listing start time set to the order time (not in report)"] += 1
            order["lines"].append(dict(source_name=AMZ, source_order_id=order_id, source_listing_id=sku, quantity=qty,
                                       unit_price=cents(sales / qty), discount_amount=cents(discount),
                                       refund_amount=ZERO))
        order["shipping_cost_amount"] = norm.estimate_shipping_cost(AMZ, order["shipping_charge_amount"])
        norm.orders[(AMZ, order_id)] = order

    for r in refunds:
        order = norm.orders.get((AMZ, r["order id"]))
        line = next((l for l in order["lines"] if l["source_listing_id"] == r["sku"].strip()), None) if order else None
        if not line:
            norm.skipped["Amazon refunds for orders not in this file"] += 1
            continue
        line["refund_amount"] += -amount(r["product sales"])  # merchandise refund, stored positive
        norm.skipped["Amazon refund fee credits (no agreed representation)"] += 1

    for (source, _), order in norm.orders.items():
        if source == AMZ:
            finish_order(order)


# ---------------------------------------------------------------------------
# eBay: Transaction report
# ---------------------------------------------------------------------------

EBAY_FEE_COLUMNS = ["Final Value Fee - fixed", "Final Value Fee - variable", "Regulatory operating fee",
                    'Very high "item not as described" fee', "Below standard performance fee",
                    "International fee", "Deposit processing fee"]


def parse_ebay(rows, batch_path, norm):
    order_rows = defaultdict(list)
    label_cost, extra_fees, refunds = defaultdict(Decimal), defaultdict(Decimal), []
    for r in rows:
        kind, order_id = r["Type"].strip(), blank(r["Order number"])
        if kind == "Order":
            order_rows[order_id].append(r)
        elif kind == "Shipping label" and order_id:
            label_cost[order_id] += -amount(r["Net amount"])
        elif kind == "Other fee" and order_id:
            extra_fees[order_id] += -amount(r["Net amount"])  # e.g. Promoted Listings fee
        elif kind == "Refund" and order_id:
            refunds.append(r)
        else:
            norm.skipped[f"eBay {kind} rows (account-level; no table for them)"] += 1

    tz = SOURCE_TZ[EBAY]
    for order_id, lines in order_rows.items():
        ordered_at = max(datetime.combine(parse_month_day_year(r["Transaction creation date"]), DATE_ONLY_TIME, tz)
                         for r in lines)
        norm.enriched["eBay: order time set to noon Pacific (report gives dates only)"] += 1
        first = lines[0]
        username = blank(first["Buyer username"])
        customer_id = None
        if username:
            # The report has no stable buyer ID; the username is the only identifier offered.
            customer_id = username
            first_name, last_name = split_name(first["Buyer name"])
            norm.customers.setdefault((EBAY, customer_id), dict(
                source_name=EBAY, source_customer_id=customer_id, username=username, first_name=first_name,
                last_name=last_name, city=blank(first["Ship to city"]),
                state=blank(first["Ship to province/region/state"]), zipcode=blank(first["Ship to zip"]),
                country=blank(first["Ship to country"]), batch_archived_path=batch_path))
        order = dict(source_name=EBAY, source_order_id=order_id, source_customer_id=customer_id, ordered_at=ordered_at,
                     shipping_charge_amount=ZERO, shipping_cost_amount=ZERO, tax_amount=ZERO,
                     operation_fee_amount=extra_fees.get(order_id, ZERO), batch_archived_path=batch_path, lines=[])
        for r in lines:
            item_id, sku, qty = r["Item ID"].strip(), r["Custom label"].strip(), int(r["Quantity"])
            title = r["Item title"].strip()
            order["shipping_charge_amount"] += abs(amount(r["Shipping and handling"]))
            order["tax_amount"] += amount(r["Seller collected tax"]) + amount(r["eBay collected tax"])
            order["operation_fee_amount"] += -sum(amount(r[c]) for c in EBAY_FEE_COLUMNS)

            category, parent = norm.categorize(title)
            norm.add_product(sku, title, category, parent)
            norm.listings[(EBAY, item_id)] = dict(source_name=EBAY, source_listing_id=item_id, sku_number=sku,
                                                  listed_at=ordered_at, ended_at=ordered_at, status="SOLD",
                                                  batch_archived_path=batch_path)
            norm.enriched["eBay: listing start time set to the order time (not in report)"] += 1
            order["lines"].append(dict(source_name=EBAY, source_order_id=order_id, source_listing_id=item_id,
                                       quantity=qty, unit_price=cents(amount(r["Item subtotal"]) / qty),
                                       discount_amount=ZERO, refund_amount=ZERO))
        if order_id in label_cost:
            order["shipping_cost_amount"] = label_cost[order_id]
        else:
            order["shipping_cost_amount"] = norm.estimate_shipping_cost(EBAY, order["shipping_charge_amount"])
        norm.orders[(EBAY, order_id)] = order

    for r in refunds:
        order = norm.orders.get((EBAY, r["Order number"].strip()))
        line = next((l for l in order["lines"] if l["source_listing_id"] == r["Item ID"].strip()), None) if order else None
        if not line:
            norm.skipped["eBay refunds for orders not in this file"] += 1
            continue
        line["refund_amount"] += -amount(r["Item subtotal"])

    for (source, _), order in norm.orders.items():
        if source == EBAY:
            finish_order(order)


# ---------------------------------------------------------------------------
# ShopGoodwill: listings export
# ---------------------------------------------------------------------------

SGW_STATUS = {"Sold": "SOLD", "Ended - Unsold": "ENDED_UNSOLD", "Relisted": "ENDED_UNSOLD",
              "Active": "ACTIVE", "Cancelled": "CANCELLED", "Canceled": "CANCELLED"}


def parse_sgw(rows, batch_path, norm):
    tz = SOURCE_TZ[SGW]

    def local(text):
        return datetime.strptime(text.strip(), "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=tz)

    for r in rows:
        state = r["State"].strip()
        if state not in SGW_STATUS:
            raise IngestError(f"ShopGoodwill listing {r['Channel ID']}: unknown state {state!r}")
        status = SGW_STATUS[state]
        sku, listing_id, title = r["Product SKU"].strip(), r["Channel ID"].strip(), r["Title"].strip()
        listed_at = local(r["Start Time"])
        ended_at = None if status == "ACTIVE" else local(r["End Time"])
        norm.enriched["ShopGoodwill: times read as Pacific (export gives no time zone)"] += 1

        category, parent = norm.categorize(title, root=r["Category Name"].strip())
        norm.add_product(sku, title, category, parent)
        norm.listings[(SGW, listing_id)] = dict(source_name=SGW, source_listing_id=listing_id, sku_number=sku,
                                                listed_at=listed_at, ended_at=ended_at, status=status,
                                                batch_archived_path=batch_path)
        if status != "SOLD":
            continue

        # The export has no order record: one order per sold listing, closing at auction end.
        price = money(r["Current Price"])
        shipping, handling = amount(r["Shipping Price"]), amount(r["Handling Price"])
        charge = shipping + handling
        tax = cents((price + charge) * SGW_ESTIMATED_TAX_RATE)
        fee = cents(SGW_COMMISSION_RATE * (price + charge) + SGW_PAYMENT_RATE * (price + charge + tax) + SGW_PAYMENT_FIXED)
        norm.enriched["ShopGoodwill: order ID derived from the listing (export has no orders)"] += 1
        norm.enriched["ShopGoodwill: tax estimated at configured rate (not in export)"] += 1
        norm.enriched["ShopGoodwill: fees estimated at configured rates (not in export)"] += 1
        order_id = f"SGW-{listing_id}"
        order = dict(source_name=SGW, source_order_id=order_id, source_customer_id=None, ordered_at=ended_at,
                     shipping_charge_amount=charge, shipping_cost_amount=shipping, tax_amount=tax,
                     operation_fee_amount=fee, batch_archived_path=batch_path,
                     lines=[dict(source_name=SGW, source_order_id=order_id, source_listing_id=listing_id, quantity=1,
                                 unit_price=price, discount_amount=ZERO, refund_amount=ZERO)])
        finish_order(order)
        norm.orders[(SGW, order_id)] = order


PARSERS = {AMZ: parse_amazon, EBAY: parse_ebay, SGW: parse_sgw}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def normalize_files(paths, archive_dir=DEFAULT_ARCHIVE_DIR, copy_files=True):
    norm = Normalized()
    ingested_at = datetime.now(REPORT_TZ).replace(microsecond=0)
    for path in paths:
        path = Path(path)
        lines = read_lines(path)
        source, header_index = detect(lines)
        rows = rows_from(lines, header_index)

        # Content-addressed archive: the same file always maps to the same batch.
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        archived = Path(archive_dir) / SOURCE_FOLDER[source] / digest / path.name
        if copy_files and not archived.exists():
            archived.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, archived)
        try:
            archived_path = archived.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            archived_path = archived.resolve().as_posix()

        PARSERS[source](rows, archived_path, norm)
        start, end = file_period(source, path, lines)
        norm.batches.append(dict(source_name=source, file_name=path.name, archived_path=archived_path,
                                 ingested_at=ingested_at, period_start=start, period_end=end,
                                 _rows=len(rows)))

    if norm.unmapped_titles:
        raise IngestError("No category rule matches these titles; add one to CATEGORY_RULES:\n  "
                          + "\n  ".join(sorted(set(norm.unmapped_titles))))
    return norm


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(cents(value))
    return str(value)


def write_csvs(norm, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    order_lines = [line for order in norm.orders.values() for line in order["lines"]]
    tables = {
        "source": (["name"], [dict(name=s) for s in sorted({b["source_name"] for b in norm.batches})]),
        "category": (["name", "parent_name"],
                     [dict(name=n, parent_name=p) for n, p in sorted(norm.categories, key=lambda c: (c[1] is not None, c))]),
        "ingestion_batch": (["source_name", "file_name", "archived_path", "ingested_at", "period_start", "period_end"],
                            norm.batches),
        "product": (["sku_number", "product_name", "category_name", "parent_category_name"], norm.products.values()),
        "listing": (["source_name", "source_listing_id", "sku_number", "listed_at", "ended_at", "status",
                     "batch_archived_path"], norm.listings.values()),
        "customer": (["source_name", "source_customer_id", "username", "first_name", "last_name", "city", "state",
                      "zipcode", "country", "batch_archived_path"], norm.customers.values()),
        "sales_order": (["source_name", "source_order_id", "source_customer_id", "ordered_at", "status",
                         "shipping_charge_amount", "shipping_cost_amount", "tax_amount", "operation_fee_amount",
                         "batch_archived_path"], norm.orders.values()),
        "order_item": (["source_name", "source_order_id", "source_listing_id", "quantity", "unit_price",
                        "discount_amount", "refund_amount"], order_lines),
        "review": (["source_name", "source_review_id", "source_customer_id", "source_order_id", "rating",
                    "review_text", "reviewed_at", "batch_archived_path"], []),
    }
    for name, (columns, rows) in tables.items():
        with (out_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([fmt(row.get(c)) for c in columns])


def print_report(norm):
    print("Parsed:")
    for b in norm.batches:
        print(f"  {b['source_name']:<13} {b['file_name']}  ({b['_rows']} rows) → {b['archived_path']}")
    by_source = Counter(o["source_name"] for o in norm.orders.values())
    lines = Counter(l["source_name"] for o in norm.orders.values() for l in o["lines"])
    listings = Counter(l["source_name"] for l in norm.listings.values())
    for source in sorted(listings):
        print(f"  {source:<13} {listings[source]} listings, {by_source[source]} orders, {lines[source]} order lines")
    print(f"  customers: {len(norm.customers)}, products: {len(norm.products)}")
    if norm.enriched:
        print("Filled by enrichment rules (values the files do not supply):")
        for rule, n in sorted(norm.enriched.items()):
            print(f"  {n:>4} × {rule}")
    if norm.skipped:
        print("Not loaded:")
        for what, n in sorted(norm.skipped.items()):
            print(f"  {n:>4} × {what}")


def psql(*args, capture=False):
    command = [os.environ.get("PSQL", "psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", *args]
    return subprocess.run(command, check=True, text=True, capture_output=capture)


def summarize_load(norm):
    paths = ", ".join("'" + b["archived_path"].replace("'", "''") + "'" for b in norm.batches)
    query = f"""
        SELECT s.name, COUNT(*), SUM(mv.merchandise_revenue), SUM(mv.total_transaction_revenue),
               MIN(so.ordered_at AT TIME ZONE 'America/Indiana/Indianapolis')::date,
               MAX(so.ordered_at AT TIME ZONE 'America/Indiana/Indianapolis')::date
        FROM sales_order so
        JOIN sales_order_mv mv USING (order_id)
        JOIN ingestion_batch b USING (batch_id)
        JOIN source s ON s.source_id = so.source_id
        WHERE b.archived_path IN ({paths})
        GROUP BY s.name ORDER BY s.name;"""
    out = psql("-At", "-F", "|", "-c", query, capture=True).stdout
    print("In the database for these files:")
    for row in filter(None, out.splitlines()):
        name, n, merch, txn, first, last = row.split("|")
        span = first if first == last else f"{first} – {last}"
        print(f"  {name:<13} {n} orders, merchandise ${merch}, transaction revenue ${txn}, dated {span}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="export files (default: all CSVs in test-data/*-data/)")
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE_DIR, type=Path,
                        help="where untouched source files are archived (default: ingestion/archive)")
    parser.add_argument("--dry-run", action="store_true", help="parse and report only; do not archive or load")
    parser.add_argument("--out", type=Path, help="also keep the normalized CSVs in this folder")
    args = parser.parse_args(argv)

    files = args.files or sorted(str(p) for d in DEFAULT_INPUT_DIRS for p in (REPO_ROOT / d).glob("*.csv"))
    if not files:
        parser.error("no input files found")
    if not args.dry_run and not os.environ.get("PGDATABASE"):
        parser.error("set PGDATABASE (and the other connection variables from .env) to choose the target database")

    try:
        norm = normalize_files(files, args.archive_dir, copy_files=not args.dry_run)
    except IngestError as e:
        print(f"Ingestion failed: {e}", file=sys.stderr)
        return 1
    print_report(norm)
    if args.out:
        write_csvs(norm, args.out)
        print(f"Normalized CSVs written to {args.out}")
    if args.dry_run:
        return 0

    print(f"Loading into database {os.environ['PGDATABASE']!r} ...")
    with tempfile.TemporaryDirectory() as tmp:
        write_csvs(norm, tmp)
        try:
            psql("-v", f"csv_dir={tmp}", "-f", str(LOADER))
        except subprocess.CalledProcessError:
            print("Load failed; nothing was committed.", file=sys.stderr)
            return 1
    summarize_load(norm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
