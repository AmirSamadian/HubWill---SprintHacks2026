# Synthetic historical dataset

About three years of believable e-commerce history for Goodwill Michiana. It covers
**Nov 4, 2023 – Oct 2, 2026** across ShopGoodwill, eBay and Amazon. The data is
already normalized into the tables in [DATABASE_SPEC.md](../../docs/DATABASE_SPEC.md).

**All of it is fabricated.** It contains no real customers, orders or Goodwill data.

| File | Rows | Table |
|---|---:|---|
| `source.csv` | 3 | `source` |
| `category.csv` | 54 | `category`: 12 root categories and 42 subcategories |
| `ingestion_batch.csv` | 456 | `ingestion_batch`: one weekly export per marketplace |
| `product.csv` | 35,310 | `product` |
| `listing.csv` | 40,433 | `listing` |
| `customer.csv` | 7,588 | `customer` (eBay only) |
| `sales_order.csv` | 26,493 | `sales_order` |
| `order_item.csv` | 29,362 | `order_item` |
| `review.csv` | 2,554 | `review` |

## Load it

From the repository root, after `database/migrate.sql` has been applied:

```sh
PGDATABASE=goodwill_db psql -X -f test-data/historical/load_historical.sql
```

The loader runs in one transaction and refreshes `sales_order_mv` at the end.
- **Existing rows are kept.** It only inserts rows whose key isn't already
  present: marketplace + external ID, SKU, or marketplace + batch archive path.
  It never updates or deletes anything. The insert logic is the shared
  [`ingestion/load_normalized.sql`](../../ingestion/load_normalized.sql).
- **Safe to rerun.** A second run adds nothing.
- **It fails rather than skipping data.** If any listing or order line can't be
  matched to its product, order or batch, the whole load is rolled back.

The CSVs refer to each other by these natural keys (batches by `batch_archived_path`), never by internal numeric
IDs. That way the data loads into any migrated database without assuming seeded
ID values.

Loading this into a database is a one-way addition; there is no "unload" script.
To try it out, use a disposable database such as `goodwill_db_test`.

## Regenerate it

```sh
python3 test-data/historical/generate.py
```

It uses the Python standard library only (3.9+) and runs in about a second. The
output is identical every time unless you change `SEED` or the catalog in the
script.

If you regenerate after a load, drop and recreate the target database before
loading again. The loader skips rows that already exist, so changed values in
the new files would not replace the old ones.

## What it models

- **Intake.** About 34 items a day are processed Monday–Saturday. Donation
  seasonality applies, and volume grows about 14% a year.
- **Products and categories.** Each product sits in a subcategory, e.g.
  Home → Furniture. The 7 seeded root categories are reused and 5 new roots are
  added: Toys & Games, Video Games, Cameras & Photo, Musical Instruments, and
  Sporting Goods.
  - SKUs follow the fixture format: `GWM-SGW-000001`, `GWM-EBY-…` and `GWM-AMZ-…`.
    The prefix shows which marketplace an item was first planned for.
- **Listings by marketplace.**
  - **ShopGoodwill:** 5, 7 or 10-day auctions that close in the evening.
  - **eBay:** 25% are 7-day auctions; the rest are fixed price for up to 90 days.
  - **Amazon:** fixed-price used offers for up to 120 days.
- **Listing outcomes.**
  - About 1.5% of listings are withdrawn (`CANCELLED`).
  - Unsold items are often relisted as a new listing for the **same product**,
    usually cheaper. About 40% of relists move to another marketplace.
  - Listings still running on Oct 2, 2026 are `ACTIVE` with no `ended_at`.
- **Orders.**
  - Multi-item orders: ShopGoodwill buyers often combine wins (about 16% of
    orders); eBay about 7%, Amazon about 4%.
  - Demand peaks in November and December.
  - Quantity is always 1, since donated items are unique.
- **Money**, all stored as non-negative facts:
  - **Shipping charge vs. carrier cost** are kept separate. ShopGoodwill furniture
    is local pickup, so both are `0`. eBay offers free shipping on about 35% of
    orders. Amazon media charges $3.99 per item and ships Media Mail.
  - **Tax** is collected at the buyer's state rate (marketplace facilitator).
    It is 0 for international eBay buyers.
  - **Fees:**

    | Marketplace | Fee model |
    |---|---|
    | ShopGoodwill | 9% commission plus payment processing |
    | eBay | 13.25% of the total plus $0.40 per order, plus promoted-listing fees on about 30% of orders |
    | Amazon | 15% referral fee plus a $1.80 closing fee per media item, matching the fixture's fee math |

  - **Discounts:** eBay markdowns on about 8% of fixed-price lines; Amazon
    promotions on about 3%.
  - **Refunds:** about 2% of lines, mostly full, stored as positive `refund_amount`.
- **Customers.** Only eBay supplies buyer identity, per DATABASE_SPEC §3.6.
  Amazon and ShopGoodwill orders have no `customer_id`.
  - About 23% of eBay buyers order more than once.
  - Some profiles are sparse: about 4% have no name and 2% have no city or zip.
  - About 3% of buyers are international.
- **Reviews.** Ratings are kept on each source's own scale, since the spec leaves
  normalization open.

  | Marketplace | Rating scale | Linked customer |
  |---|---|---|
  | eBay | Feedback: `1` positive, `0` neutral, `-1` negative | Yes |
  | Amazon | Seller feedback, 1–5 stars | No |
  | ShopGoodwill | No reviews | — |

- **Ingestion batches.** One file per marketplace per Saturday–Friday week, named
  like the existing fixtures, e.g. `Transaction_report_20260926_20261002.csv`.
  Each record points to the batch for the week it was first seen: listed,
  ordered, reviewed, or the buyer's first order. `ingested_at` is the following
  Saturday morning.
- **Timezone.** Timestamps carry offsets for America/Indiana/Indianapolis
  (Eastern), the time zone of Goodwill Michiana.

## Assumptions to confirm with the team

These fill gaps the spec leaves open. They live only in this dataset and in no
schema rule:

- **Order statuses:** `COMPLETED`, `SHIPPED` (orders from the last few days) and
  `REFUNDED` (every line fully refunded). The spec's normalized order-status
  vocabulary is still undecided.
- **Archived files:** `archived_path` values are illustrative. No raw export
  files exist for these batches.
  - The last week (Sep 26 – Oct 2, 2026) has the same batch file names as the
    real fixtures in `amazon-data/`, `ebay-data/` and `goodwill-data/`, but
    different contents.
- **Ingestion is bypassed.** This data goes straight into the normalized tables
  without the parsing/normalization step. It is for exercising the database,
  backend queries and dashboards until ingestion exists.
- **Order lines:** the loader treats (order, listing) as a line's identity. That
  holds for this dataset, but the spec has not chosen a line-level key.
