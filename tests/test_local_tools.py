from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from jarvis_local_tools import LocalToolHub


class LocalToolHubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.hub = LocalToolHub(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_catalog_has_many_key_free_allowlisted_tools(self) -> None:
        catalog = self.hub.catalog()
        self.assertTrue(catalog["ok"])
        self.assertGreaterEqual(catalog["count"], 20)
        self.assertTrue(catalog["no_api_required"])
        self.assertTrue(catalog["no_signup_required"])
        self.assertEqual(catalog["count"], len({tool["name"] for tool in catalog["tools"]}))
        self.assertGreaterEqual(len(catalog["categories"]), 5)

    def test_calculator_is_math_only(self) -> None:
        answer = self.hub.run("calculator", {"expression": "(12*8)+sqrt(81)"})
        self.assertEqual(answer["result"]["result"], 105)
        with self.assertRaises(ValueError):
            self.hub.run("calculator", {"expression": "__import__('os').system('whoami')"})

    def test_converter_and_json_formatter(self) -> None:
        converted = self.hub.run("unit_converter", {"value": 25.4, "from_unit": "mm", "to_unit": "in"})
        self.assertAlmostEqual(converted["result"]["result"], 1.0)
        formatted = self.hub.run("json_format", {"text": '{"b":2,"a":1}', "sort_keys": True})
        self.assertEqual(json.loads(formatted["result"]["text"]), {"a": 1, "b": 2})
        self.assertLess(formatted["elapsed_ms"], 5_000)

    def test_unknown_tool_never_falls_through_to_shell(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown local tool"):
            self.hub.run("powershell", {"command": "anything"})

    def test_created_notes_are_confined_to_tool_outputs(self) -> None:
        created = self.hub.run("create_note", {"title": "../../safe name", "text": "hello"})
        path = Path(created["result"]["path"]).resolve()
        self.assertTrue(path.is_file())
        self.assertTrue(path.is_relative_to(self.hub.output_dir.resolve()))
        self.assertEqual(path.read_text(encoding="utf-8"), "hello")

    def test_filename_search_is_read_only(self) -> None:
        source = self.root / "documents"
        source.mkdir()
        wanted = source / "doorstop-notes.txt"
        wanted.write_text("keep me", encoding="utf-8")
        result = self.hub.run("file_search", {"folder": str(source), "query": "doorstop"})
        self.assertEqual(result["result"]["count"], 1)
        self.assertTrue(wanted.exists())
        self.assertEqual(wanted.read_text(encoding="utf-8"), "keep me")

    def test_natural_language_dispatch_is_bounded(self) -> None:
        result = self.hub.command("Jarvis calculate 7 * 9")
        self.assertTrue(result["matched"])
        self.assertEqual(result["result"]["result"], 63)
        self.assertFalse(self.hub.command("delete everything")["matched"])


if __name__ == "__main__":
    unittest.main()
