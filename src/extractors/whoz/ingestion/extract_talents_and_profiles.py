
"""
extract_talents.py — Extract all talents, profiles, certifications,
and accreditations (work history) from the WHOZ API.

Output structure:
    data/
      <email>/
        <email>.json                    — talent record
        profiles/
          <profile-name>.json           — one per profile
        certifications/
          <certification-name>.json     — one per certification
        accreditations/
          <accreditation-name>.json     — one per accreditation
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from whoz_client import WhozClient, get_env_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Endpoints ────────────────────────────────────────────────────────────────
TALENT_LIST_ENDPOINT = "api/talent/list/by-workspace-id"
PROFILE_BY_TALENT_IDS_ENDPOINT = "api/profile/list/by-talent-ids"
CERTIFICATION_BY_TALENT_IDS_ENDPOINT = "api/certification/list/by-talent-ids"
ACCREDITATION_BY_TALENT_IDS_ENDPOINT = "api/accreditation/list/by-talent-ids"

# ── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("data")


# ── Helpers ──────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a file/folder name."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = name.strip('. ')
    return name or "unnamed"


def deduplicate_name(name: str, seen: Dict[str, int]) -> str:
    """Append a counter if the name has already been used."""
    if name not in seen:
        seen[name] = 1
        return name
    seen[name] += 1
    return f"{name} ({seen[name]})"


def save_json(path: Path, data: Any) -> None:
    """Write a Python object to a JSON file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_talent_email(talent: Dict[str, Any]) -> str:
    """Extract the primary email address from a talent record."""
    emails = talent.get("emails") or []

    # Prefer the one marked as main
    for entry in emails:
        if entry.get("main"):
            address = entry.get("address", "").strip().lower()
            if address:
                return sanitize_filename(address)

    # Fall back to first email
    if emails and emails[0].get("address"):
        return sanitize_filename(emails[0]["address"].strip().lower())

    # Last resort: firstName.lastName or ID
    first = talent.get("firstName", "")
    last = talent.get("lastName", "")
    if first and last:
        fallback = f"{first}.{last}".strip().lower()
        logger.warning(f"No email for {fallback} — using name as folder.")
        return sanitize_filename(fallback)

    tid = talent.get("id") or "unknown"
    logger.warning(f"No email found for talent {tid} — using ID as folder name.")
    return sanitize_filename(tid)


def get_talent_id(talent: Dict[str, Any]) -> Optional[str]:
    """Extract the entity ID from a talent record."""
    return talent.get("id")


def get_entity_name(entity: Dict[str, Any], fallback_prefix: str = "item") -> str:
    """Extract a display name from a profile/certification/accreditation."""
    # For profiles: use versionName or headline.jobTitle
    version_name = entity.get("versionName")
    if version_name:
        return sanitize_filename(str(version_name).strip())

    headline = entity.get("headline") or {}
    job_title = headline.get("jobTitle")
    if job_title:
        return sanitize_filename(str(job_title).strip())

    # Generic fallbacks for certifications/accreditations
    name = (
        entity.get("name")
        or entity.get("title")
        or entity.get("label")
        or entity.get("displayName")
    )
    if name:
        return sanitize_filename(str(name).strip())

    eid = entity.get("id") or "unknown"
    return sanitize_filename(f"{fallback_prefix}_{eid}")


# ── Talent extraction ────────────────────────────────────────────────────────

