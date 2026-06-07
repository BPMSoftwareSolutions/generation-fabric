from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest

from generation_fabric.exceptions import SchemaError
from generation_fabric.layout.ascii_sketch import build_zone_document
from generation_fabric.layout.component_intent import (
    build_component_intent,
    build_component_intent_document,
    build_component_intent_schema,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"


def zone(zone_id: str, label: str, details: list[str] | None = None, band: int = 0) -> dict:
    return {
        "zone_id": zone_id,
        "label": label,
        "purpose": "",
        "details": details or [],
        "layout_role": "full_width",
        "bounds": {"band": band, "column": 0, "column_count": 1, "x": 1, "y": 1, "width": 60, "height": 1},
    }


class ComponentIntentParseTests(unittest.TestCase):
    def test_form_hint_extracts_fields_and_action(self) -> None:
        intent = build_component_intent(zone("filters", "FILTERS [form]", ["fields: date,status,team", "action: apply_filters"]))
        self.assertEqual(intent.component_type, "form")
        self.assertEqual(intent.component_id, "component-filters")
        self.assertEqual([f.name for f in intent.fields], ["date", "status", "team"])
        self.assertEqual(intent.fields[0].label, "Date")
        self.assertEqual([a.name for a in intent.actions], ["apply_filters"])
        self.assertEqual(intent.accessibility["aria_label"], "FILTERS")
        self.assertEqual(intent.warnings, ())

    def test_data_grid_hint_extracts_columns_and_binding(self) -> None:
        intent = build_component_intent(
            zone("runs", "RUNS [data_grid]", ["data: runs[]", "columns: id,status,owner,duration", "action: open_run"])
        )
        self.assertEqual(intent.component_type, "data_grid")
        self.assertEqual([c.name for c in intent.columns], ["id", "status", "owner", "duration"])
        self.assertIsNotNone(intent.data)
        assert intent.data is not None
        self.assertEqual(intent.data.source, "runs[]")
        self.assertEqual(intent.data.item_name, "run")

    def test_gauge_collects_range_measures_from_one_line(self) -> None:
        intent = build_component_intent(zone("health", "DELIVERY HEALTH [gauge]", ["value: delivery_health", "min: 0 max: 100"]))
        self.assertEqual(intent.component_type, "gauge")
        self.assertEqual(intent.measures, {"value": "delivery_health", "min": "0", "max": "100"})

    def test_chart_collects_axes_from_one_line(self) -> None:
        intent = build_component_intent(zone("trend", "TREND [chart_line]", ["x: day y: success_rate"]))
        self.assertEqual(intent.component_type, "chart_line")
        self.assertEqual(intent.measures, {"x": "day", "y": "success_rate"})

    def test_page_hint_resolves_main_landmark_role(self) -> None:
        intent = build_component_intent(zone("console", "OPERATIONS CONSOLE [page]", ["h1: Operations Console"]))
        self.assertEqual(intent.component_type, "page")
        self.assertEqual(intent.role, "main")

    def test_unknown_type_degrades_to_container_with_warning(self) -> None:
        intent = build_component_intent(zone("widget", "WHATSIT [flux_capacitor]"))
        self.assertEqual(intent.component_type, "container")
        self.assertTrue(any("unsupported component type" in w for w in intent.warnings))

    def test_plain_label_without_hint_warns(self) -> None:
        intent = build_component_intent(zone("notes", "NOTES"))
        self.assertEqual(intent.component_type, "container")
        self.assertTrue(any("no component hint" in w for w in intent.warnings))

    def test_explicit_variant_and_role_override(self) -> None:
        intent = build_component_intent(zone("panel", "SUMMARY [card]", ["variant: compact", "role: complementary"]))
        self.assertEqual(intent.variant, "compact")
        self.assertEqual(intent.role, "complementary")


class ComponentIntentDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.zones_document = {
            "page_id": "operations-dashboard",
            "title": "Operations Dashboard",
            "zones": [
                zone("console", "OPERATIONS DASHBOARD [page]", band=0),
                zone("filters", "FILTERS [form]", ["fields: date,status,team", "action: apply_filters"], band=1),
                zone("health", "DELIVERY HEALTH [gauge]", ["value: delivery_health", "min: 0 max: 100"], band=1),
                zone("runs", "RUNS [data_grid]", ["data: runs[]", "columns: id,status,owner,duration"], band=2),
                zone("notes", "NOTES", band=3),
            ],
        }

    def test_document_validates_and_collects_components(self) -> None:
        document = build_component_intent_document(self.zones_document)
        self.assertEqual(document["page_id"], "operations-dashboard")
        self.assertEqual(len(document["components"]), 5)
        types = [c["component_type"] for c in document["components"]]
        self.assertEqual(types, ["page", "form", "gauge", "data_grid", "container"])

    def test_warnings_are_aggregated(self) -> None:
        document = build_component_intent_document(self.zones_document)
        # Only the plain NOTES zone has no hint.
        self.assertTrue(any("no component hint" in w for w in document["warnings"]))

    def test_document_is_deterministic(self) -> None:
        first = build_component_intent_document(self.zones_document)
        second = build_component_intent_document(self.zones_document)
        self.assertEqual(first, second)

    def test_empty_zones_are_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            build_component_intent_document({"page_id": "x", "zones": []})

    def test_schema_builds_and_validates(self) -> None:
        schema = build_component_intent_schema()
        self.assertEqual(schema["title"], "Component Intent")


class OperationsDashboardGoldenTests(unittest.TestCase):
    def _read(self, name: str) -> str:
        return (EXAMPLES / name).read_text(encoding="utf-8")

    def test_committed_components_match_extraction(self) -> None:
        sketch = self._read("operations-dashboard.ascii.md")
        zones = build_zone_document(sketch, page_id="operations-dashboard", title="Operations Dashboard")
        committed_zones = json.loads(self._read("operations-dashboard.zones.json"))
        self.assertEqual(committed_zones, zones)

        components = build_component_intent_document(zones)
        committed_components = json.loads(self._read("operations-dashboard.components.json"))
        self.assertEqual(committed_components, components)

    def test_generator_script_reproduces_committed_examples(self) -> None:
        script_path = REPO_ROOT / "scripts" / "generate_operations_dashboard.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("generated:", result.stdout)


if __name__ == "__main__":
    unittest.main()
