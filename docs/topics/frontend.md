# Frontend architecture

WhoIsWho's frontend is a server-rendered Flask app (Jinja2 templates + Bootstrap 5) with one
island of client-side JavaScript: the mini-games on the `/game` page. There is no SPA, no
build step, and no separate JS frontend — everything under `src_frontend/` is one deployable.

## Running it locally

```
python run_app.py
```

This sets `WHOISWHO_AUTH_MODE=mock` (fake local login, see [sso.md](sso.md)) and launches
`flask run` against `wsgi.py`. There is no `app.py` anymore — `wsgi.py` is the entrypoint,
both for local dev (`run_app.py`) and for a real WSGI server in production.

## Package layout

```
src_frontend/
  wsgi.py                  entrypoint: from whoiswho import create_app; app = create_app()
  run_app.py                dev launcher (sets mock auth + data dir defaults, execs flask run)
  whoiswho/                 the actual application package
    __init__.py              create_app() factory — config validation, CSRF, blueprint registration
    config.py                env var reading (AUTH_MODE, SECRET_KEY, Entra ID settings)
    storage.py                JSON-file "table storage" standing in for Azure Table Storage
    avatar_storage.py         profile picture upload (local disk today, Azure Blob stub for later)
    auth.py                   MockProvider / EntraProvider (see sso.md)
    users.py                  get_user(), _user_from_row(), the login_required decorator
    seed.py                   demo data seeding (DEFAULT_EMPLOYEES, seed_demo_data())
    blueprints/
      auth.py                 /login, /auth/callback, /logout
      profile.py               /, /home (GET+POST), /avatars/<filename>
      employees.py             /employees
      game.py                  /game, /home/visit/game
  templates/
    base.html                 shared layout (navbar, flash messages), all pages extend this
    auth/login.html
    profile/home.html
    employees/employees.html
    game/game.html
  static/
    css/style.css              all custom CSS (rest is Bootstrap 5 via CDN)
    js/games/                  client-side game engine + 4 game modules (see below)
```

Each blueprint owns one feature area and keeps the exact same URL paths the app has always
had — blueprints are purely an endpoint-naming device here (`auth.login`, `profile.home`,
`employees.employees_page`, `game.game_page`, ...), not a URL namespace. `/auth/callback` in
particular is the registered Entra ID redirect URI and must never move.

Templates mirror the blueprint structure 1:1 (`profile/home.html` is rendered by
`blueprints/profile.py`, etc.), with `base.html` shared at the template root since every page
extends it regardless of which blueprint renders it.

## Pages

| Route | Blueprint.endpoint | Template | Auth required |
|---|---|---|---|
| `/` | `profile.index` | — (redirects) | no — redirects to `/home` or `/login` |
| `/login` | `auth.login` | `auth/login.html` | no |
| `/auth/callback` | `auth.callback` | — (redirect only) | no (validates the SSO callback itself) |
| `/home` | `profile.home` / `profile.update_profile` | `profile/home.html` | yes |
| `/avatars/<filename>` | `profile.uploaded_file` | — (serves the image file) | yes |
| `/employees` | `employees.employees_page` | `employees/employees.html` | yes |
| `/game` | `game.game_page` | `game/game.html` | yes |
| `/home/visit/game` | `game.legacy_game_page` | — (redirects to `/game`) | no |
| `/logout` | `auth.logout` | — (clears session, redirects) | no |

Every authenticated route uses the `@login_required` decorator from `whoiswho/users.py`,
which redirects to `auth.login` if `session["authenticated"]` isn't set.

**Profile (`/home`)** — the user's own editable record: name, email, address, hobbies, and a
profile picture upload. `GET` renders the form pre-filled from `get_user()`; `POST`
(`update_profile`) writes the submitted fields back via `storage.upsert_row("Users", ...)`
and, if a file was uploaded, calls `avatar_storage.save(...)` first and stores the returned
path. Both the save location and the serving route (`/avatars/<filename>`) resolve through
the same `avatar_storage.LOCAL_UPLOAD_DIR`, so they can never drift apart even if
`WHOISWHO_AVATAR_DIR` is overridden.

