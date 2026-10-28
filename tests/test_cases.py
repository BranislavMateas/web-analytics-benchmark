"""Validate authoring invariants without exposing answers to agents."""

import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "duplicate_purchase", "lost_consent_update", "url_attribution_loss",
    "setup_mismatch", "stale_context", "no_fault",
}


def read_cases():
    return [json.loads(path.read_text()) for path in sorted((ROOT / "cases").glob("*/*.json"))]


class CaseSchemaTests(unittest.TestCase):
    def test_size_ids_and_splits(self):
        cases = read_cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({case["id"] for case in cases}), 12)
        for split in ("dev", "holdout"):
            selected = [case for case in cases if case["split"] == split]
            self.assertEqual(len(selected), 6)
            self.assertEqual({case["family"] for case in selected}, FAMILIES)
        dev_ids = {case["container"]["id"] for case in cases if case["split"] == "dev"}
        holdout_ids = {case["container"]["id"] for case in cases if case["split"] == "holdout"}
        self.assertFalse(dev_ids & holdout_ids)

    def test_required_fields_and_types(self):
        for case in read_cases():
            with self.subTest(case=case["id"]):
                self.assertEqual(set(case), {"id", "split", "family", "task", "container", "documents", "scenarios", "expected"})
                container = case["container"]
                self.assertIn(container["architecture"], ("central", "sequenced"))
                self.assertIn(container["consent_transport"], ("preserve", "drop_arguments"))
                self.assertIn(container["url_mode"], ("native", "strip_query", "zero_on_missing"))
                self.assertIsInstance(container["version"], int)
                self.assertGreater(len(container["tags"]), 0)
                self.assertEqual(len({tag["id"] for tag in container["tags"]}), len(container["tags"]))
                for tag in container["tags"]:
                    self.assertEqual(set(tag), {"id", "event", "destination", "enabled", "requires_consent", "setup_tag", "firing"})
                    self.assertIn(tag["firing"], ("per_event", "per_page"))
                    for key in ("enabled", "requires_consent", "setup_tag"):
                        self.assertIs(type(tag[key]), bool)
                for doc in case["documents"]:
                    self.assertEqual(set(doc), {"id", "date", "status", "text"})
                    self.assertIn(doc["status"], ("current", "draft", "superseded"))

    def test_synthetic_urls_and_check_references(self):
        for case in read_cases():
            with self.subTest(case=case["id"]):
                scenario_ids = {scenario["id"] for scenario in case["scenarios"]}
                self.assertEqual(len(scenario_ids), len(case["scenarios"]))
                for scenario in case["scenarios"]:
                    for step in scenario["steps"]:
                        self.assertTrue(urlsplit(step["url"]).hostname.endswith(".test"))
                        self.assertTrue({"event", "page_id", "url"}.issubset(step))
                expected = case["expected"]
                self.assertGreater(len(expected["checks"]), 0)
                self.assertEqual({check["scenario"] for check in expected["checks"]}, scenario_ids)
                self.assertEqual(set(expected["diagnoses"]), {case["family"]})
                self.assertIs(type(expected["request_human"]), bool)
                for check in expected["checks"]:
                    self.assertIs(type(check["count"]), int)
                    self.assertGreaterEqual(check["count"], 0)
                    self.assertIsInstance(check["all"], dict)
                for path in ("/id", "/version", "/country", "/architecture"):
                    self.assertIn(path, expected["unchanged_paths"])

    def test_consent_and_distinct_order_controls(self):
        for case in read_cases():
            with self.subTest(case=case["id"]):
                self.assertTrue(all(tag["requires_consent"] for tag in case["container"]["tags"]))
                checks = case["expected"]["checks"]
                for destination in ("ads", "ga4"):
                    self.assertTrue(any(check.get("destination") == destination and check["count"] == 0 for check in checks))
                    self.assertTrue(any(check.get("destination") == destination and check["count"] > 0 for check in checks))
                two_order_scenarios = []
                for scenario in case["scenarios"]:
                    purchases = [step for step in scenario["steps"] if step["event"] == "purchase"]
                    if len(purchases) == 2:
                        self.assertEqual(len({step["page_id"] for step in purchases}), 1)
                        self.assertEqual(len({step["order_id"] for step in purchases}), 2)
                        two_order_scenarios.append(scenario["id"])
                self.assertEqual(len(two_order_scenarios), 1)
                self.assertTrue(any(check["scenario"] == two_order_scenarios[0] and check.get("destination") == "ads" and check["count"] == 2 for check in checks))

    def test_no_change_controls(self):
        for case in read_cases():
            if case["family"] in ("stale_context", "no_fault"):
                with self.subTest(case=case["id"]):
                    self.assertEqual(case["expected"]["max_patch_ops"], 0)
                    self.assertEqual(case["container"]["url_mode"], "native")
                    self.assertEqual(case["container"]["consent_transport"], "preserve")
                    if case["family"] == "stale_context":
                        self.assertTrue(any(doc["status"] == "superseded" for doc in case["documents"]))


if __name__ == "__main__":
    unittest.main()
