"""Verify Phase 6 static deliverables without reading secrets or changing databases."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_TABLES = {
    "user",
    "system_setting",
    "platform",
    "channel",
    "sender",
    "message",
    "message_attachment",
    "ai_analysis",
    "information_item",
    "message_information",
    "category",
    "information_category",
    "tag",
    "information_tag",
    "event",
    "event_reminder",
}
REQUIRED_FILES = {
    "README.md",
    "docs/API.md",
    "docs/DATABASE.md",
    "docs/DATA_DICTIONARY.md",
    "docs/ER_MAPPING.md",
    "docs/DEMO_SCRIPT.md",
    "docs/TESTING.md",
    "docs/STATISTICS_SQL.md",
    "docs/SCREENSHOT_CHECKLIST.md",
    "docs/KNOWN_LIMITATIONS.md",
    "infra/schema.sql",
    "infra/statistics.sql",
}
ADVANCED_OBJECTS = {
    "v_upcoming_events",
    "v_channel_effectiveness",
    "v_category_statistics",
    "v_tag_popularity",
    "trg_information_item_set_updated_at",
    "sp_channel_statistics",
}
ENV_PATTERN = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)
TABLE_PATTERN = re.compile(r"^CREATE TABLE ([a-z_]+) \(", re.MULTILINE)


def read(relative_path: str) -> str:
    """Read a UTF-8 repository file."""

    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8-sig")


def main() -> int:
    """Check the final documentation and schema-export contract."""

    errors: list[str] = []
    missing_files = sorted(
        relative_path
        for relative_path in REQUIRED_FILES
        if not (REPOSITORY_ROOT / relative_path).is_file()
    )
    if missing_files:
        errors.append(f"missing files: {', '.join(missing_files)}")

    example_keys = set(ENV_PATTERN.findall(read(".env.example")))
    configuration_keys = set(ENV_PATTERN.findall(read("docs/CONFIGURATION.md")))
    if example_keys != configuration_keys:
        errors.append(
            "environment key mismatch: "
            f"example_only={sorted(example_keys - configuration_keys)}, "
            f"configuration_only={sorted(configuration_keys - example_keys)}"
        )

    schema = read("infra/schema.sql")
    exported_tables = set(TABLE_PATTERN.findall(schema))
    if not CORE_TABLES.issubset(exported_tables):
        errors.append(f"schema missing tables: {sorted(CORE_TABLES - exported_tables)}")
    if "alembic_version" not in exported_tables:
        errors.append("schema export is missing alembic_version")
    missing_objects = sorted(name for name in ADVANCED_OBJECTS if name not in schema)
    if missing_objects:
        errors.append(f"schema missing advanced objects: {', '.join(missing_objects)}")

    forbidden_compose = sorted(
        path.name
        for path in REPOSITORY_ROOT.iterdir()
        if path.is_file() and path.name.lower() in {"docker-compose.yml", "docker-compose.yaml"}
    )
    if forbidden_compose:
        errors.append(f"forbidden Docker Compose files: {', '.join(forbidden_compose)}")

    result = {
        "status": "ok" if not errors else "failed",
        "required_files": len(REQUIRED_FILES),
        "environment_keys": len(example_keys),
        "core_tables": len(CORE_TABLES & exported_tables),
        "advanced_objects": len(ADVANCED_OBJECTS) - len(missing_objects),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
