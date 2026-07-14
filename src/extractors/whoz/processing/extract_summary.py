"""
extract_summary.py — Transform raw WHOZ data into app-ready summaries.

Reads from data/<email>/ and writes:
  - summary.json into each person's folder
  - all.json combining every person into one array
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


# ── File helpers ─────────────────────────────────────────────────────────────

def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file, returning None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"Could not load {path}: {e}")
        return None


def load_all_in_folder(folder: Path) -> List[Dict[str, Any]]:
    """Load all JSON files in a folder."""
    results = []
    if folder.exists():
        for f in sorted(folder.glob("*.json")):
            data = load_json(f)
            if data:
                results.append(data)
    return results


# ── Profile helpers ──────────────────────────────────────────────────────────

def get_main_profile(profiles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the main profile, or fall back to the first one."""
    for p in profiles:
        if p.get("main"):
            return p
    return profiles[0] if profiles else None


# ── Field extractors ─────────────────────────────────────────────────────────

def extract_top_skills(profile: Dict[str, Any], max_skills: int = 10) -> List[Dict[str, Any]]:
    """Extract top skills — prioritise FAVORITE visibility, then by proficiency."""
    aptitudes = profile.get("aptitudes") or []

    def sort_key(a):
        is_fav = 1 if a.get("visibility") == "FAVORITE" else 0
        prof = a.get("proficiency") or 0
        return (-is_fav, -prof)

    sorted_apt = sorted(aptitudes, key=sort_key)

    return [
        {
            "name": a.get("name"),
            "type": a.get("type"),
            "proficiency": a.get("proficiency"),
            "highlighted": a.get("visibility") == "FAVORITE",
        }
        for a in sorted_apt[:max_skills]
        if a.get("name")
    ]


