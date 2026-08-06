# Changelog

This changelog summarizes major implementation milestones visible in the current repository and Git history. It does not replace commit history.

## v3.1 — Documentation sprint

### Documentation

- Added a complete current-state documentation set under `docs/`.
- Cataloged all 28 live SQLite tables, relationships, and indexes.
- Documented production workflow, Notion synchronization, Command Center, shipment architecture, channel metadata gaps, and roadmap.

## v3.0 workflow checkpoint — 2026-08-06

Tag: `v3.0-workflow-checkpoint`

### Major milestones

- Stabilized the operator workflow from marketplace order import through shipment registration.
- Added a separate ERP Command Center while preserving the existing Dashboard and feature pages.
- Created a verified source checkpoint and excluded runtime artifacts from version control.

### Workflow improvements

- Imported orders automatically run existing product-mapping logic.
- Mapping states distinguish exact matches, ambiguous matches, and unmatched products.
- Purchase generation is limited to mapping-complete orders.
- Purchase work is grouped by supplier and quantities are carried into purchase records/exports.
- Shipment registration updates the ERP order to `배송중`.

### Shipment improvements

- Added supplier-returned Excel import with total, registered, skipped, and error counts.
- Added supplier-specific header/column mappings stored by supplier ID.
- Added full-row preview before registration.
- Preserved tracking numbers as text and safely skipped blank, invalid, and duplicate rows.
- Kept legacy shipment parsers/import behavior available.
- Added safe Coupang API skip for Excel orders missing shipment box, order, or vendor item identifiers.
- Prevented skipped Excel orders from inflating Coupang API failure counts.

### Command Center

- Added daily workflow KPIs, actions, Exception Center, and Activity Log.
- Limited activity logging to actions initiated from the Command Center.
- Disabled channel shipment export as “준비 중”.
- Removed startup dependency on the optional legacy automation runner.

### Bug fixes

- Corrected Product Management imports and constructor arguments to use the existing `NotionProductSyncService`.
- Connected full product synchronization to the existing `sync_products()` method.
- Disabled unsupported single-product Notion synchronization rather than routing it incorrectly.
- Prevented Command Center startup from importing the missing legacy `src.excel_reader` dependency.
- Preserved local shipment saves and `배송중` state when marketplace API metadata is unavailable.

### Repository hygiene

- Added runtime-only ignore rules for bytecode, databases, output, backups, logs, Microsoft runtime artifacts, `.env`, and temporary Excel files.
- Kept source-controlled Excel templates and sample workbooks trackable.

## Earlier workflow commits

- `636dec5` — required fully mapped orders for purchases.
- `a09f0f3` — initialized shipment service lazily.
- `e12a0cd` — added shipment handoff workflow coverage.
- `f1d50f5` — exposed shipment workflow through the CLI.
- `44524ea` — added shipment registration step.
- `a763ddd` — Bisun ERP v2.8 baseline.
