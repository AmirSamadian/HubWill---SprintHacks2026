# System Architecture

## Overview

The system follows this high-level architecture:

Source data/files
→ ingest + archive
→ normalize / enrich
→ relational database
→ backend business-rule computations
→ daily dashboard + monthly dashboard

The database is the source of truth for normalized application data.

---

## Architecture Diagram

```text
┌─────────────────────────┐
│      SOURCE FILES       │
│ Amazon / eBay /         │
│ ShopGoodwill / others   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│    INGEST + ARCHIVE     │
│                         │
│ Read source files       │
│ Preserve raw source     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   NORMALIZE / ENRICH    │
│                         │
│ Source-specific format  │
│          ↓              │
│ Common representation   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  RELATIONAL DATABASE    │
│                         │
│ Source of truth         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│        BACKEND          │
│                         │
│ Business rules          │
│ Aggregations            │
│ Dashboard computations  │
└──────────┬───────┬──────┘
           │       │
           ▼       ▼
    ┌───────────┐ ┌───────────┐
    │   DAILY   │ │  MONTHLY  │
    │ DASHBOARD │ │ DASHBOARD │
    └───────────┘ └───────────┘