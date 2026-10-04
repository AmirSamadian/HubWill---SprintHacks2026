# Product Context

## Project

SprintHack@ND 2026 — Goodwill Michiana

This repository contains our team's implementation for the Goodwill Michiana
reverse-pitch challenge.

The project is being developed by a three-person team during a hackathon.
Implementation decisions should therefore prioritize:

- a coherent end-to-end working system
- clear business value
- demonstrability
- reliability
- understandable architecture
- realistic scope

over attempting to implement every possible feature in the original challenge.

---

## Core Problem

Goodwill Michiana receives operational and transaction information from
multiple selling channels and source systems.

Those sources may produce information in different formats and structures,
making it difficult to consistently analyze the business across channels.

Our project focuses on building a data pipeline and application architecture
that converts source-specific marketplace information into a consistent,
queryable representation that can support business analysis and dashboards.

---

## Product Goal

Create a system that can:

1. ingest source files from multiple marketplace/source systems
2. preserve the original source information
3. normalize relevant information into a common data model
4. store normalized information in a relational database
5. calculate required business metrics and rules in the backend
6. expose useful information through daily and monthly dashboards

The database becomes the source of truth for normalized application data.

---

## Source Data

Goodwill did not provide the team with production datasets.

We will therefore create and use synthetic but realistic source data based on
the information available from the challenge and representative marketplace
exports.

Source files may differ by marketplace.

Current examples include:

- Amazon
- eBay
- ShopGoodwill

The architecture should allow additional source types to be supported without
requiring the entire system to be redesigned.

---

## Hackathon Scope

Our implementation focuses on:

- source-file ingestion
- raw/source preservation
- data normalization and enrichment
- relational database storage
- backend business-rule computation
- daily dashboard
- monthly dashboard

We want to demonstrate the complete path from source information to useful
business information.

---

## Explicitly Out of Scope

The original challenge contains accounting and Business Central-related
requirements for which the team does not have enough implementation detail.

We are intentionally NOT implementing:

- Microsoft Business Central integration
- Business Central APIs
- journal-entry generation
- AR invoice generation
- accounting-close infrastructure
- automated posting into Business Central
- the complete month-end-close workflow

These may be described as future integration opportunities, but they should not
consume implementation time unless the team explicitly changes scope.

---

## Product Principle

A smaller system that works coherently from ingestion through dashboard is more
valuable for this hackathon than a large system containing partially
implemented or speculative integrations.

When uncertain whether to implement additional functionality, prefer the
smallest feature set that strengthens the core end-to-end demonstration.