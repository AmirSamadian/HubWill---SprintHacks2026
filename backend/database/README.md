# PostgreSQL database

The database implements [DATABASE_SPEC.md](../../docs/DATABASE_SPEC.md).
Use PostgreSQL 17 and its `psql`/`createdb` clients. No ORM, Python package, or
migration framework is required. SQL files live in `migrations/`; `migrate.sql`
is the entry point. All application tables use the common `public` schema.

## Local setup

Install PostgreSQL 17 using your platform's package manager or PostgreSQL
distribution. For Homebrew on macOS:

```sh
brew install postgresql@17
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"
brew services start postgresql@17
```

Configure connection settings for your own server and role. `.env.example`
lists the supported libpq variables; neither PostgreSQL nor these scripts loads
`.env` automatically. Keep credentials local; use a password prompt or `.pgpass`.
The database role needs permission to create objects in `public`.

From the repository root, with the connection variables exported:

```sh
createdb goodwill_db
PGDATABASE=goodwill_db psql -X -f backend/database/migrate.sql
```

For a remote/existing database, skip `createdb` and set `PGHOST`, `PGPORT`,
`PGUSER`, and `PGDATABASE` as appropriate. Do not point tests at shared data.

## Migrations and reference data

The runner stops on errors, serializes concurrent runs with a transaction-level
advisory lock, and commits all pending migrations together. `schema_migration`
records applied versions. Rerunning the same command skips applied migrations,
including category seeds; it does not rebuild or truncate existing tables.

- `001_initial_schema.sql`: nine domain tables, constraints/indexes, and
  `sales_order_mv` with a unique `order_id` index.
- `002_reference_data.sql`: Amazon, eBay, ShopGoodwill, and the seven categories
  present in the ShopGoodwill fixture. No source hierarchy is available, so these
  start as roots. Other sources need explicit canonical category mapping.

Add future changes as numbered migrations and register them in `migrate.sql`.
Do not edit migrations already applied to a team database. The small runner
does not detect edits to previously applied files or provide down migrations.
Use a fresh disposable database to test a changed initial migration during review.

## Implementation choices

- Keys: `BIGINT GENERATED ALWAYS AS IDENTITY`; omit IDs on inserts and use
  `RETURNING`. Resolve sources by name, never by assumed numeric seed IDs.
- Money and ratings: unconstrained `NUMERIC`. Monetary facts must be finite and
  non-negative. No implicit zero, quantity, status, or business timestamp defaults.
- Times: `TIMESTAMPTZ`. Normalization must honor any supplied timezone; otherwise
  it must apply a configured source timezone or configured default. If neither
  is available, reject/defer the record rather than silently using the machine
  timezone. PostgreSQL retains the instant, not the original timezone name or
  offset; preserve the original text in the untouched archived file. Configure
  reporting timezone in backend queries; do not assume UTC business dates.
- Date checks reject reversed reporting periods and listing end times while
  allowing the specified nullable fields.
- FKs use PostgreSQL's default `NO ACTION` on delete/update, without cascading
  history deletion. Same-source consistency across related entities remains a
  normalization responsibility; no additional composite FKs or triggers are added.
- Empty orders remain in the materialized view with `NULL` derived totals.
  Their known header amounts remain available. No minimum item count is enforced.

## Refreshing totals

After a successful normalized import, the ingestion/backend caller must run:

```sh
PGDATABASE=goodwill_db psql -X -v ON_ERROR_STOP=1 \
  -c 'REFRESH MATERIALIZED VIEW public.sales_order_mv;'
```

The view aggregates lines before joining headers, so shipping, tax, and fees are
counted once per order. It is initially populated (and queryable even when empty).
There is no refresh trigger or scheduler. Consumers must account for stale data
until refresh and `NULL` totals for incomplete orders.

## Validation

Use a separate disposable database on your local server:

```sh
createdb goodwill_db_test
PGDATABASE=goodwill_db_test psql -X -f backend/database/migrate.sql
PGDATABASE=goodwill_db_test psql -X -f backend/database/migrate.sql
PGDATABASE=goodwill_db_test psql -X -f tests/database/test_database.sql
```

The second migration run checks safe reapplication; tests verify seeds, both spec
money examples, multiline totals, discounts/refunds, refresh behavior, empty
orders, time offsets, numeric precision, source-scoped uniqueness, sparse buyers,
relisting, FK enforcement, invalid money/quantity/date values, and required money.
Tests roll back rows and refreshed view contents, but identity sequences may
advance. A failed assertion causes `psql` to exit nonzero and rolls back the test
transaction on disconnect. No external test framework is needed.

## Remaining integration decisions

Parsing, raw-file archiving, and normalization are separate work. These CSVs are
not loaded into domain tables by the migrations: missing required facts need
enrichment, not invented zeros. Synthetic test transactions are SQL-only and
rolled back; existing CSVs remain unchanged.

The spec's unresolved decisions still apply: global SKU uniqueness, order status
vocabulary, review scales, first/latest batch provenance, duplicate-file policy,
line-item repeat-import identity, refund components, and dashboard metric/cohort
definitions. In particular, header upserts do not make line imports idempotent.
No automatic source timezone mapping or reporting timezone has been selected.
