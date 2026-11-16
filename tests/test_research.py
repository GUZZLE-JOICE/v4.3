from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from jarvis_research import ResearchEngine


class ResearchEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.engine = ResearchEngine(Path(self.temp.name), timeout=2)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_partial_provider_failure_still_returns_research(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str, *, accept: str = "application/json") -> bytes:
            calls.append(url)
            if "wikipedia.org" in url:
                return json.dumps({"query": {"pages": [{"title": "Doorstop", "extract": "A doorstop holds a door open.", "fullurl": "https://example.test/wiki"}]}}).encode()
            if "hn.algolia.com" in url:
                return json.dumps({"hits": [{"objectID": "1", "title": "Practical wedges", "url": "https://example.test/hn", "points": 5, "num_comments": 2}]}).encode()
            raise RuntimeError("provider unavailable in test")

        self.engine._fetch = fake_fetch  # type: ignore[method-assign]
        result = self.engine.research("door stop", "Door stop")
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["source_count"], 2)
        self.assertIn("Doorstop", result["text"])
        self.assertGreaterEqual(len(result["failures"]), 1)
        self.assertEqual(len(calls), 9)

    def test_duckduckgo_instant_answer_is_parsed(self) -> None:
        def fake_fetch(url: str, *, accept: str = "application/json") -> bytes:
            self.assertIn("api.duckduckgo.com", url)
            return json.dumps({
                "Heading": "Iron Man", "AbstractText": "Iron Man is a superhero.", "AbstractURL": "https://example.test/iron",
                "RelatedTopics": [{"Text": "Tony Stark - inventor", "FirstURL": "https://example.test/tony"},
                                  {"Topics": [{"Text": "Arc reactor - power source", "FirstURL": "https://example.test/arc"}]}],
            }).encode()

        self.engine._fetch = fake_fetch  # type: ignore[method-assign]
        rows = self.engine._duckduckgo("iron man")
        self.assertEqual([row["title"] for row in rows], ["Iron Man", "Tony Stark", "Arc reactor"])
        self.assertTrue(all(row["source"] == "DuckDuckGo" for row in rows))

    def test_brave_is_only_used_with_a_key_and_leads_results(self) -> None:
        self.assertNotIn("Brave Search", self.engine.source_names)
        self.engine.set_brave_key(" BSA-test-key ")
        self.assertTrue(self.engine.brave_configured)
        self.assertEqual(self.engine.source_names[0], "Brave Search")
        self.engine._brave = lambda q: [{"source": "Brave Search", "title": "Brave hit", "excerpt": "x", "url": "https://b.test"}]  # type: ignore[method-assign]
        self.engine._providers = (("Fixture", lambda q: [{"source": "Fixture", "title": "Other", "excerpt": "y", "url": "https://o.test"}]),)
        result = self.engine.research("anything")
        self.assertEqual(result["sources"][0]["source"], "Brave Search")
        self.assertEqual(self.engine.top_web_result("anything"), "https://b.test")

    def test_successful_results_are_cached(self) -> None:
        calls = 0

        def provider(_: str):
            nonlocal calls
            calls += 1
            return [{"source": "Fixture", "title": "Unique result", "excerpt": "Useful fact", "url": "https://example.test"}]

        self.engine._providers = (("Fixture", provider),)
        first = self.engine.research("cache topic")
        second = self.engine.research("cache topic")
        self.assertTrue(first["ok"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(calls, 1)

    def test_duplicate_titles_are_deduplicated(self) -> None:
        def provider(_: str):
            return [
                {"source": "Fixture", "title": "Same title", "excerpt": "one", "url": "https://one.test"},
                {"source": "Fixture", "title": "Same title!", "excerpt": "two", "url": "https://two.test"},
            ]

        self.engine._providers = (("Fixture", provider),)
        result = self.engine.research("deduplicate")
        self.assertEqual(result["result_count"], 1)

    def test_all_sources_failed_is_explicit(self) -> None:
        def unavailable(_: str):
            raise RuntimeError("offline")

        self.engine._providers = (("Offline A", unavailable), ("Offline B", unavailable))
        result = self.engine.research("unavailable topic")
        self.assertFalse(result["ok"])
        self.assertIn("No public source returned", result["error"])
        self.assertEqual(len(result["failures"]), 2)

    def test_site_filters_are_removed_from_api_query(self) -> None:
        observed: list[str] = []

        def provider(query: str):
            observed.append(query)
            return [{"source": "Fixture", "title": "Result", "excerpt": query, "url": "https://example.test"}]

        self.engine._providers = (("Fixture", provider),)
        result = self.engine.research("site:reddit.com 3D printing habits")
        self.assertTrue(result["ok"])
        self.assertEqual(observed, ["3D printing habits"])


if __name__ == "__main__":
    unittest.main()
