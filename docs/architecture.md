# architecture

## component diagram

```text
                                    ┌──────────────────────────────────────────────────────────────┐
                                    │                   Import Service (internal)                   │
                                    │                                                               │
                                    │  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐  │
                                    │  │  Connector  │      │  Connector  │      │     ...     │  │
                                    │  │    Odoo     │      │    WHOZ     │      │             │  │
                                    │  └──────┬──────┘      └──────┬──────┘      └──────┬──────┘  │
                                    └─────────┼─────────────────────┼─────────────────── ┼─────────┘
                                              │ extract             │ extract             │ extract
                                              ▼                     ▼                     ▼
                                    ┌──────────────────────────────────────────────────────────────┐
                                    │                        Source APIs                            │
                                    │               (Odoo, WHOZ, TeamTailor, ...)                   │
                                    └──────────────────────────────────────────────────────────────┘
                                              │ write raw           │ write raw           │ write raw
                                              ▼                     ▼                     ▼
                                    ┌──────────────────────────────────────────────────────────────┐
                                    │                   File Storage (raw + archive)                │
                                    └──────────────────────────────────┬───────────────────────────┘
                                                                       │ read raw / archive processed
                                                                       ▼
 ┌──────────────┐   HTTP    ┌───────────┐  trigger  ┌─────────────────────────────────────────────┐
 │   Frontend   │──────────►│    BFF    │──────────►│                Import Service               │
 │  (web app)   │◄──────────│    API    │           │                  (above)                    │
 └──────┬───────┘           └─────┬─────┘           └─────────────────────┬───────────────────────┘
        │                         │                                        │
        │ SSO auth                │ read/write                             │ read current data, watermarks
        ▼                         │ (personal data,                        │ write changeset + logs
 ┌──────────────┐                 │  logs, profiles)                       │
 │     SSO      │                 ▼                                        │
 └──────────────┘          ┌─────────────┐                                 │
                            │  Database   │◄────────────────────────────────┘
                            └─────────────┘
```

## tech stack

| component | technology |
|---|---|
| frontend | HTML + vanilla JS + Bootstrap |
| BFF API | .NET |
| import service | Python |
| database | relational database (Azure SQL in production; swappable via DI in the BFF data access layer) |
| file storage | Azure Blob Storage (Azurite for local dev) |
| auth | SSO |
| containerisation | Docker / Docker Compose |
| CI/CD | Azure DevOps |

## BFF API design

### auth
the BFF validates the SSO token itself using ASP.NET Core's built-in JWT/SSO middleware. no API gateway required. the import service trigger endpoint is restricted to admin users.

### access levels
| level | condition | capabilities |
|---|---|---|
| unauthenticated | no token | no access — all endpoints require a valid token |
| authenticated | valid token | read all profiles + edit own personal data |
| admin | valid token + admin flag | read all profiles + edit any profile + trigger imports |

### endpoints

**profiles**
- `GET /profiles` — list of profiles (name, photo, role); supports search filters (initially name only, extensible)
- `GET /profiles/{id}` — full profile for one person (corporate data + personal data, each field tagged with owner)
- `PUT /profiles/{id}/personal` — update personal data for a profile (own profile or admin only)

**import**
- `POST /import/run` — trigger import run (admin only); optional body `{ sources: ["odoo", "whoz"] }` — omit to run all connectors
- `GET /import/status` — last run status per source, read from the log table

## principles

### separation of concerns
each layer has a single responsibility and communicates only through defined interfaces. the frontend never talks to storage directly; the import pipeline never goes through the BFF.

### loose coupling
components (database engine, BFF, frontend, importers) interact through contracts/interfaces, not concrete implementations. any component should be replaceable without requiring changes in the components that depend on it.

### database access boundaries
the BFF and the import service both access the database directly — each maintains its own database access layer. routing import writes through the BFF would couple a backend pipeline to a frontend-facing API, adding unnecessary network hops and forcing the BFF to expose endpoints that have nothing to do with serving the UI.

the principle is: **the frontend never talks to the database directly**. backend components (import service) are not subject to this restriction.

since the BFF (.NET) and import service (Python) cannot share a library, the database schema is the shared contract — each component implements its own access layer against the same schema independently.

