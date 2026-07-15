# data design

## database

we'll use a relational database (Azure SQL). the concrete engine is only known to the BFF data access layer — everything else is isolated from this choice via dependency injection.

known considerations:

* name/characteristic search will require either a separate search index (e.g. Azure Cognitive Search) or query-time filtering — plan for this as search scope grows beyond name
* soundex/phonetic search is not supported natively in most relational databases — will need application-level handling or a dedicated search index

## data import

### from api

```text
    ┌────────────┐
    │ Source API │
    └─────┬──────┘
          │
          ▼
    ┌───────────┐
    │ Extractor │
    └─────┬─────┘
          │
          ▼
    ┌───────────┐
    │ Raw Files │
    └─────┬─────┘
          │
          ▼
 ┌──────────────────┐            ┌──────────────────┐
 │     Importer     │◄───────────│  Internal Model  │
 │  (map + compare) │            │  (current data)  │
 └────────┬─────────┘            └────────┬─────────┘
          │ changed rows only             │
          │                               │
 ┌────────▼─────────┐                     │
 │  Internal Model  │              ┌──────┴──────┐
 │   (changeset)    │              │  Database   │
 └────────┬─────────┘              └──────▲──────┘
          │                               │
          ▼                               │
 ┌──────────────────┐                     │
 │      Loader      │─────────────────────┘
 └──────────────────┘
```

* The data is extracted from the external system using **extractors**
* the extracted data is stored in a temporary **raw** input location; once processed, files are moved to an **archive** location (retention/cleanup policy TBD)
* the data is mapped / transformed to an **internal data** model using **importers** (mappers). During this step, the importer compares the incoming data against the current state and filters out unchanged records — this is the primary change detection point.
  * this is especially important because some source APIs offer no incremental extraction; we are forced to bulk-extract everything on each run
  * by detecting changes during mapping, only a small diff of actually changed rows reaches the database
* the filtered changeset is then upserted into the database

### data entry via the UI

* the app should talk to a backend api, never directly to the database/storage

### initial load

* the "private" data which users should be able to update, will be updated normally via the UI profile page.
* but to support initial load or bulk scenarios, we should also be able to load this using json files following 
  the same method as the "from api" data feeds

## data ownership & model

data is split by source and ownership:

* **corporate data** — one table per source system (e.g. `odoo`, `whoz`), written exclusively by the import pipeline. Read-only from the application's perspective; the BFF never exposes write endpoints for these tables.
* **personal data** — a single table for user-managed profile data, writable through the BFF by the owning user.

the BFF composes a person's full profile by joining across these tables at read time.

## data retrieval

the web application should never talk to the data layer directly, instead we'll build a BFF (Backend for Frontend) API.
