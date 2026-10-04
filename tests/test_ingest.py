"""Tests for ingestion/ingest.py (standard library unittest).

Run from the repository root:
    python3 -m unittest discover -s tests -p "test_*.py" -v
"""

import importlib.util
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ingest", REPO / "ingestion" / "ingest.py")
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)

AMAZON_FILE = REPO / "test-data/amazon-data/2026Sep26-2026Oct2CustomTransaction.csv"
EBAY_FILE = REPO / "test-data/ebay-data/Transaction_report_20260926_20261002.csv"
SGW_FILE = REPO / "test-data/goodwill-data/ShopGoodwill_Listings_20260916_20261002.csv"


def normalize(*paths):
    return ingest.normalize_files(paths, copy_files=False)


def orders_for(norm, source):
    return {oid: o for (s, oid), o in norm.orders.items() if s == source}


class DetectFormat(unittest.TestCase):
    def test_detects_each_marketplace_from_its_header(self):
        for path, source in [(AMAZON_FILE, ingest.AMZ), (EBAY_FILE, ingest.EBAY), (SGW_FILE, ingest.SGW)]:
            detected, _ = ingest.detect(ingest.read_lines(path))
            self.assertEqual(detected, source, path.name)

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ingest.IngestError):
            ingest.detect(["just,some,columns", "1,2,3"])

    def test_reads_reporting_period_from_file(self):
        for path, source in [(AMAZON_FILE, ingest.AMZ), (EBAY_FILE, ingest.EBAY)]:
            self.assertEqual(ingest.file_period(source, path, ingest.read_lines(path)),
                             (date(2026, 9, 26), date(2026, 10, 2)))
        self.assertEqual(ingest.file_period(ingest.SGW, SGW_FILE, []), (date(2026, 9, 16), date(2026, 10, 2)))


class ParseHelpers(unittest.TestCase):
    def test_money_treats_blank_and_dashes_as_missing(self):
        self.assertIsNone(ingest.money("--"))
        self.assertIsNone(ingest.money(""))
        self.assertEqual(ingest.money("-1,234.50"), Decimal("-1234.50"))
        self.assertEqual(ingest.amount("--"), Decimal("0"))

    def test_amazon_time_honors_stated_zone(self):
        dt = ingest.parse_amazon_time("Sep 26, 2026 3:01:22 AM PDT")
        self.assertEqual(dt.isoformat(), "2026-09-26T03:01:22-07:00")
        with self.assertRaises(ingest.IngestError):
            ingest.parse_amazon_time("Sep 26, 2026 3:01:22 AM XYZ")

    def test_negative_zero_is_written_as_zero(self):
        self.assertEqual(str(ingest.cents(-Decimal("0"))), "0.00")

    def test_unmatched_title_without_root_is_reported(self):
        norm = ingest.Normalized()
        self.assertEqual(norm.categorize("Mystery Object 3000"), (None, None))
        self.assertEqual(norm.unmapped_titles, ["Mystery Object 3000"])
        # With a source root category, an unmatched title stays in that root.
        self.assertEqual(norm.categorize("Mystery Object 3000", root="Home"), ("Home", None))


