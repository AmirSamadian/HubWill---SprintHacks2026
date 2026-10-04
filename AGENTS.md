# Repository Guidelines

## Project Overview

This repository contains the SprintHack@ND 2026 Goodwill Michiana project.

This is a hackathon project with intentionally limited scope. Do not expand
the implementation beyond the architecture and product requirements documented
in this repository unless explicitly instructed.

Before making significant implementation or architectural changes, read:

- `docs/PRODUCT_CONTEXT.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`

When working on the database, also read:

- `docs/DATABASE_SPEC.md`

These documents are authoritative for the project scope and design.

---

## Project Structure

The repository currently contains documentation and synthetic marketplace
data fixtures.

Current source-data directories include:

- `test-data/amazon-data/`
- `test-data/ebay-data/`
- `test-data/goodwill-data/`

Application modules will be added as the project develops.

Expected high-level organization:

- `docs/` — product, architecture, and implementation decisions
- `test-data/` — synthetic/source-like marketplace input files
- `backend/` — backend application and business-rule computation
- `frontend/` — dashboard application
- `tests/` — automated tests

Do not reorganize major project directories without explicit approval.

---

## Architecture and Scope

The intended system flow is:

Source data/files
→ ingest + archive
→ normalize / enrich
→ relational database
→ backend business-rule computations
→ daily dashboard + monthly dashboard

The relational database is the system's source of truth after ingestion and
normalization.

The project intentionally does NOT implement the complete Business Central or
month-end accounting workflow.

Unless explicitly requested, do not implement:

- Business Central APIs or integration
- journal-entry generation
- AR invoice generation
- accounting-close infrastructure
- Business Central export infrastructure

Do not infer missing accounting requirements and implement them automatically.

---

## Source Data

Goodwill did not provide production datasets for the hackathon.

The repository therefore contains synthetic or representative source files
modeled after marketplace/export formats.

Source-specific input formats may differ.

Ingestion should preserve the original source data while transforming relevant
information into the project's normalized relational representation.

Do not manually modify fixture contents merely to make a parser succeed unless
explicitly instructed.

Preserve existing source filenames, schemas, metadata, column ordering, and
formatting where practical.

---

## Git Workflow

The team uses the following branch hierarchy:

main
└── dev
    ├── feature/database
    ├── feature/backend
    └── feature/frontend

Additional feature branches may be created from `dev` as needed.

Rules:

- Never commit implementation work directly to `main`.
- Feature work should happen on a feature branch created from `dev`.
- Do not merge into `dev` or `main` unless explicitly instructed.
- Do not push, commit, rebase, reset, stash, or switch branches unless
  explicitly instructed.
- Do not force-push shared branches.
- Keep changes focused on the requested feature.
- Do not refactor unrelated code while implementing a task.

Git operations are normally controlled by the human developer.

---

## Before Editing Code

Before implementing a significant change:

1. Read the relevant project documentation.
2. Inspect the existing implementation.
3. Identify which files should change.
4. Prefer the smallest reasonable implementation.
5. Ask before making a major architectural change or adding substantial scope.

Do not assume a framework, package, language, database, or deployment platform
unless it is already configured or specified in project documentation.

---

## Dependencies

Before adding a new dependency:

1. Determine whether the existing stack already provides the needed capability.
2. Prefer common, well-maintained dependencies.
3. Explain why the dependency is needed if it meaningfully changes the stack.

When introducing executable code, include reproducible dependency declarations
and update setup instructions.

---

## Testing and Validation

No testing command should be assumed until one is configured.

When implementation code is introduced:

- add appropriate automated tests for important transformations and business logic
- run relevant tests after modifying code
- test edge cases for parsers and normalization
- test missing or malformed values where appropriate
- report tests or validation performed

For Python tests, prefer:

`tests/test_<module>.py`

unless the project later establishes another convention.

---

## Secrets and Configuration

Never commit:

- `.env`
- API keys
- passwords
- tokens
- credentials
- private configuration values

Use environment variables for secrets.

If environment variables are required, maintain an `.env.example` containing
variable names but no real credentials.

Review source files before committing them for accidentally included personal
information or credentials.

---

## Code Quality

Prefer readable and maintainable code over unnecessarily clever implementations.

Unless a project-specific convention later overrides these rules:

- use descriptive names
- keep functions focused
- avoid unnecessary duplication
- avoid premature abstraction
- preserve existing interfaces unless a change is required
- comment decisions or non-obvious behavior rather than obvious syntax

If Python is used:

- use four-space indentation
- use `snake_case` for modules, variables, and functions

Follow configured formatters and linters once they exist.

---

## AI Development Behavior

AI-generated code must remain understandable to the human development team.

Do not generate large unrelated refactors merely to improve style.

For substantial work:

1. understand the existing architecture
2. implement the requested change
3. run relevant validation
4. summarize what changed
5. identify assumptions or unresolved issues

If project documentation conflicts with an inferred implementation choice,
follow the project documentation.

If two project documents appear to conflict, stop and point out the conflict
rather than silently choosing one.

---

## Completion Report

After significant implementation work, briefly report:

- files created or modified
- what was implemented
- tests or validation performed
- important assumptions
- remaining issues or follow-up work

Do not claim something was tested if it was not.