import os
import sys
from pathlib import Path

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    os.chdir(base_dir)
    os.environ.setdefault("FLASK_APP", "app.py")
    os.environ.setdefault("WHOISWHO_AUTH_MODE", "mock")
    os.execv(sys.executable, [sys.executable, "-m", "flask", "run", "--host", "127.0.0.1", "--port", "5000"])