class Amazon(unittest.TestCase):
    def setUp(self):
        self.norm = normalize(AMAZON_FILE)
        self.orders = orders_for(self.norm, ingest.AMZ)

    def test_groups_rows_into_orders_and_lines(self):
        self.assertEqual(len(self.orders), 16)
        self.assertEqual(sum(len(o["lines"]) for o in self.orders.values()), 21)

    def test_order_money_matches_report(self):
        o = self.orders["113-4140674-6772469"]  # two items in one order
        self.assertEqual(o["shipping_charge_amount"], Decimal("7.98"))
        self.assertEqual(o["tax_amount"], Decimal("18.92"))  # 13.48 + 5.44
        self.assertEqual(o["operation_fee_amount"], Decimal("41.74"))  # 29.49 + 12.25
        self.assertEqual([l["unit_price"] for l in o["lines"]], [Decimal("192.61"), Decimal("77.67")])

    def test_quantity_two_line_uses_per_unit_price(self):
        line = next(l for l in self.orders["112-6279323-3428428"]["lines"] if l["quantity"] == 2)
        self.assertEqual(line["unit_price"], Decimal("75.60"))  # 151.20 / 2

    def test_refund_row_becomes_positive_refund_amount(self):
        o = self.orders["112-2840351-5705543"]
        self.assertEqual(o["lines"][0]["refund_amount"], Decimal("162.46"))
        self.assertEqual(o["status"], "REFUNDED")
        self.assertEqual(self.orders["114-4162996-9117501"]["status"], "COMPLETED")

    def test_account_level_rows_are_skipped_and_counted(self):
        self.assertEqual(self.norm.skipped["Amazon Service Fee rows (account-level; no table for them)"], 1)
        self.assertEqual(self.norm.skipped["Amazon Adjustment rows (account-level; no table for them)"], 1)

    def test_no_customer_identity(self):
        self.assertTrue(all(o["source_customer_id"] is None for o in self.orders.values()))
        self.assertEqual(self.norm.customers, {})


class EBay(unittest.TestCase):
    def setUp(self):
        self.norm = normalize(EBAY_FILE)
        self.orders = orders_for(self.norm, ingest.EBAY)

    def test_groups_rows_and_ignores_footer(self):
        self.assertEqual(len(self.orders), 12)
        self.assertEqual(sum(len(o["lines"]) for o in self.orders.values()), 18)
        self.assertEqual(self.norm.batches[0]["_rows"], 34)  # matches "34 record(s) downloaded"

    def test_shipping_label_row_is_the_carrier_cost(self):
        self.assertEqual(self.orders["22-14710-69895"]["shipping_cost_amount"], Decimal("13.40"))

    def test_promoted_listing_fee_is_added_to_order_fees(self):
        self.assertEqual(self.orders["26-10980-53897"]["operation_fee_amount"], Decimal("10.36"))  # 0.40 + 7.73 + 2.23

    def test_shipping_is_summed_across_lines(self):
        self.assertEqual(self.orders["19-11466-28243"]["shipping_charge_amount"], Decimal("5.99"))  # 0.11 + 0.19 + 5.69

    def test_refunds_and_status(self):
        o = self.orders["16-10737-65422"]
        self.assertEqual(o["lines"][0]["refund_amount"], Decimal("111.70"))
        self.assertEqual(o["status"], "REFUNDED")
        partial = self.orders["19-11466-28243"]  # one of three lines refunded
        self.assertEqual(sorted(l["refund_amount"] for l in partial["lines"])[-1], Decimal("100.48"))
        self.assertEqual(partial["status"], "COMPLETED")

    def test_buyers_become_customers(self):
        self.assertEqual(len(self.norm.customers), 6)
        jasmine = self.norm.customers[(ingest.EBAY, "thriftqueen_88")]
        self.assertEqual((jasmine["first_name"], jasmine["last_name"], jasmine["state"]), ("Jasmine", "Carter", "OH"))
        self.assertEqual(self.orders["16-10737-65422"]["source_customer_id"], "thriftqueen_88")


