# Ingestion

Reads marketplace export files, archives them untouched, normalizes them into
the common schema ([DATABASE_SPEC.md](../docs/DATABASE_SPEC.md)), and loads
them into PostgreSQL. This is the "ingest + archive → normalize / enrich" step
of [ARCHITECTURE.md](../docs/ARCHITECTURE.md).

| File | Purpose |
|---|---|
| `ingest.py` | Detects each file's format, normalizes it, archives it, and loads it. Python 3.9+, standard library only. |
| `load_normalized.sql` | Shared insert-only loader for normalized CSVs. Also used by `test-data/historical/load_historical.sql`. |
| `archive/` | Untouched copies of ingested files, created on first run and git-ignored. |

## Run it

From the repository root, with PostgreSQL's `psql` on your PATH and the
database already migrated (`database/migrate.sql`):

```sh
set -a; source .env; set +a                     # connection settings
PGDATABASE=goodwill_db_test python3 ingestion/ingest.py
```

**Inputs:**
- With no file arguments, it reads every CSV in `test-data/amazon-data/`,
  `test-data/ebay-data/` and `test-data/goodwill-data/`.
- You can also pass specific files: `python3 ingestion/ingest.py path/to/file.csv`.

**Options:**
- `--dry-run --out <folder>` parses and reports only, and writes the normalized
  CSVs for review. It touches no database and archives nothing.
- `PGDATABASE` must be set, so the target database is always an explicit choice.

**Dates:** every record is dated by when its file says it happened. That means
the order time, or a listing's start and end times. Each file's data therefore
lands on its own days, next to whatever is already stored for those days. The
batch keeps the reporting period stated by the file.

Dashboards report in Goodwill's Eastern time, so a late-evening Pacific sale can
fall on the next day. For example, ShopGoodwill's Pyrex auction closed at
9:34 PM Pacific on Oct 2, which is 12:34 AM Eastern on Oct 3.

**Each run prints:**
- what it parsed
- every value it had to fill (see "Enrichment")
- rows it deliberately skipped
- the orders now in the database for those files

**Safety:**
- The load is one transaction: if any row can't be matched, nothing is committed.
- Existing rows are never updated or deleted, and rerunning the same files adds nothing.
- Archive paths include a hash of the file's contents, so the same file always
  maps to the same batch.

## What each format supplies

The format is detected from the header row, not the file name.

| | Amazon transaction report | eBay transaction report | ShopGoodwill listings export |
|---|---|---|---|
| Orders | `Order` rows grouped by order ID; `Refund` rows become positive `refund_amount` | `Order` rows grouped by order number; `Refund` rows become `refund_amount` | One order per `Sold` listing, ID `SGW-<Channel ID>` *(derived)* |
| Listing | Seller SKU is the listing ID; start time *(enriched)* | Item ID; start time *(enriched)* | Channel ID, Start/End Time; `Relisted` becomes `ENDED_UNSOLD`; `Active` has no end |
| Customer | None (no buyer ID) | Buyer username used as the ID; name and address | None |
| Category | From the title *(enriched)* | From the title *(enriched)* | Root from `Category Name`; subcategory from the title when it agrees |
| Shipping charge / cost | Shipping credits / *(estimated)* | Shipping and handling / `Shipping label` rows, else *(estimated)* | Shipping + Handling Price / Shipping Price |
| Tax | Product, shipping and gift-wrap tax | Seller- plus eBay-collected tax | *(estimated)* |
| Fees | Selling, FBA, other transaction and regulatory fees | Final value fees and other fee columns, plus `Other fee` rows for the order (promoted listings) | *(estimated)* |
| Times | Stated zone honored (PDT/PST) | Dates only, Pacific | No zone; read as Pacific |

These rows are skipped and counted, because no table holds them:
- payouts
- store subscriptions
- service fees
- reimbursements
- fee credits on refunds

The spec has no representation yet for refunded fees, shipping or tax.

## Enrichment (needs team sign-off)

The spec requires facts these exports don't contain. Rather than inventing
values silently, every such rule is defined in one block at the top of
`ingest.py` (`ENRICHMENT`), and every run reports how many values each rule
filled. These are provisional answers to the open decisions in DATABASE_SPEC §9:

- **Listing start time (Amazon, eBay):** set to the order time, so days-to-sell
  is 0 for these records.
- **Carrier cost (Amazon; eBay without a label row):** the buyer's shipping
  charge, or a flat $8.50 per package when shipping was free.
- **ShopGoodwill tax and fees:** 7% tax; fees are a 9% commission plus 2.9% + $0.30
  payment processing.
- **ShopGoodwill order IDs:** derived from the listing, since the export has no
  order records.
- **Time zones:** Pacific when a file states none, and noon for eBay's date-only
  rows.
- **eBay customer identity:** the username. The spec says usernames aren't
  identity keys, but the report offers nothing else.
- **Categories:** keyword rules in `CATEGORY_RULES`. A title matching no rule
  stops the run with a list of titles to add rules for. ShopGoodwill items stay
  in their root category instead.

## Tests

```sh
python3 -m unittest discover -s tests -p "test_*.py" -v
```

`tests/test_ingest.py` checks format detection and money parsing against the
fixture files. It also covers grouping, refunds, statuses, shipping labels,
promoted-listing fees, customers, category mapping, and that every record keeps
its file's own dates.
