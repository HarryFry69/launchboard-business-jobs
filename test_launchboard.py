"""Offline regression tests for Launchboard's ranking and curated data."""
import json
import os
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault("ADZUNA_APP_ID", "offline-test")
os.environ.setdefault("ADZUNA_APP_KEY", "offline-test")

import collector_adzuna as adz
import collector_combined as combined
import collector_direct as direct

ROOT = Path(__file__).parent


class LaunchboardTests(unittest.TestCase):
    def test_adzuna_quota_and_rotation(self):
        self.assertEqual(len(adz.QUERIES), 12)
        self.assertEqual(len(set(adz.QUERIES)), 12)
        self.assertTrue(any("insurance" in q or "broker" in q or "underwrit" in q or "claims" in q for q in adz.QUERIES))
        self.assertTrue(any("pr" in q.lower().split() or "communications" in q or "public relations" in q or "media relations" in q for q in adz.QUERIES))
        self.assertTrue(any("wealth" in q or "financial planning" in q or "paraplan" in q or "investment" in q for q in adz.QUERIES))

    def test_categories_preserve_core_and_add_specialisms(self):
        tests = [
            ("Trainee Insurance Broker", "Insurance broking", "Insurance & Broking"),
            ("PR Account Executive", "Public relations agency", "PR & Communications"),
            ("Graduate Wealth Management Analyst", "Financial planning", "Wealth Management & Financial Planning"),
            ("Account Executive", "PR agency writing press releases and pitching journalists", "PR & Communications"),
            ("Account Handler", "Independent insurance broker servicing policies", "Insurance & Broking"),
            ("Client Services Administrator", "Wealth management and financial planning", "Wealth Management & Financial Planning"),
            ("Graduate Strategy Consultant", "Management consulting", "Strategy & Consulting"),
        ]
        for title, desc, expected in tests:
            with self.subTest(title=title):
                self.assertEqual(adz.category_for(title, desc), expected)
                self.assertTrue(adz.relevant(title, desc))

    def test_excludes_senior_positions(self):
        self.assertTrue(adz.hard_excluded("Senior Wealth Manager"))
        self.assertTrue(adz.hard_excluded("Head of Public Relations"))
        self.assertFalse(adz.hard_excluded("Junior Insurance Broker"))

    def test_direct_junior_insurance_and_pr(self):
        self.assertTrue(direct.early_relevant("Junior Insurance Broker", "Entry-level insurance sales and client support"))
        self.assertTrue(direct.early_relevant("PR Account Executive", "Junior public relations agency position with no experience required"))

    def test_research_directory(self):
        rows = json.loads((ROOT / "employers.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 250)
        self.assertEqual(len(rows), len({r["name"].lower() for r in rows}))
        self.assertGreaterEqual(len({r["category"] for r in rows}), 3)
        self.assertGreaterEqual(sum(bool(r["independent"]) for r in rows), 180)
        for sector in ("Insurance & Broking", "PR & Communications", "Wealth Management & Financial Planning"):
            self.assertGreaterEqual(sum(r["category"] == sector for r in rows), 50)
        for r in rows:
            if r.get("linkType") == "research-source":
                self.assertTrue(r.get("sourceName"), r["name"])
                self.assertTrue(r.get("sourceUrl", "").startswith("https://"), r["name"])
        for r in rows:
            self.assertEqual(urlparse(r["url"]).scheme, "https")
            self.assertTrue(urlparse(r["url"]).netloc)
            self.assertIsInstance(r["independent"], bool)
            self.assertEqual(r["checkedAt"], "2026-10-22")
        label, independent = adz.employer_profile("MFP Wealth Management")
        self.assertTrue(independent)
        self.assertIn("Boutique", label)

    def test_featured_are_dated_verified_and_unique(self):
        rows = json.loads((ROOT / "featured_jobs.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 10)
        self.assertEqual(len(rows), len({r["id"] for r in rows}))
        for r in rows:
            self.assertEqual(r["verifiedAt"], "2026-10-22")
            self.assertTrue(r["direct"])
            self.assertTrue(r["caution"])
            self.assertTrue(r["url"].startswith("https://"))
            self.assertGreaterEqual(date.fromisoformat(r["expiresAt"]), date.fromisoformat(r["verifiedAt"]))
            if "deadline" in r:
                self.assertGreaterEqual(date.fromisoformat(r["deadline"]), date.fromisoformat(r["verifiedAt"]))

    def test_deadline_expiry(self):
        now = date(2026, 10, 22)
        self.assertFalse(combined.current_listing({"deadline": "2026-10-21"}, now))
        self.assertTrue(combined.current_listing({"deadline": "2026-10-22"}, now))
        self.assertTrue(combined.current_listing({"expiresAt": "2026-11-02"}, now))
        self.assertFalse(combined.current_listing({"expiresAt": "2026-10-20"}, now))
        self.assertTrue(combined.current_listing({}, now))


if __name__ == "__main__":
    unittest.main()
