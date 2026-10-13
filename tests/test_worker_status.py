import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from scripts.validate_worker_status import validate_feed

ROOT = Path(__file__).resolve().parents[1]


class WorkerFeedTests(unittest.TestCase):
    def setUp(self):
        self.feed = json.loads((ROOT / "public_html/pekerja-web/status.example.json").read_text())
        self.updated = datetime(2000, 1, 1, tzinfo=timezone.utc)
        self.feed["updatedAt"] = self.updated.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.feed["teams"][0].update(status="working", observedAt=self.feed["updatedAt"], evidence=[{"label": "Synthetic evidence", "url": "https://github.com/erwin071996/rumahwebhous/pull/1"}])
        self.now = self.updated + timedelta(hours=1)

    def reject(self, mutate):
        feed = copy.deepcopy(self.feed)
        mutate(feed)
        with self.assertRaises(ValueError):
            validate_feed(feed, self.now)

    def test_curated_snapshot_valid_without_changing_source_times(self):
        before = copy.deepcopy(self.feed)
        validate_feed(self.feed, self.now)
        self.assertEqual(self.feed, before)

    def test_empty_source_example_has_no_actual_data(self):
        example = json.loads((ROOT / "public_html/pekerja-web/status.example.json").read_text())
        validate_feed(example, self.now)
        self.assertIsNone(example["updatedAt"])
        self.assertTrue(all(t["status"] == "unknown" and t["observedAt"] is None and t["evidence"] == [] for t in example["teams"]))
        self.assertIsNone(example["release"]["sha"])
        self.assertIsNone(example["release"]["prUrl"])
        self.assertFalse((ROOT / "public_html/pekerja-web/status.json").exists())

    def test_empty_source_cannot_claim_work_or_release(self):
        self.reject(lambda f: f.update(updatedAt=None))
        self.reject(lambda f: (f.update(updatedAt=None), f["teams"][0].update(status="unknown", observedAt=None), f["release"].update(stage="live")))

    def test_unknown_activity_accepts_missing_observation(self):
        self.assertIsNone(self.feed["teams"][1]["observedAt"])
        self.assertEqual(self.feed["teams"][1]["status"], "unknown")
        validate_feed(self.feed, self.now)

    def test_claimed_work_requires_time_and_evidence(self):
        self.reject(lambda f: f["teams"][1].update(status="working"))
        self.reject(lambda f: f["teams"][0].update(evidence=[]))

    def test_blocker_has_source_time_and_reason_without_fabricated_public_link(self):
        self.feed["teams"][0].update(status="blocked", evidence=[], summary="Synthetic approval hold.", waitingFor="Synthetic approver")
        validate_feed(self.feed, self.now)

    def test_rejects_duplicates_extra_fields_and_unsupported_cadence(self):
        self.reject(lambda f: f["teams"].__setitem__(1, copy.deepcopy(f["teams"][0])))
        self.reject(lambda f: f.update(rawChat="transcript"))
        self.reject(lambda f: f.update(refreshIntervalMs=100))

    def test_rejects_personal_data_and_internal_paths(self):
        for value in ["Contact a.person@example.org", "Call " + " ".join(["00"] * 6), "Source " + "/" + "/".join(("work" + "space", "private", "file")), "Source " + "C:" + chr(92) + "Users" + chr(92) + "person", "gh" + "p_" + "x" * 12]:
            with self.subTest(value=value):
                self.reject(lambda f: f["teams"][0].update(summary=value))

    def test_rejects_foreign_or_script_links(self):
        for url in ["javascript:alert(1)", "https://github.com/other/repo/pull/1", "https://github.com@elsewhere.invalid/erwin071996/rumahwebhous/pull/1", "https://github.com/erwin071996/rumahwebhous/pull/1?token=x"]:
            with self.subTest(url=url):
                self.reject(lambda f: f["teams"][0]["evidence"][0].update(url=url))

    def test_future_or_newer_than_feed_timestamp_rejected(self):
        future = (self.now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        newer = (self.updated + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.reject(lambda f: f.update(updatedAt=future))
        self.reject(lambda f: f["teams"][0].update(observedAt=newer))


if __name__ == "__main__":
    unittest.main()
