import os
import time
from pathlib import Path
from typing import Optional

from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
LOCAL_UPLOAD_DIR = Path(os.getenv("WHOISWHO_AVATAR_DIR", BASE_DIR / "data" / "avatars"))
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_URL_PREFIX = "avatars"


class AvatarStorage:
    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or os.getenv("WHOISWHO_AVATAR_BACKEND", "local")

    def save(self, file_storage, user_email: str) -> str:
        if self.backend == "azure":
            return self._save_to_azure(file_storage, user_email)
        return self._save_locally(file_storage, user_email)

    def _save_locally(self, file_storage, user_email: str) -> str:
        filename = secure_filename(f"{user_email}_{file_storage.filename}")
        target_path = LOCAL_UPLOAD_DIR / filename
        file_storage.save(str(target_path))
        return f"{AVATAR_URL_PREFIX}/{filename}?v={int(time.time())}"

    def _save_to_azure(self, file_storage, user_email: str) -> str:
        # Placeholder for real Azure Storage integration.
        # This keeps the same interface so the app can switch to Azure once credentials are available.
        return self._save_locally(file_storage, user_email)
