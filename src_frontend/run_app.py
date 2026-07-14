import os
import sys
from pathlib import Path

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    os.chdir(base_dir)
    os.environ.setdefault("FLASK_APP", "wsgi.py")
    os.environ.setdefault("WHOISWHO_AUTH_MODE", "mock")
    os.environ.setdefault("WHOISWHO_DATA_DIR", str(base_dir / "data"))
    os.environ.setdefault("WHOISWHO_AVATAR_DIR", str(base_dir / "data" / "avatars"))
    sys.path.insert(0, str(base_dir))
    os.execv(sys.executable, [sys.executable, "-m", "flask", "run", "--host", "127.0.0.1", "--port", "5000"])