def extract_experience(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract work positions from the profile, most recent first."""
    positions = profile.get("positions") or []

    positions_sorted = sorted(
        positions,
        key=lambda p: p.get("startDate") or "",
        reverse=True,
    )

    return [
        {
            "title": pos.get("title"),
            "company": pos.get("companyName") or pos.get("employerName"),
            "description": pos.get("description"),
            "startDate": pos.get("startDate"),
            "endDate": pos.get("endDate"),
            "current": pos.get("current", False),
            "location": (pos.get("addresses") or [{}])[0].get("formattedAddress")
            if pos.get("addresses") else None,
        }
        for pos in positions_sorted
    ]


def extract_education(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract education entries from the profile, most recent first."""
    educations = profile.get("educations") or []

    educations_sorted = sorted(
        educations,
        key=lambda e: e.get("endDate") or e.get("startDate") or "",
        reverse=True,
    )

    return [
        {
            "school": edu.get("school"),
            "degree": edu.get("degree"),
            "description": edu.get("description"),
            "startDate": edu.get("startDate"),
            "endDate": edu.get("endDate"),
            "location": (edu.get("address") or {}).get("formattedAddress"),
        }
        for edu in educations_sorted
    ]


def extract_certifications(certs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract certification summaries, most recent first."""
    certs_sorted = sorted(
        certs,
        key=lambda c: c.get("obtentionDate") or "",
        reverse=True,
    )

    return [
        {
            "title": cert.get("title"),
            "issuer": cert.get("deliveringEntity"),
            "obtainedDate": cert.get("obtentionDate"),
            "expirationDate": cert.get("expirationDate"),
        }
        for cert in certs_sorted
        if cert.get("title")
    ]


def extract_accreditations(accreds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract accreditation (work history) summaries, most recent first."""
    accreds_sorted = sorted(
        accreds,
        key=lambda a: a.get("obtentionDate") or "",
        reverse=True,
    )

    return [
        {
            "title": acc.get("title"),
            "issuer": acc.get("deliveringEntity"),
            "obtainedDate": acc.get("obtentionDate"),
            "expirationDate": acc.get("expirationDate"),
            "description": acc.get("description"),
        }
        for acc in accreds_sorted
        if acc.get("title")
    ]


def get_current_team(talent: Dict[str, Any]) -> Optional[str]:
    """Get the most recent orgUnit from history."""
    history = talent.get("history") or []
    if not history:
        return None

    history_sorted = sorted(history, key=lambda h: h.get("since") or "", reverse=True)
    return history_sorted[0].get("orgUnit")


def get_current_scope(talent: Dict[str, Any]) -> Optional[str]:
    """Get the most recent scope (EMPLOYEE, ALUMNI, etc.) from history."""
    history = talent.get("history") or []
    if not history:
        return None

    history_sorted = sorted(history, key=lambda h: h.get("since") or "", reverse=True)
    return history_sorted[0].get("scope")


def resolve_person(person_id: Optional[str], lookup: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Resolve a talent ID to a {id, name, email} dict using the lookup table."""
    if not person_id:
        return None

    info = lookup.get(person_id)
    if info:
        return {
            "id": person_id,
            "name": info.get("name"),
            "email": info.get("email"),
        }

    # ID exists but not in our lookup (maybe a different workspace)
    return {"id": person_id, "name": None, "email": None}


# ── Summary builder ──────────────────────────────────────────────────────────

def build_summary(
    talent: Dict[str, Any],
    profiles: List[Dict[str, Any]],
    certifications: List[Dict[str, Any]],
    accreditations: List[Dict[str, Any]],
    people_lookup: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    """Build the app-ready summary for a single person."""

    # Basic identity
    first = talent.get("firstName") or ""
    last = talent.get("lastName") or ""

    # Email
    emails = talent.get("emails") or []
    main_email = None
    for entry in emails:
        if entry.get("main"):
            main_email = entry.get("address")
            break
    if not main_email and emails:
        main_email = emails[0].get("address")

    # Location
    address = talent.get("address") or {}
    location = {
        "city": address.get("city"),
        "country": address.get("countryCode"),
        "formatted": address.get("formattedAddress"),
        "lat": (address.get("coordinates") or {}).get("lat"),
        "lng": (address.get("coordinates") or {}).get("lng"),
    }

    # Main profile data
    main_profile = get_main_profile(profiles)
    headline = (main_profile.get("headline") or {}) if main_profile else {}

    summary = {
        # Who they are
        "name": f"{first} {last}".strip(),
        "firstName": first,
        "lastName": last,
        "email": main_email,
        "phone": talent.get("phoneNumber"),
        "photo": (talent.get("photo") or {}).get("uid"),
        "initials": talent.get("initials"),
        "gender": talent.get("gender"),
        "nationalities": talent.get("nationalities") or [],
        "language": talent.get("language"),
        "bio": headline.get("bio"),
        "hobbies": (main_profile.get("hobbies") or []) if main_profile else [],
        # Where they work
        "location": location,
        "remote": talent.get("remoteWork"),
        "team": get_current_team(talent),
        "scope": get_current_scope(talent),
        "manager": resolve_person(talent.get("managerId"), people_lookup),
        "mentor": resolve_person(talent.get("mentorId"), people_lookup),
        "mobility": {
            "national": headline.get("nationalMobility"),
            "international": headline.get("internationalMobility"),
            "destinations": headline.get("mobilityDestinations"),
        },
        # What they do
        "jobTitle": headline.get("jobTitle"),
        "company": headline.get("company"),
        "aim": headline.get("aim"),
        "yearsOfExperience": talent.get("yearsOfExperience"),
        "topSkills": extract_top_skills(main_profile) if main_profile else [],
        "experience": extract_experience(main_profile) if main_profile else [],
        "education": extract_education(main_profile) if main_profile else [],
        "certifications": extract_certifications(certifications),
        "accreditations": extract_accreditations(accreditations),
    }

    return summary


# ── Main pipeline ────────────────────────────────────────────────────────────

def main():
    person_dirs = sorted([d for d in DATA_DIR.iterdir() if d.is_dir()])
    logger.info(f"Found {len(person_dirs)} person folders.")

    # ── Pass 1: Build a lookup table of talent ID → {name, email} ────────────
    logger.info("Building people lookup table …")
    people_lookup: Dict[str, Dict[str, str]] = {}
    talent_data_by_dir: Dict[str, Dict[str, Any]] = {}

    for person_dir in person_dirs:
        talent_file = person_dir / f"{person_dir.name}.json"
        if not talent_file.exists():
            candidates = [
                f for f in person_dir.glob("*.json")
                if f.name != "summary.json"
                and "profiles" not in f.parts
                and "certifications" not in f.parts
                and "accreditations" not in f.parts
            ]
            talent_file = candidates[0] if candidates else None

        if not talent_file or not talent_file.exists():
            continue

        talent = load_json(talent_file)
        if not talent:
            continue

        tid = talent.get("id")
        if tid:
            first = talent.get("firstName") or ""
            last = talent.get("lastName") or ""
            emails = talent.get("emails") or []
            main_email = None
            for entry in emails:
                if entry.get("main"):
                    main_email = entry.get("address")
                    break
            if not main_email and emails:
                main_email = emails[0].get("address")

            people_lookup[tid] = {
                "name": f"{first} {last}".strip(),
                "email": main_email,
            }

        talent_data_by_dir[str(person_dir)] = talent

    logger.info(f"Lookup table built with {len(people_lookup)} people.")

    # ── Pass 2: Build summaries ──────────────────────────────────────────────
    all_people = []
    success = 0

    for person_dir in person_dirs:
        talent = talent_data_by_dir.get(str(person_dir))
        if not talent:
            continue

        # Load related entities
        profiles = load_all_in_folder(person_dir / "profiles")
        certifications = load_all_in_folder(person_dir / "certifications")
        accreditations = load_all_in_folder(person_dir / "accreditations")

        # Build and save individual summary
        summary = build_summary(talent, profiles, certifications, accreditations, people_lookup)
        save_path = person_dir / "summary.json"

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        all_people.append(summary)
        success += 1

    # Save combined file
    all_file = DATA_DIR / "all.json"
    with open(all_file, "w", encoding="utf-8") as f:
        json.dump(all_people, f, indent=2, ensure_ascii=False)

    logger.info(f"Done ✓ — Generated {success} summary files + {all_file}")


if __name__ == "__main__":
    main()
