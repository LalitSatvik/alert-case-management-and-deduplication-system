"""Export the canonical AlertIn JSON schema to a file.

This script generates backend/schemas/alert.schema.json from the AlertIn model.
Run from the backend/ directory: python scripts/export_schema.py
"""

import json
import pathlib

from app.schemas.alert import export_alert_json_schema


def main() -> None:
    """Export AlertIn schema to backend/schemas/alert.schema.json."""
    schema = export_alert_json_schema()
    output_path = pathlib.Path(__file__).parent.parent / "schemas" / "alert.schema.json"

    # Ensure the schemas directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the schema as formatted JSON with trailing newline
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Exported schema to {output_path}")


if __name__ == "__main__":
    main()
