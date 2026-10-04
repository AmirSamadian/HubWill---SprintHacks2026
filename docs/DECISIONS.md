# Project Decisions

This file records product, architecture, scope, and implementation decisions
that have already been made.

The purpose is to prevent developers and AI agents from repeatedly reopening
questions that the team has already resolved.

If a future implementation decision conflicts with one of these accepted
decisions, stop and surface the conflict rather than silently changing the
project direction.

---

## D001 — Database Is the Source of Truth

**Status:** Accepted

After ingestion and normalization, the relational database is the application's
source of truth. The ingestion stage of the project will try to fit the data to the database structure. 

The backend and dashboards should generally operate on normalized database data
rather than repeatedly interpreting marketplace source files.

### Reason

The project integrates multiple source systems with different schemas and file
formats. A normalized relational representation gives the rest of the system a
consistent interface.

---

## D002 — Preserve Raw Source Data

**Status:** Accepted

Original source files should be preserved when they are ingested.

### Reason

Preserving raw input provides:

- traceability
- reproducibility
- debugging capability
- the ability to re-run normalization if transformation logic changes

---

## D003 — Source-Specific Inputs Normalize Into One Common Schema

**Status:** Accepted

Amazon, eBay, ShopGoodwill, and future supported sources may have different
input formats and parsing logic.

They should NOT each have separate application database schemas.

All supported sources should ultimately normalize into one common relational
model.

---

## D004 — Synthetic / Representative Input Data

**Status:** Accepted

Goodwill did not provide production datasets for the hackathon.

The team will create realistic synthetic or representative source files and
organize them by source/company.

Current examples include:

- Amazon
- eBay
- ShopGoodwill

The synthetic files should remain realistic enough to demonstrate the actual
ingestion, normalization, database, backend, and dashboard workflow.

---

## D005 — Scope Ends At Dashboards

**Status:** Accepted

The implemented product flow is:

Source data/files
→ ingest + archive
→ normalize / enrich
→ relational database
→ backend business-rule computations
→ daily dashboard + monthly dashboard 

The team is prioritizing a complete, coherent implementation of this path.
Other dashboards may be added in the future.

---

## D006 — Business Central / Full Month-End Close Is Out of Scope

**Status:** Accepted

The project will NOT implement:

- Microsoft Business Central APIs or integration
- Business Central export infrastructure
- journal-entry generation
- AR invoice generation
- automated accounting posting
- accounting-close infrastructure
- full month-end-close automation
- reconciliation against Business Central

### Reason

Those parts of the original challenge contain too many unknown implementation
details and assumptions for the hackathon.

They may be discussed as future extensions, but should not consume
implementation time unless the team explicitly changes scope.

---

## D007 — Dashboard Analytics Are Not The Same As Month-End Close

**Status:** Accepted

The daily and monthly dashboards present calculated business information from
the normalized data.

Month-end close is a separate accounting workflow that may consume some of
those same underlying calculations but includes additional accounting tasks,
mappings, reconciliation, journal/invoice creation, and posting. Those calculations would've required knowing their business accounting workflow which we didn't get too much info on. 

The dashboard therefore remains in scope even though month-end close is not.

---

## D008 — Business Calculations Live In The Backend

**Status:** Accepted

Derived business metrics and business-rule calculations should generally be
computed by the backend rather than hard-coded independently in frontend
dashboard components.

The frontend's primary responsibility is presentation.

---

## D009 — Derived Metrics Should Generally Not Be Stored As Base Data

**Status:** Accepted

Metrics that can be reliably derived from normalized database fields should
generally be calculated rather than stored redundantly as independent source
fields.

Materialized views or other performance-oriented derived structures may be used
when appropriate, but they should remain derived from source-of-truth tables.

---

## D010 — Product, Listing, And Sale Are Distinct Concepts

**Status:** Accepted

The database distinguishes:

- `product` — the underlying physical item
- `listing` — an attempt to sell that product on a marketplace
- `order_item` — the actual sale of an item as part of an order

A product may therefore exist independently of a listing, and a listing does not
automatically imply a completed sale.

---

## D011 — Core Database Entity Direction

**Status:** Accepted

The agreed relational model currently centers around:

- `source`
- `ingestion_batch`
- `category`
- `product`
- `listing`
- `customer`
- `sales_order`
- `order_item`
- optional `review`

The detailed definitions, relationships, fields, constraints, and mappings are
owned by `docs/DATABASE_SPEC.md`.

`DECISIONS.md` should not replace the detailed database specification. IMPORTANT. 

---

## D012 — External IDs Are Scoped By Source

**Status:** Accepted

Marketplace-provided IDs should not be assumed globally unique.

External identifiers should be interpreted in combination with their source /
marketplace.

---

## D013 — Customer Data May Be Sparse

**Status:** Accepted

Customer-related fields should allow missing values where a marketplace does
not provide customer information.

Current synthetic/source assumptions include customer information being
available from eBay while other sources may not provide equivalent fields.

The common schema should support this without requiring fake values.

---

## D014 — Listing Statuses

**Status:** Accepted

The current listing-status model includes:

- `ACTIVE`
- `SOLD`
- `ENDED_UNSOLD`
- `CANCELLED`

The detailed database specification controls exact implementation.

---

## D015 — Revenue Calculation Direction

**Status:** Accepted

Revenue-related calculations should be derived from normalized transaction
data rather than stored as opaque source totals.

Current agreed direction includes:

- taxes are excluded from sales revenue
- marketplace / transaction fees reduce revenue
- buyer-paid shipping and actual shipping cost are distinct concepts
- refunds are represented as positive refund amounts and reduce calculated
  revenue

Exact formulas should be documented in the database/backend specifications
before implementation.

---

## D016 — Productivity / Labor KPIs Are Out of Current Scope

**Status:** Accepted

The current project does not implement productivity/listing KPIs such as:

- revenue per labor hour
- profit per labor hour
- related labor-productivity metrics

Do not add these automatically merely because they appear in broader challenge
material.

---

## D017 — Git Branch Strategy

**Status:** Accepted

The current Git hierarchy is:

main
└── dev
    ├── feature/database
    ├── feature/backend
    └── feature/frontend

Feature branches are created from `dev`.

Feature work is merged into `dev`.

`main` represents the stable/demoable version.

A separate `feature/data-ingestion` branch may be created later when that work
begins.

---

## D018 — Keep Major Layers Separated

**Status:** Accepted

The project separates responsibility between:

- ingestion
- normalization
- database
- backend/business logic
- frontend/dashboard

This separation is intended to reduce coupling and let team members work in
parallel.

In particular:

- source-specific parsing belongs near ingestion/normalization
- normalized persistent state belongs in the database
- business calculations belong in the backend
- visualization belongs in the frontend