**Employees (`/employees`)** — a read-only table of every seeded employee (name, role,
department), sourced from `storage.load_table("Employees")`.

**Game (`/game`)** — see below, this is the one page with real client-side interactivity.

## The `/game` page and its mini-games

`blueprints/game.py` builds one enriched employee dict per row via `_build_game_employee()`,
adding fields the templates/JS need beyond the raw storage record:

- `summary` — a one-line auto-generated blurb (`_build_employee_summary`)
- `initials` — for the avatar-circle fallback (`_employee_initials`)
- `color_index` — deterministic 0–5 bucket used to pick one of 6 CSS gradient classes
  (`.avatar-color-1` … `.avatar-color-6` in `style.css`)
- `hobbies` / `two_truths` — pulled straight from the seeded employee data (see `seed.py`)

`game/game.html` renders this as a JSON blob (`<script type="application/json"
id="employees-data">{{ employees|tojson }}</script>`) plus four empty "mount" `<div>`s (one
per game, `data-game="..."` identifies which), switched between via Bootstrap nav-pills. All
the actual game logic is client-side — the server never receives a fetch/AJAX call for any of
this, it just hands over the employee data once at page load.

### JS architecture (`static/js/games/`)

- **`engine.js`** — shared utilities used by every game: `shuffle()`, `el()` (a tiny
  `document.createElement` helper), `runQuiz()` (the generic "prompt + N choice buttons"
  flow used by three of the four games — renders a round, scores the pick, shows a
  next-question/see-results control, and supports replay by re-calling the round-builder
  function passed in), and `renderCompletion()` / `renderScorePill()` for the shared
  end-of-round UI.
- **`main.js`** — the bootstrapper. Parses the embedded employee JSON, lazy-`import()`s the
  four game modules, and only calls a game's `register()` — and therefore only initializes
  its mount — the first time its tab is actually shown (`shown.bs.tab`), not eagerly on page
  load.
- **`photo-match.js`** — *Photo Match*: match each colleague's avatar-circle to their name in
  two shuffled columns. Not built on `runQuiz()` (it's pair-matching, not prompt/choice), so it
  has its own click/selection/evaluate state machine directly in the module.
- **`two-truths.js`** — *Two Truths & a Lie*: uses each employee's seeded `two_truths`
  (3 statements, one marked `lie_index`) as a `runQuiz()` round — pick which statement is the
  lie.
- **`hobby-guess.js`** — *Hobby Guess*: shows one employee's hobby emoji and asks which
  colleague they belong to, distractors drawn from the other seeded employees.
- **`guess-department.js`** — *Guess the Department*: shows an employee's `summary` with their
  own name redacted (`redactName`) and asks which department they're in.

Each game module only needs to export a `register(registerGame)` function; `main.js` doesn't
know anything about game internals beyond that contract, so adding a fifth game means adding
one new module + one `import()` + one tab/mount pair in `game.html` — nothing else changes.

## Styling

Bootstrap 5 (via CDN, loaded in `base.html`) provides layout, cards, forms, and the navbar.
`static/css/style.css` is the only custom stylesheet and covers what Bootstrap doesn't:
the gradient avatar circles, the game page's hero/card treatment, the quiz choice buttons
and their correct/incorrect states, the photo-match tiles and their
selected/matched/wrong states, and the 6-color avatar palette used by `color_index`.

## Data flow

Nothing here calls a real database. `storage.py` reads/writes flat JSON files
(`src_frontend/data/users.json`, `employees.json`) through a small
`load_table`/`upsert_row`/`delete_row` API deliberately shaped like Azure Table Storage
(`PartitionKey`/`RowKey` rows), so swapping in the real thing later shouldn't require changing
any calling code. `avatar_storage.py` does the same for uploaded profile pictures (local disk
today, an `AvatarStorage(backend="azure")` stub for later). `seed.py` populates both tables
with demo data (Ada Lovelace, Grace Hopper, Katherine Johnson, Margaret Hamilton, complete
with hobbies and two-truths statements for the game) the first time `create_app()` runs
against an empty data directory.

## Related docs

- [sso.md](sso.md) — authentication (mock login vs. real Entra ID SSO)
- [technical_debt.md](../technical_debt.md) — known gaps and deferred improvements
