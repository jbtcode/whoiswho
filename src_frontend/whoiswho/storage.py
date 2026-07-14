import json
import os
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("WHOISWHO_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

TABLE_FILES = {
    "Users": DATA_DIR / "users.json",
    "Employees": DATA_DIR / "employees.json",
}

DEFAULT_USER = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada.lovelace@whoiswho.dev",
    "address": "10 Downing Street, London",
    "hobbies": "Reading, Hiking, Tech",
    "role": "Product Designer",
    "avatar": "AL",
}


def user_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **DEFAULT_USER,
        **row,
        "first_name": row.get("first_name", DEFAULT_USER["first_name"]),
        "last_name": row.get("last_name", DEFAULT_USER["last_name"]),
        "email": row.get("email", DEFAULT_USER["email"]),
        "avatar": row.get("avatar", f"{row.get('first_name', DEFAULT_USER['first_name'])[0].upper()}{row.get('last_name', DEFAULT_USER['last_name'])[0].upper()}"),
    }


def _read_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)


def initialize_tables() -> None:
    for path in TABLE_FILES.values():
        if not path.exists():
            path.write_text("[]", encoding="utf-8")


def load_table(table_name: str) -> List[Dict[str, Any]]:
    initialize_tables()
    return _read_json(TABLE_FILES[table_name])


def upsert_row(table_name: str, row: Dict[str, Any]) -> Dict[str, Any]:
    initialize_tables()
    rows = load_table(table_name)

    partition_key = row.get("PartitionKey", "default")
    row_key = row.get("RowKey", row.get("email", "default"))

    existing_index = next(
        (
            index
            for index, item in enumerate(rows)
            if item.get("PartitionKey") == partition_key and item.get("RowKey") == row_key
        ),
        None,
    )

    row_to_store = {**row, "PartitionKey": partition_key, "RowKey": row_key}

    if existing_index is None:
        rows.append(row_to_store)
    else:
        rows[existing_index] = {**rows[existing_index], **row_to_store}

    _write_json(TABLE_FILES[table_name], rows)
    return row_to_store


def delete_row(table_name: str, row_key: str, partition_key: str = "default") -> None:
    initialize_tables()
    rows = load_table(table_name)
    filtered = [
        row for row in rows if not (row.get("PartitionKey") == partition_key and row.get("RowKey") == row_key)
    ]
    _write_json(TABLE_FILES[table_name], filtered)
