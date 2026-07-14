# Single Sign-On (Entra ID)

`src_frontend` supports two login modes, selected entirely by configuration — no code changes needed to go from local development to a real deployment.

| Mode | `WHOISWHO_AUTH_MODE` | What it does |
|---|---|---|
| **Mock** | `mock` | The original demo login form (`/login`): any name/email typed in creates a session. Local development only. |
| **Entra ID SSO** | anything else, including unset | Real OAuth 2.0 Authorization Code flow against Microsoft Entra ID via [MSAL](https://learn.microsoft.com/en-us/entra/msal/python/), gated by Entra ID group membership. |

**The default is Entra ID SSO.** If `WHOISWHO_AUTH_MODE` isn't set to exactly `mock`, the app requires real SSO and the mock form is completely unreachable — including via a raw `POST /login`, which returns `404` in that mode. This is deliberate: a missing or misspelled env var must never silently fall back to the fake login. `run_app.py` (the local dev launcher) is the only place that opts into `mock` by default.

## How it works

```
src_frontend/
  config.py     # reads all SSO settings from env vars
  auth.py       # MockProvider / EntraProvider, selected by config.AUTH_MODE
  app.py        # routes delegate to auth.get_provider()
```

- **`config.py`** is the single source of truth for every SSO-related setting. Nothing is hardcoded — tenant ID, client ID, client secret, redirect URI, and the list of allowed groups are all read from `WHOISWHO_*` env vars. `config.require_entra_config()` raises a clear `RuntimeError` naming exactly which variable is missing, the moment a real login is attempted — not silently.
- **`auth.py`** exposes `get_provider()`, which returns either a `MockProvider` or an `EntraProvider` depending on `config.AUTH_MODE`. Both providers populate `session["authenticated"]`, `session["email"]`, and `session["user"]` in the exact same shape, so nothing downstream (`get_user()`, templates, `/home`, `/employees`) needs to know or care which provider is active.
- **`app.py`** routes are provider-agnostic:
  - `GET/POST /login` → `provider.login_get()` / `provider.login_post()`. In Entra mode, `login_get()` redirects straight to Microsoft's login page (no intermediate page), and `login_post()` always `abort(404)`s — this is what closes off the mock bypass.
  - `GET /auth/callback` → `provider.callback()`. Only meaningful for `EntraProvider`; it completes the MSAL auth code flow, validates the token, checks group membership, and creates the session.
  - `GET /logout` → clears the local session and, in Entra mode, redirects through Entra ID's own logout endpoint (`end_session_endpoint`) so the browser's Entra session is cleared too, not just this app's cookie.
- **Session secret**: `app.secret_key` comes from `WHOISWHO_SECRET_KEY`. It's only allowed to fall back to a dev default when `AUTH_MODE=mock`; in Entra mode, a missing secret key raises at app startup rather than reusing a hardcoded value.

### Token validation

MSAL's `acquire_token_by_auth_code_flow` validates the ID token's signature, issuer, audience, and expiry against Entra ID's discovery document before returning claims — this isn't hand-rolled, so there's nothing extra to implement there.

### Group-based authorization

`EntraProvider.callback()` reads the `groups` claim off the validated ID token and checks it against `config.ENTRA_ALLOWED_GROUPS`. If that list is empty, any authenticated user in the tenant is let in; if it's non-empty, the user must belong to at least one listed group or they get a `403`.

**Known limitation — group overage.** Entra ID only includes the `groups` claim directly in the token if the user belongs to 200 or fewer groups. Above that, Entra omits the claim and returns an overage marker (`_claim_names`) instead, requiring a follow-up Microsoft Graph API call to resolve membership. The app detects this case and returns a `403` with an explicit "not yet implemented" message rather than silently letting the user through or failing confusingly — but it does not perform the Graph lookup. If this starts affecting real users, that's the piece to build next (see [Microsoft's guidance on group overage](https://learn.microsoft.com/en-us/troubleshoot/entra/entra-id/app-integration/get-signed-in-users-groups-in-access-token)).

## Setting it up with a real Entra ID app registration and groups

Once you have Entra ID admin access and know which group(s) should have access, this is a configuration task — no code changes.

1. **Register the app in Entra ID** (single-tenant, since this is an internal tool):
   - Entra admin center → *App registrations* → *New registration*.
   - Redirect URI: type **Web**, value pointing at this app's callback route, e.g. `https://<your-deployment-host>/auth/callback` (and a separate registration or an additional redirect URI for any staging/local URL you actually intend to test against).
   - Note the **Application (client) ID** and **Directory (tenant) ID** from the registration's overview page.
2. **Create a client secret**: *Certificates & secrets* → *New client secret*. Copy the secret value immediately — it's only shown once. (A certificate is a more rotation-friendly alternative if that's already the org's pattern for other SSO apps; swapping it in only touches `auth.py`'s `_msal_app()`.)
3. **Configure the groups claim**: *Token configuration* → *Add groups claim* → select the group types relevant to this app (e.g. "Security groups"), and under the optional-claims settings scope it to "groups assigned to the application" rather than all of the user's groups — this keeps the token smaller and avoids pulling in irrelevant group memberships.
4. **Assign the existing Entra ID groups to the app**: *Enterprise applications* → find this app → *Users and groups* → add the group(s) that should be allowed access. This step matters even if you're not using app roles — a user still needs to be assigned to the enterprise application to sign in if assignment is required on the app.
5. **Get the group Object ID(s)**: *Groups* → select the group → copy the **Object ID** (a GUID) — this is what goes into `WHOISWHO_ENTRA_ALLOWED_GROUPS`, not the group's display name.
6. **Fill in the environment configuration** (copy `src_frontend/.env.example` to `.env`, or set these directly in the deployment's environment):

   ```
   WHOISWHO_AUTH_MODE=              # leave unset/anything but "mock" to require real SSO
   WHOISWHO_SECRET_KEY=             # long random value
   WHOISWHO_ENTRA_TENANT_ID=        # Directory (tenant) ID
   WHOISWHO_ENTRA_CLIENT_ID=        # Application (client) ID
   WHOISWHO_ENTRA_CLIENT_SECRET=    # the client secret value
   WHOISWHO_ENTRA_REDIRECT_URI=     # must match the app registration exactly
   WHOISWHO_ENTRA_ALLOWED_GROUPS=   # comma-separated group Object IDs
   ```

7. **Test end to end**: hit `/login` on the deployed app, confirm it redirects to Microsoft, log in as a user who *is* in an allowed group and confirm access, then as a user who *isn't* and confirm a `403`.

## Troubleshooting

Work through these in order — they cover the large majority of real-world issues:

1. **`AADSTS50011` (redirect URI mismatch)** — the registered redirect URI and `WHOISWHO_ENTRA_REDIRECT_URI` must match *exactly*: scheme, host, path, and trailing slash. This is the most common failure when promoting between environments.
2. **`AADSTS700016`** — wrong client ID or the app isn't registered in the tenant you're authenticating against; double check `WHOISWHO_ENTRA_TENANT_ID`.
3. **`AADSTS65001`** — the app's requested scopes haven't been consented to; an admin may need to grant consent in the app registration.
4. **User gets a 403 after logging in successfully** — either they're not a member of any group listed in `WHOISWHO_ENTRA_ALLOWED_GROUPS`, or they've hit the group-overage case above. Check the ID token's claims (e.g. via [jwt.io](https://jwt.io)) to tell which.
5. **App won't start / raises `RuntimeError` on import** — `config.require_entra_config()` or the secret-key check is telling you exactly which `WHOISWHO_*` variable is missing. This is intentional fail-closed behavior, not a bug.
6. **Local dev suddenly requires real SSO** — check that `WHOISWHO_AUTH_MODE` is actually `mock`, and that you're launching via `run_app.py` (which sets that default) rather than `flask run` directly.

## Testing

`src_frontend/test_app.py` covers the SSO logic without needing a real Entra ID tenant. Run it with:

```bash
pytest src_frontend/test_app.py -q
```

### The mock-mode tests

`test_profile_update_is_persisted_to_json` and `test_profile_picture_upload_uses_web_safe_avatar_path` (pre-existing, not SSO-specific) log in via `MockProvider` and exercise the app's ordinary request/response behavior. They matter here only in that they confirm `WHOISWHO_AUTH_MODE=mock` still works end to end after the SSO changes.

### Faking Entra ID: `_FakeMsalApp` and `_entra_test_client`

The Entra flow can't be tested against the real service in CI, so the tests fake the one thing that actually talks to Microsoft: the MSAL client object.

- **`_FakeMsalApp`** stands in for `msal.ConfidentialClientApplication`. It implements just the two methods `EntraProvider` calls:
  - `initiate_auth_code_flow(...)` — always returns a fixed fake `auth_uri`, so `EntraProvider.login_get()` has something to redirect to.
  - `acquire_token_by_auth_code_flow(...)` — returns whatever `token_result` dict the test passes in. This is the knob each test uses to simulate a specific Entra response: a successful token with chosen claims, an `error` response, or claims carrying the group-overage marker.
- **`_entra_test_client(tmp_path, monkeypatch, token_result, allowed_groups="")`** is the shared setup every Entra test calls:
  1. Sets `WHOISWHO_AUTH_MODE=entra` (so `auth.get_provider()` returns `EntraProvider`), a throwaway `WHOISWHO_SECRET_KEY`, an isolated `WHOISWHO_DATA_DIR`, and `WHOISWHO_ENTRA_ALLOWED_GROUPS`.
  2. Reloads `config`, `auth`, `storage`, and `app` — necessary because these modules read their env-var-driven settings at import time; reusing the previously-imported modules from an earlier test would keep stale config.
  3. Monkeypatches `EntraProvider._msal_app` to return a `_FakeMsalApp(token_result)` instead of constructing a real MSAL client — this is what removes the Entra ID dependency entirely, while every other line of `EntraProvider.callback()` (claims parsing, group check, overage check, session/user creation) still runs for real.
  4. Disables CSRF for the test client, matching the other tests (CSRF is unrelated to SSO — it protects form POSTs in general — but the test client needs it off since it doesn't send a token).

Each test then drives a real request through `EntraProvider`, only the network call to Microsoft is substituted:

| Test | `token_result` simulates | Verifies |
|---|---|---|
| `test_entra_mode_never_accepts_the_mock_login_post` | n/a | `POST /login` is `404` in Entra mode — the bypass stays closed |
| `test_entra_mode_login_get_redirects_straight_to_microsoft` | n/a | `GET /login` redirects to the (fake) Microsoft authorize URL |
| `test_entra_callback_without_a_pending_login_is_rejected` | n/a | Hitting `/auth/callback` without a prior `/login` (no `session["auth_flow"]`) is `400` |
| `test_entra_callback_rejects_a_failed_token_exchange` | MSAL `error`/`error_description` | A failed code exchange is `401`, not a crash |
| `test_entra_callback_rejects_group_overage` | `_claim_names` overage marker, no `groups` | The >200-group case is caught and rejected (`403`) instead of silently admitting the user |
| `test_entra_callback_rejects_user_outside_allowed_group` | valid claims, `groups` not in the allow-list | Group-based authorization actually denies (`403`) |
| `test_entra_callback_grants_access_and_creates_session_for_allowed_group` | valid claims, `groups` in the allow-list | The success path: session is created, `/home` becomes reachable, the user row is persisted with the claims' name |
| `test_entra_callback_allows_any_tenant_user_when_no_groups_are_configured` | valid claims, no `groups` claim needed | An empty `WHOISWHO_ENTRA_ALLOWED_GROUPS` allows any authenticated tenant user, as documented above |

What this suite does **not** cover — because it can't, without a real tenant — is whether MSAL's own signature/issuer/audience/expiry validation is wired correctly, or whether a real redirect URI/consent/token exchange actually succeeds against Microsoft. Manual verification against a real Entra ID app registration is still required at least once (see the setup steps above).

## What's intentionally not implemented

- **Microsoft Graph fallback for group overage** (>200 groups) — see above.
- **Full front-channel single logout propagation** to other Entra-connected apps — logout redirects through Entra's own logout endpoint, which clears the browser's Entra session, but doesn't actively notify other applications' sessions.
- **Certificate-based client credentials** — currently a client secret only; swapping to a certificate is a small, isolated change in `auth.py`'s `_msal_app()` if the org standardizes on certs.