class ShopGoodwill(unittest.TestCase):
    def setUp(self):
        self.norm = normalize(SGW_FILE)
        self.listings = {k[1]: l for k, l in self.norm.listings.items()}

    def test_listing_states_map_to_spec_statuses(self):
        statuses = sorted(l["status"] for l in self.listings.values())
        self.assertEqual(statuses.count("SOLD"), 16)
        self.assertEqual(statuses.count("ENDED_UNSOLD"), 3)  # includes "Relisted"
        self.assertEqual(statuses.count("ACTIVE"), 1)

    def test_active_listing_has_no_end_time(self):
        active = next(l for l in self.listings.values() if l["status"] == "ACTIVE")
        self.assertIsNone(active["ended_at"])

    def test_sold_listing_becomes_order_with_source_amounts(self):
        o = self.norm.orders[(ingest.SGW, "SGW-214886563")]
        self.assertEqual(o["lines"][0]["unit_price"], Decimal("252.74"))
        self.assertEqual(o["shipping_charge_amount"], Decimal("8.11"))  # shipping 6.11 + handling 2.00
        self.assertEqual(o["shipping_cost_amount"], Decimal("6.11"))

    def test_uses_source_root_category(self):
        self.assertEqual(self.norm.products["GWM-SGW-00017"]["category_name"], "Collectibles")  # Pyrex filed by SGW under Collectibles
        self.assertEqual(self.norm.products["GWM-SGW-00001"]["parent_category_name"], "Jewelry & Gemstones")


class FileDates(unittest.TestCase):
    """Records are dated by when each file says the transaction happened."""

    def test_amazon_orders_keep_their_reported_time(self):
        norm = normalize(AMAZON_FILE)
        first = norm.orders[(ingest.AMZ, "112-2840351-5705543")]["ordered_at"]
        self.assertEqual(first.isoformat(), "2026-09-26T03:01:22-07:00")

    def test_ebay_orders_keep_their_reported_date(self):
        norm = normalize(EBAY_FILE)
        self.assertEqual(norm.orders[(ingest.EBAY, "25-13956-54400")]["ordered_at"].date(), date(2026, 9, 26))
        self.assertEqual(norm.orders[(ingest.EBAY, "25-14837-60019")]["ordered_at"].date(), date(2026, 10, 2))

    def test_shopgoodwill_sale_is_dated_at_auction_close(self):
        norm = normalize(SGW_FILE)
        order = norm.orders[(ingest.SGW, "SGW-214886563")]
        listing = norm.listings[(ingest.SGW, "214886563")]
        self.assertEqual(order["ordered_at"], listing["ended_at"])
        self.assertEqual(order["ordered_at"].isoformat(), "2026-09-29T19:34:22-07:00")

    def test_orders_span_the_files_own_days(self):
        norm = normalize(AMAZON_FILE, EBAY_FILE, SGW_FILE)
        days = {o["ordered_at"].date() for o in norm.orders.values()}
        self.assertEqual(min(days), date(2026, 9, 26))
        self.assertEqual(max(days), date(2026, 10, 2))
        self.assertGreater(len(days), 3)  # spread over the week, not piled onto one day
        for order in norm.orders.values():
            for line in order["lines"]:
                listing = norm.listings[(line["source_name"], line["source_listing_id"])]
                self.assertLessEqual(listing["listed_at"], order["ordered_at"])

    def test_batches_keep_the_files_reporting_period(self):
        norm = normalize(AMAZON_FILE, SGW_FILE)
        periods = {b["source_name"]: (b["period_start"], b["period_end"]) for b in norm.batches}
        self.assertEqual(periods[ingest.AMZ], (date(2026, 9, 26), date(2026, 10, 2)))
        self.assertEqual(periods[ingest.SGW], (date(2026, 9, 16), date(2026, 10, 2)))


class Output(unittest.TestCase):
    def test_writes_one_csv_per_table_with_valid_money(self):
        norm = normalize(AMAZON_FILE, EBAY_FILE, SGW_FILE)
        with tempfile.TemporaryDirectory() as tmp:
            ingest.write_csvs(norm, tmp)
            names = sorted(p.stem for p in Path(tmp).glob("*.csv"))
            self.assertEqual(names, ["category", "customer", "ingestion_batch", "listing", "order_item", "product",
                                     "review", "sales_order", "source"])
            self.assertNotIn("-0.00", (Path(tmp) / "sales_order.csv").read_text())
        for order in norm.orders.values():
            for field in ("shipping_charge_amount", "shipping_cost_amount", "tax_amount", "operation_fee_amount"):
                self.assertGreaterEqual(order[field], 0)


if __name__ == "__main__":
    unittest.main()
