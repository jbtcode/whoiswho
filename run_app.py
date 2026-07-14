import os
import sys
from pathlib import Path

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent / "src_frontend"
    os.chdir(base_dir)
    os.environ.setdefault("FLASK_APP", "app.py")
    sys.path.insert(0, str(base_dir))
    os.execv(sys.executable, [sys.executable, "-m", "flask", "run", "--host", "127.0.0.1", "--port", "5000"])
