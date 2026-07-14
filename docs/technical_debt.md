# Technical Debt

Deliberate trade-offs and known gaps, tracked so they aren't rediscovered by accident. Each entry says what the improvement would involve and why it'd be worth doing — not a commitment to do it on any particular timeline.

## SSO (Entra ID)

See `docs/sso.md` for how the current implementation works. The items below are the improvements considered and consciously deferred while building it.

### Microsoft Graph fallback for group overage

**What it entails:** Entra ID only includes the `groups` claim in the token when the user belongs to 200 or fewer groups; above that, the token carries an overage marker instead (`_claim_names`), and the app currently rejects the login outright rather than resolving membership. Closing this means calling Microsoft Graph (`/me/transitiveMemberOf` or similar) with the access token when overage is detected, and checking the allowed groups against that result instead.

**Benefit:** Users who happen to belong to many groups (common for people in broad distribution/security groups unrelated to this app) aren't locked out. Without this, group-based authorization silently stops working for a subset of users depending on their org's group membership, not on anything this app controls.

### Front-channel or back-channel single logout (SLO)

**What it entails:** Register a `frontchannel_logout_uri` (or the more robust server-to-server `backchannel_logout_uri`) in the Entra app registration, and add a route that clears the local WhoIsWho session when Entra notifies it. Today, logout only clears WhoIsWho's own session and ends the browser's central Entra session (RP-initiated logout) — it doesn't propagate to other already-open Entra-connected app sessions in either direction.

**Benefit:** Logging out of one Entra-connected app would also log the user out of WhoIsWho, and vice versa, closing the window where a different tab stays authenticated after the user believes they've logged out everywhere. Lower priority than it sounds, though — short session lifetimes address the same underlying risk more directly (see below).

### Certificate-based client credential instead of a client secret

**What it entails:** Swap `WHOISWHO_ENTRA_CLIENT_SECRET` for a certificate (thumbprint + private key) and update `EntraProvider._msal_app()` to use MSAL's certificate-credential support instead of a plain secret string.

**Benefit:** Certificates avoid the manual/periodic rotation burden of a client secret and are Microsoft's currently recommended credential type for confidential clients. Worth doing sooner rather than later if the org's other Entra-connected apps already use certificates, so this one doesn't diverge from the established pattern.

### Secret management / Key Vault integration

**What it entails:** `WHOISWHO_SECRET_KEY` and `WHOISWHO_ENTRA_CLIENT_SECRET` are currently read from plain environment variables with no central store or rotation policy. Wiring the app to Azure Key Vault (ideally via managed identity, so no separate credential is needed just to fetch the credentials) would replace that.

**Benefit:** Removes long-lived plaintext secrets from deployment configuration, enables rotation without a redeploy, and reduces the blast radius if the hosting environment's configuration is ever exposed.

### No live end-to-end verification against a real Entra ID tenant

**What it entails:** The automated test suite (`test_app.py`) fakes the MSAL client entirely (`_FakeMsalApp`) so `EntraProvider`'s logic can be tested without a tenant — but that means the real redirect → consent → token exchange → signature validation against Microsoft has only ever been designed, never actually run. A manual pass against a real app registration is still needed before relying on this in production.

**Benefit:** Catches integration-only failure modes unit tests structurally can't reach — redirect URI mismatches, missing admin consent, real claim shapes, clock skew — before real users hit them.

### Session/token lifetime not explicitly tuned

**What it entails:** The Flask session cookie currently relies on framework defaults rather than an explicit, deliberately chosen `PERMANENT_SESSION_LIFETIME` or re-authentication trigger.

**Benefit:** A shorter, deliberately-set session lifetime shrinks the window a stolen or leaked session cookie stays useful — a more direct control on the same risk that motivated the SLO idea above, and cheaper to implement.

### Flat allow/deny group authorization, no differentiated roles

**What it entails:** `WHOISWHO_ENTRA_ALLOWED_GROUPS` currently gates access as all-or-nothing. If the app ever needs tiered permissions (e.g. an admin view), that would mean either multiple group lists mapped to permission levels, or switching from raw groups to Entra app roles.

**Benefit:** None needed today — this is here so that if a permissions tier is ever requested, it's a known, already-scoped decision rather than a surprise refactor. Not worth building ahead of an actual need.
