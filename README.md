# SprintHack
Project for SprintHack 2026

## Database

PostgreSQL migrations, reference seeds, and setup instructions are in
[`backend/database/`](backend/database/README.md). The schema contract is
[`docs/DATABASE_SPEC.md`](docs/DATABASE_SPEC.md).

With PostgreSQL 17 running and connection settings configured, run from the
repository root:

```sh
createdb goodwill_db
PGDATABASE=goodwill_db psql -X -f backend/database/migrate.sql
```

See the database guide for isolated integration tests, view refreshes, and
remaining normalization decisions. No source-file ingestion is implemented yet.
