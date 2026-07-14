from flask import abort, flash, redirect, render_template, session, url_for

import config
import storage


class MockProvider:
    """Local-dev-only stand-in for real SSO. Never used unless WHOISWHO_AUTH_MODE=mock."""

    def login_get(self):
        return render_template("login.html")

    def login_post(self, req):
        email = req.form.get("email", storage.DEFAULT_USER["email"])
        first_name = req.form.get("first_name", storage.DEFAULT_USER["first_name"])
        last_name = req.form.get("last_name", storage.DEFAULT_USER["last_name"])
        user_row = {
            "PartitionKey": "default",
            "RowKey": email,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "address": "",
            "hobbies": "",
            "role": storage.DEFAULT_USER["role"],
            "avatar": f"{first_name[0].upper()}{last_name[0].upper()}",
        }
        storage.upsert_row("Users", user_row)
        session["authenticated"] = True
        session["email"] = email
        session["user"] = storage.user_from_row(user_row)
        flash("Signed in successfully through SSO", "success")
        return redirect(url_for("home"))

    def callback(self, req):
        abort(404)

    def logout_redirect_url(self):
        return None


class EntraProvider:
    """Real SSO against Entra ID via MSAL. Used whenever WHOISWHO_AUTH_MODE is not 'mock'."""

    def _msal_app(self):
        config.require_entra_config()
        import msal

        authority = f"https://login.microsoftonline.com/{config.ENTRA_TENANT_ID}"
        return msal.ConfidentialClientApplication(
            config.ENTRA_CLIENT_ID,
            client_credential=config.ENTRA_CLIENT_SECRET,
            authority=authority,
        )

    def login_get(self):
        flow = self._msal_app().initiate_auth_code_flow(
            scopes=["User.Read"],
            redirect_uri=config.ENTRA_REDIRECT_URI,
        )
        session["auth_flow"] = flow
        return redirect(flow["auth_uri"])

    def login_post(self, req):
        # The mock form-post flow must never be reachable when real SSO is required.
        abort(404)

    def callback(self, req):
        flow = session.pop("auth_flow", None)
        if not flow:
            abort(400, "No SSO sign-in was in progress.")

        result = self._msal_app().acquire_token_by_auth_code_flow(flow, req.args)
        if "error" in result:
            abort(401, result.get("error_description", result["error"]))

        claims = result.get("id_token_claims", {})

        if "_claim_names" in claims and "groups" in claims.get("_claim_names", {}):
            # Group overage (>200 groups): Entra omits the groups claim and expects a
            # Microsoft Graph call to resolve membership instead. Not implemented here.
            abort(
                403,
                "This account belongs to too many Entra ID groups for the groups claim "
                "to be included in the token. Group-based authorization requires a "
                "Microsoft Graph lookup for this user, which is not yet implemented.",
            )

        groups = set(claims.get("groups", []))
        if config.ENTRA_ALLOWED_GROUPS and not groups & set(config.ENTRA_ALLOWED_GROUPS):
            abort(403, "You are not a member of a group authorized to access this application.")

        email = claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        if not email:
            abort(401, "SSO sign-in did not return a usable identity.")

        first_name = claims.get("given_name", "")
        last_name = claims.get("family_name", "")

        existing = next(
            (row for row in storage.load_table("Users") if row.get("RowKey") == email),
            {},
        )
        user_row = {
            **existing,
            "PartitionKey": "default",
            "RowKey": email,
            "first_name": first_name or existing.get("first_name", storage.DEFAULT_USER["first_name"]),
            "last_name": last_name or existing.get("last_name", storage.DEFAULT_USER["last_name"]),
            "email": email,
            "role": existing.get("role", storage.DEFAULT_USER["role"]),
            "avatar": f"{(first_name or '?')[0].upper()}{(last_name or '?')[0].upper()}",
        }
        storage.upsert_row("Users", user_row)

        session["authenticated"] = True
        session["email"] = email
        session["user"] = storage.user_from_row(user_row)
        flash("Signed in successfully through SSO", "success")
        return redirect(url_for("home"))

    def logout_redirect_url(self):
        if not config.ENTRA_TENANT_ID:
            return None
        return (
            f"https://login.microsoftonline.com/{config.ENTRA_TENANT_ID}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={url_for('login', _external=True)}"
        )


def get_provider():
    if config.AUTH_MODE == "mock":
        return MockProvider()
    return EntraProvider()
