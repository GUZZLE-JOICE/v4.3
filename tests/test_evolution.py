from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from jarvis_evolution import EvolutionEngine, EvolutionError


class GuardedEvolutionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "source"
        (self.workspace / "tests").mkdir(parents=True)
        (self.workspace / "jarvis_browser.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "jarvis_v2.html").write_text("<main>JARVIS</main>\n", encoding="utf-8")
        (self.workspace / "tests" / "test_bundle.py").write_text(
            "import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        (self.workspace / "notes.txt").write_text("old behavior\n", encoding="utf-8")
        self.engine = EvolutionEngine(self.root / "data")
        self.engine.configure({"source_workspace": str(self.workspace)})

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_external_skill_activates_immediately(self) -> None:
        skill = self.engine.remember_skill("Short replies", "Keep normal status replies concise.")
        self.assertEqual(skill["kind"], "external_skill")
        self.assertTrue(skill["active"])
        self.assertEqual(self.engine.status()["skill_count"], 1)

    def test_user_intent_warns_but_jarvis_intent_queues_quietly(self) -> None:
        user = self.engine.create_intent("Improve the LAB button.", "user")
        jarvis = self.engine.create_intent("Investigate repeated LAB error.", "jarvis")
        self.assertTrue(user["requires_warning"])
        self.assertFalse(jarvis["requires_warning"])
        self.assertEqual(jarvis["status"], "needs_patch")

    def test_exact_patch_backup_validation_and_rollback(self) -> None:
        proposal = self.engine.propose_replacement(
            source_path="notes.txt",
            find_text="old behavior",
            replacement_text="new behavior",
            reason="Test guarded replacement",
        )
        self.assertEqual((self.workspace / "notes.txt").read_text(encoding="utf-8"), "old behavior\n")
        applied = self.engine.apply(proposal["id"], proposal["approval_phrase"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual((self.workspace / "notes.txt").read_text(encoding="utf-8"), "new behavior\n")
        reverted = self.engine.rollback(proposal["id"])
        self.assertEqual(reverted["status"], "reverted")
        self.assertEqual((self.workspace / "notes.txt").read_text(encoding="utf-8"), "old behavior\n")

    def test_failed_syntax_check_restores_source(self) -> None:
        proposal = self.engine.propose_replacement(
            source_path="jarvis_browser.py",
            find_text="VALUE = 1",
            replacement_text="def broken(",
            reason="Force validation failure",
        )
        result = self.engine.apply(proposal["id"], proposal["approval_phrase"])
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual((self.workspace / "jarvis_browser.py").read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_high_risk_patch_is_blocked(self) -> None:
        with self.assertRaises(EvolutionError):
            self.engine.propose_replacement(
                source_path="notes.txt",
                find_text="old behavior",
                replacement_text="os.system('anything')",
                reason="Unsafe shell attempt",
            )


if __name__ == "__main__":
    unittest.main()
