"""
extract_photos.py — Download all talent photos from the WHOZ API.

Self-contained: fetches talents directly from the API, then downloads photos to:
    data/<email>/<photo-uid>.<ext>
"""

import json
import logging
import re
import urllib3
from pathlib import Path
from typing import Optional, List, Dict, Any

from whoz_client import WhozClient, get_env_config

urllib3.disable_warnings(urllib3.exceptions.HeaderParsingError)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("urllib3").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
TALENT_LIST_ENDPOINT = "api/talent/list/by-workspace-id"


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a folder name."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = name.strip('. ')
    return name or "unnamed"


def get_talent_email(talent: Dict[str, Any]) -> Optional[str]:
    """Extract the primary email address from a talent record."""
    emails = talent.get("emails") or []

    for entry in emails:
        if entry.get("main"):
            address = entry.get("address", "").strip().lower()
            if address:
                return sanitize_filename(address)

    if emails and emails[0].get("address"):
        return sanitize_filename(emails[0]["address"].strip().lower())

    first = talent.get("firstName", "")
    last = talent.get("lastName", "")
    if first and last:
        return sanitize_filename(f"{first}.{last}".strip().lower())

    tid = talent.get("id") or "unknown"
    return sanitize_filename(tid)


def list_all_talents(client: WhozClient, workspace_id: str, federation_id: str) -> List[Dict[str, Any]]:
    """Paginate through the talent list endpoint and return all records."""
    body: Dict[str, Any] = {
        "workspaceId": workspace_id,
        "federationId": federation_id,
        "withRemoved": False,
    }

    all_talents = []
    page = 0
    for chunk in client.paginate_list(TALENT_LIST_ENDPOINT, body):
        page += 1
        all_talents.extend(chunk)
        logger.info(f"Talent page {page}: +{len(chunk)} (total {len(all_talents)})")

    return all_talents


def download_photo(client: WhozClient, photo_uid: str) -> Optional[bytes]:
    """Download a photo by UID. Returns raw bytes or None on failure."""
    url = f"{client.base_url}/api/photo/{photo_uid}"
    headers = client._get_headers()
    headers.pop("Content-Type", None)

    try:
        resp = client.session.get(url, headers=headers)
        if resp.status_code == 200 and len(resp.content) > 0:
            return resp.content
        else:
            logger.warning(f"Photo {photo_uid}: status {resp.status_code}, size {len(resp.content)}")
            return None
    except Exception as e:
        logger.warning(f"Photo {photo_uid}: error {e}")
        return None


def get_extension(content: bytes) -> str:
    """Detect image format from magic bytes."""
    if content[:3] == b'\xff\xd8\xff':
        return "jpg"
    if content[:8] == b'\x89PNG\r\n\x1a\n':
        return "png"
    if content[:4] == b'GIF8':
        return "gif"
    if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return "webp"
    return "jpg"


def main():
    config = get_env_config()
    client = WhozClient()

    # 1. Fetch all talents from the API
    logger.info("Fetching talents from WHOZ API …")
    talents = list_all_talents(client, config["workspace_id"], config["federation_id"])
    logger.info(f"Found {len(talents)} talents.")

    # 2. Download photos
    downloaded = 0
    skipped = 0
    failed = 0

    for talent in talents:
        photo = talent.get("photo") or {}
        photo_uid = photo.get("uid")
        name = f"{talent.get('firstName', '')} {talent.get('lastName', '')}".strip()

        if not photo_uid or photo.get("isEmpty"):
            skipped += 1
            continue

        email = get_talent_email(talent)
        folder = DATA_DIR / email

        # Skip if already downloaded
        existing = list(folder.glob(f"{photo_uid}.*"))
        if existing:
            skipped += 1
            continue

        # Download
        content = download_photo(client, photo_uid)
        if content:
            ext = get_extension(content)
            photo_path = folder / f"{photo_uid}.{ext}"
            photo_path.parent.mkdir(parents=True, exist_ok=True)
            photo_path.write_bytes(content)
            downloaded += 1
            logger.info(f"✓ {name} → {photo_uid}.{ext} ({len(content)} bytes)")
        else:
            failed += 1
            logger.warning(f"✗ {name} — photo download failed (uid: {photo_uid})")

    logger.info(f"Done ✓ — Downloaded: {downloaded} | Skipped: {skipped} | Failed: {failed}")


if __name__ == "__main__":
    main()