### internal data model
the internal data model is defined as a **JSON schema** — a language-agnostic specification that describes the shape of profile data. it is the single source of truth shared across all components. each component (BFF, connectors, importers) builds its own private model layer to convert and interpret data according to this schema. no code is shared — only the specification.

### storage abstraction
the application is decoupled from its storage technology. the BFF's data access layer is the only component that knows which database engine is in use — all other components are unaffected by a database swap. dependency injection is used in the BFF to bind the concrete database implementation, making it straightforward to switch engines (e.g. from Azure SQL to another provider) without touching business logic.

### BFF (Backend for Frontend)
a BFF is a dedicated backend service that exists solely to serve one frontend. rather than the frontend talking directly to databases or internal services, it talks to the BFF — which aggregates, shapes, and secures the data on its behalf.

the web application communicates exclusively with the BFF. benefits:
* **single entry point** — auth, validation, and data ownership rules are enforced in one place
* **frontend stays simple** — data arrives ready to render; no joining or merging in the browser
* **internal services stay hidden** — the database, import service, and source integrations are never directly exposed
* **independently deployable** — the frontend and backend can evolve separately without coupling their release cycles

### data ownership
data is classified by who can write it:
* **corporate data** — written only by the import pipeline, read-only via the BFF. users are expected to maintain corporate data in the source systems (e.g. skills in WHOZ, HR data in Odoo). the app is a read window into corporate data, not a place to maintain it.
* **personal data** — written by the user through the BFF

each field in the profile response carries an **owner** tag (e.g. `odoo`, `whoz`, `personal`) so the frontend knows who controls it. for read-only fields, the UI can use this tag to show the user where to go to update the value (e.g. "Update this field in WHOZ").

### import pipeline
external data flows through a fixed pipeline: extract -> raw storage -> map + change detection -> load. each step is isolated so individual extractors or importers can be added or replaced independently.

### import service
all import logic runs in a single dedicated container — the **import service**. each data source is implemented as a pluggable **connector** (extractor + importer pair) behind a common interface. the service orchestrates connectors independently: a failing connector does not block others.

the import service exposes an HTTP endpoint as its single trigger mechanism. all invocation paths — scheduled runs, admin UI button, local CLI — call this same endpoint. no separate trigger infrastructure is needed.

after each connector run, the service writes a status record (source, timestamp, outcome) to a log table. the BFF exposes this for the admin page; polling on page load is sufficient.

### change detection at the importer
change detection happens in the importer layer, not in the database. the importer compares incoming data to the current state and forwards only changed records to the loader. this applies equally to full and incremental extractions — an incremental feed reduces the volume of incoming data, but the comparison step still runs. the pipeline is identical in both cases; only the input size differs.

### connector interface contract

each connector receives:
* **watermark** — the last successful extraction point for this source (timestamp, cursor, etc.). `null` on the first run. the connector uses this for incremental extraction if the source API supports it; otherwise it ignores it and does a full extract.
* **current data** — the current rows for this source as an opaque collection. the import service fetches these without interpreting them.

each connector returns:
* **changeset** — the records to upsert, derived by comparing incoming data against current data. deletions are out of scope for now and will be handled by a dedicated feature later.
* **new watermark** — the extraction point to persist for the next run. `null` if the source does not support incremental extraction.
* **status** — success or failure, with a message, written by the import service to the log table

the import service is not aware of the internal structure of the current data, the watermark value, or the changeset fields — it passes them through and persists what the connector returns.

### extensibility
new data sources, mini-games, and pages should be addable without modifying existing components. this applies to both the import pipeline (new extractor + importer pair) and the frontend (new page/module).

### deployment topology
the import service exposes its own HTTP endpoint but is treated as internal — in production it is not publicly reachable, only the BFF can call it. locally, it can be called directly (CLI, curl) for development and testing. this design is deployment-topology agnostic: the containers can be co-deployed (e.g. Azure Web App multi-container, Azure Container Apps) or split into separate services without any code changes — only network configuration differs.

### local-first development
the full solution must run locally on containers. this covers development, unit testing, and CI/CD pipelines alike. no component should require a live Azure environment to run or test.
