import os

AUTH_MODE = os.getenv("WHOISWHO_AUTH_MODE", "entra").lower()

SECRET_KEY = os.getenv(
    "WHOISWHO_SECRET_KEY",
    "whoiswho-dev-secret" if AUTH_MODE == "mock" else None,
)

ENTRA_TENANT_ID = os.getenv("WHOISWHO_ENTRA_TENANT_ID")
ENTRA_CLIENT_ID = os.getenv("WHOISWHO_ENTRA_CLIENT_ID")
ENTRA_CLIENT_SECRET = os.getenv("WHOISWHO_ENTRA_CLIENT_SECRET")
ENTRA_REDIRECT_URI = os.getenv("WHOISWHO_ENTRA_REDIRECT_URI")

ENTRA_ALLOWED_GROUPS = [
    group_id.strip()
    for group_id in os.getenv("WHOISWHO_ENTRA_ALLOWED_GROUPS", "").split(",")
    if group_id.strip()
]


def require_entra_config():
    missing = [
        name
        for name, value in (
            ("WHOISWHO_ENTRA_TENANT_ID", ENTRA_TENANT_ID),
            ("WHOISWHO_ENTRA_CLIENT_ID", ENTRA_CLIENT_ID),
            ("WHOISWHO_ENTRA_CLIENT_SECRET", ENTRA_CLIENT_SECRET),
            ("WHOISWHO_ENTRA_REDIRECT_URI", ENTRA_REDIRECT_URI),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required Entra ID configuration: " + ", ".join(missing)
        )