def list_all_talents(
    client: WhozClient,
    workspace_id: str,
    federation_id: str,
    modified_since: Optional[str] = None,
    with_removed: bool = False,
    max_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Paginate through the talent list endpoint and return all records."""
    body: Dict[str, Any] = {
        "workspaceId": workspace_id,
        "federationId": federation_id,
        "withRemoved": with_removed,
    }
    if modified_since:
        body["modifiedSince"] = modified_since

    all_talents = []
    page = 0
    for chunk in client.paginate_list(TALENT_LIST_ENDPOINT, body, max_pages=max_pages):
        page += 1
        all_talents.extend(chunk)
        logger.info(f"Talent page {page}: +{len(chunk)} (total {len(all_talents)})")

    return all_talents


# ── Generic batch-by-talent-ids fetcher ──────────────────────────────────────

def fetch_by_talent_ids(
    client: WhozClient,
    endpoint: str,
    talent_ids: List[str],
    federation_id: str,
    entity_label: str = "entities",
    batch_size: int = 50,
) -> List[Dict[str, Any]]:
    """
    Generic fetcher for any endpoint that accepts talentIds + federationId.
    Batches in groups of ≤50 and paginates each batch.
    """
    all_entities = []

    for i in range(0, len(talent_ids), batch_size):
        batch = talent_ids[i : i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(f"{entity_label} batch {batch_num}: requesting for {len(batch)} talents …")

        body: Dict[str, Any] = {
            "talentIds": batch,
            "federationId": federation_id,
            "withRemoved": False,
        }

        # For profiles, always get all (not just main)
        if "profile" in endpoint:
            body["mainOnly"] = False

        for chunk in client.paginate_list(endpoint, body):
            all_entities.extend(chunk)

    logger.info(f"Fetched {len(all_entities)} {entity_label} total.")
    return all_entities


# ── Save helpers ─────────────────────────────────────────────────────────────

def save_entities_to_talent_folders(
    entities: List[Dict[str, Any]],
    talent_id_to_email: Dict[str, str],
    subfolder: str,
    name_fallback_prefix: str,
) -> int:
    """
    Save a list of entities into per-talent subfolders.
    Returns the count of files saved.
    """
    # Group entities by talent ID
    by_talent: Dict[str, List[Dict[str, Any]]] = {}
    for entity in entities:
        tid = entity.get("talentId")
        if not tid:
            logger.warning(f"Entity missing talentId — skipping: {list(entity.keys())[:5]}")
            continue
        by_talent.setdefault(tid, []).append(entity)

    count = 0
    for tid, ents in by_talent.items():
        email_folder = talent_id_to_email.get(tid)
        if not email_folder:
            email_folder = sanitize_filename(tid)
            logger.warning(f"Unknown talent {tid} — using ID as folder name.")

        folder = OUTPUT_DIR / email_folder / subfolder
        seen_names: Dict[str, int] = {}

        for entity in ents:
            name = get_entity_name(entity, fallback_prefix=name_fallback_prefix)
            unique_name = deduplicate_name(name, seen_names)
            save_json(folder / f"{unique_name}.json", entity)
            count += 1

    return count


# ── Main pipeline ────────────────────────────────────────────────────────────

def run(
    modified_since: Optional[str] = None,
    with_removed: bool = False,
    max_pages: Optional[int] = None,
) -> None:
    config = get_env_config()
    client = WhozClient()
    federation_id = config["federation_id"]

    # 1. List all talents
    talents = list_all_talents(
        client,
        workspace_id=config["workspace_id"],
        federation_id=federation_id,
        modified_since=modified_since,
        with_removed=with_removed,
        max_pages=max_pages,
    )

    if not talents:
        logger.info("No talents found — nothing to do.")
        return

    # 2. Build ID → email mapping and save talents
    talent_ids: List[str] = []
    talent_id_to_email: Dict[str, str] = {}

    for talent in talents:
        tid = get_talent_id(talent)
        if not tid:
            continue

        email = get_talent_email(talent)
        talent_ids.append(tid)
        talent_id_to_email[tid] = email

        talent_dir = OUTPUT_DIR / email
        save_json(talent_dir / f"{email}.json", talent)

    logger.info(f"Saved {len(talent_ids)} talent files.")

    # 3. Fetch & save profiles
    profiles = fetch_by_talent_ids(
        client, PROFILE_BY_TALENT_IDS_ENDPOINT,
        talent_ids, federation_id, entity_label="Profiles",
    )
    n = save_entities_to_talent_folders(
        profiles, talent_id_to_email, subfolder="profiles", name_fallback_prefix="profile",
    )
    logger.info(f"Saved {n} profile files.")

    # 4. Fetch & save certifications
    certifications = fetch_by_talent_ids(
        client, CERTIFICATION_BY_TALENT_IDS_ENDPOINT,
        talent_ids, federation_id, entity_label="Certifications",
    )
    n = save_entities_to_talent_folders(
        certifications, talent_id_to_email, subfolder="certifications", name_fallback_prefix="cert",
    )
    logger.info(f"Saved {n} certification files.")

    # 5. Fetch & save accreditations (work history)
    accreditations = fetch_by_talent_ids(
        client, ACCREDITATION_BY_TALENT_IDS_ENDPOINT,
        talent_ids, federation_id, entity_label="Accreditations",
    )
    n = save_entities_to_talent_folders(
        accreditations, talent_id_to_email, subfolder="accreditations", name_fallback_prefix="accreditation",
    )
    logger.info(f"Saved {n} accreditation files.")

    logger.info("Done ✓")


if __name__ == "__main__":
    run(
        modified_since=None, # modified_since="2026-01-01T00:00:00Z",  # Set to None to fetch everything
        with_removed=False,
    )
