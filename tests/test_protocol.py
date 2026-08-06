"""Tests for the local JSON protocol."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

COMPONENT_DIR = Path(__file__).parents[1] / "custom_components" / "apple_health_bridge"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, COMPONENT_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType("apple_health_bridge")
package.__path__ = [str(COMPONENT_DIR)]
sys.modules["apple_health_bridge"] = package
_load_module("apple_health_bridge.const", "const.py")
protocol = _load_module("apple_health_bridge.protocol", "protocol.py")


class ProtocolTests(unittest.TestCase):
    def test_valid_full_payload(self) -> None:
        result = protocol.validate_payload(
            {
                "version": 1,
                "timestamp": "2026-08-03T10:30:00+08:00",
                "health": {"steps": {"value": "1234", "unit": "steps"}},
                "location": {"latitude": 31.2, "longitude": 121.4, "accuracy": 8},
                "wifi": {"ssid": "Home", "bssid": "AA:BB:CC:DD:EE:FF"},
            }
        )
        self.assertEqual(result["health"]["steps"]["value"], 1234.0)
        self.assertEqual(result["wifi"]["bssid"], "AA:BB:CC:DD:EE:FF")

    def test_localized_form_number_is_normalized(self) -> None:
        result = protocol.validate_payload(
            {"health": {"steps": {"value": "1,234 步"}}}
        )
        self.assertEqual(result["health"]["steps"]["value"], 1234.0)

        result = protocol.validate_payload(
            {"health": {"steps": {"value": "12,5"}}}
        )
        self.assertEqual(result["health"]["steps"]["value"], 12.5)

    def test_requires_data_section(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"version": 1})

    def test_rejects_bad_metric_key(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"health": {"Bad Key": 1}})

    def test_rejects_out_of_range_location(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload(
                {"location": {"latitude": 91, "longitude": 0}}
            )

    def test_rejects_unknown_wifi_field(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"wifi": {"channel": 149}})

    def test_rejects_non_finite_number(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"health": {"steps": float("inf")}})


    def test_passes_daily_totals(self) -> None:
        """Daily-total metrics should now accept a plain numeric value plus
        the canonical unit (``steps``, ``km``, ``kcal``, ``min``, ``h``,
        ``floors``)."""
        payload = {
            "health": {
                "steps": {"value": 6234, "unit": "steps"},
                "walking_running_distance": {"value": 5.234, "unit": "km"},
                "active_energy": {"value": 480, "unit": "kcal"},
                "exercise_minutes": {"value": 32, "unit": "min"},
                "stand_hours": {"value": 8, "unit": "h"},
                "floors_climbed": {"value": 12, "unit": "floors"},
            }
        }
        result = protocol.validate_payload(payload)
        self.assertEqual(result["health"]["steps"]["value"], 6234.0)
        self.assertEqual(result["health"]["walking_running_distance"]["value"], 5.234)
        self.assertEqual(result["health"]["active_energy"]["value"], 480.0)
        self.assertEqual(result["health"]["exercise_minutes"]["value"], 32.0)
        self.assertEqual(result["health"]["stand_hours"]["value"], 8.0)
        self.assertEqual(result["health"]["floors_climbed"]["value"], 12.0)

    def test_passes_sleep_duration(self) -> None:
        """Sleep duration expects hours after the shortcut's /3600 conversion."""
        payload = {"health": {"sleep_duration": {"value": 7.5, "unit": "h"}}}
        result = protocol.validate_payload(payload)
        self.assertEqual(result["health"]["sleep_duration"]["value"], 7.5)
        self.assertEqual(result["health"]["sleep_duration"]["unit"], "h")

    def test_unit_field_is_optional(self) -> None:
        """Unit remains optional; missing unit falls back to the metric's
        KNOWN_HEALTH_METRICS default at the sensor layer (not protocol)."""
        payload = {"health": {"steps": {"value": 6234}}}
        result = protocol.validate_payload(payload)
        self.assertNotIn("unit", result["health"]["steps"])


if __name__ == "__main__":
    unittest.main()
