import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault("WHOISWHO_DATA_DIR", str(BASE_DIR / "data"))
os.environ.setdefault("WHOISWHO_AVATAR_DIR", str(BASE_DIR / "data" / "avatars"))

from whoiswho import create_app

app = create_app()
