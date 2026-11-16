"""Guarded self-improvement support for the local JARVIS app.

JARVIS may update external skills and preferences automatically.  Executable
source changes are stored as reviewable proposals and can only be promoted by
the person using the local app.  Every promoted change is backed up, checked,
and rolled back automatically if validation fails.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".py", ".js", ".html", ".json", ".txt", ".md", ".yml", ".yaml", ".wxs", ".wixproj"}
BLOCKED_PARTS = {".git", "dist", "build", "__pycache__", ".venv", "venv", "node_modules"}
MAX_REPLACEMENT_CHARS = 80_000
MAX_SKILL_CHARS = 8_000
FORBIDDEN_PATCH_PATTERNS = (
    (re.compile(r"\bWin" r"logon\b|CurrentVersion" r"\\\\Run|\bsch" r"tasks\b", re.I), "Windows persistence or shell replacement"),
    (re.compile(r"Set-MpPreference|DisableAntiSpyware|DisableRealtimeMonitoring", re.I), "security-tool disabling"),
    (re.compile(r"bypass.{0,40}(?:captcha|verification)|(?:captcha|verification).{0,40}bypass", re.I | re.S), "web-verification bypass"),
    (re.compile(r"allow_automatic_print_start\s*[\"']?\s*[:=]\s*True|automatic_print_start\s*[\"']?\s*[:=]\s*True", re.I), "unattended physical printing"),
    (re.compile(r"\bshell\s*=\s*True\b|\bos\.system\s*\(", re.I), "unrestricted command-shell execution"),
    (re.compile(r"powershell(?:\.exe)?\s+[^\n]{0,80}(?:-enc|-encodedcommand)", re.I), "encoded PowerShell execution"),
)


def _now() -> int:
    return int(time.time())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_slug(value: str, fallback: str = "improvement") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:64]
    return slug or fallback


class EvolutionError(RuntimeError):
    """A user-readable evolution-engine failure."""


class EvolutionEngine:
    """Own proposals, external skills, backups, validation, and rollback."""

    def __init__(self, data_root: Path) -> None:
        self.root = Path(data_root) / "evolution"
        self.proposals_dir = self.root / "proposals"
        self.skills_dir = self.root / "skills"
        self.backups_dir = self.root / "backups"
        self.state_path = self.root / "state.json"
        for directory in (self.proposals_dir, self.skills_dir, self.backups_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "automatic_skill_updates": True,
            "source_workspace": "",
            "code_changes_require_approval": True,
            "automatic_executable_code_changes": False,
            "last_activity": 0,
        }

    def _state(self) -> dict[str, Any]:
        state = self._default_state()
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except (OSError, ValueError):
            pass
        # These two invariants are deliberately not user-configurable.
        state["code_changes_require_approval"] = True
        state["automatic_executable_code_changes"] = False
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_path)

    def configure(self, values: dict[str, Any]) -> dict[str, Any]:
        state = self._state()
        if "enabled" in values:
            state["enabled"] = bool(values["enabled"])
        if "automatic_skill_updates" in values:
            state["automatic_skill_updates"] = bool(values["automatic_skill_updates"])
        if "source_workspace" in values:
            raw = str(values.get("source_workspace") or "").strip().strip('"')
            if raw:
                workspace = Path(raw).expanduser().resolve()
                self._validate_workspace(workspace)
                state["source_workspace"] = str(workspace)
            else:
                state["source_workspace"] = ""
        state["last_activity"] = _now()
        self._save_state(state)
        return self.status()

    def _validate_workspace(self, workspace: Path) -> None:
        if not workspace.is_dir():
            raise EvolutionError("That source workspace folder does not exist.")
        required = ("jarvis_browser.py", "jarvis_v2.html", "tests/test_bundle.py")
        missing = [name for name in required if not (workspace / name).is_file()]
        if missing:
            raise EvolutionError("Choose the extracted JARVIS source folder, not the installed Program Files folder.")

    def _workspace(self) -> Path:
        raw = str(self._state().get("source_workspace") or "").strip()
        if not raw:
            raise EvolutionError("Set the extracted JARVIS source workspace in Settings > Evolution first.")
        workspace = Path(raw).resolve()
        self._validate_workspace(workspace)
        return workspace

    def _safe_relative_path(self, raw: Any) -> Path:
        value = str(raw or "").replace("\\", "/").strip().lstrip("/")
        relative = Path(value)
        if not value or relative.is_absolute() or ".." in relative.parts:
            raise EvolutionError("That source path is not allowed.")
        if any(part.casefold() in BLOCKED_PARTS for part in relative.parts):
            raise EvolutionError("Build, cache, dependency, and repository-control folders cannot be edited.")
        if relative.suffix.casefold() not in TEXT_SUFFIXES:
            raise EvolutionError("Self-edit proposals are limited to JARVIS text source files.")
        return relative

    def _scan_replacement(self, replacement: str) -> None:
        for pattern, label in FORBIDDEN_PATCH_PATTERNS:
            if pattern.search(replacement):
                raise EvolutionError(f"This guarded editor blocks {label}.")

    def _proposal_path(self, proposal_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9-]{8,96}", proposal_id or ""):
            raise EvolutionError("Invalid proposal id.")
        return self.proposals_dir / (proposal_id + ".json")

    def _load_proposal(self, proposal_id: str) -> dict[str, Any]:
        path = self._proposal_path(proposal_id)
        try:
            proposal = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise EvolutionError("That proposal no longer exists.") from exc
        if not isinstance(proposal, dict):
            raise EvolutionError("That proposal is damaged.")
        return proposal

    def _save_proposal(self, proposal: dict[str, Any]) -> None:
        path = self._proposal_path(str(proposal["id"]))
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def remember_skill(self, title: Any, instruction: Any, reason: Any = "") -> dict[str, Any]:
        state = self._state()
        if not state.get("enabled") or not state.get("automatic_skill_updates"):
            raise EvolutionError("Automatic skill learning is turned off.")
        clean_title = " ".join(str(title or "").split())[:120]
        clean_instruction = str(instruction or "").strip()
        if not clean_title or not clean_instruction:
            raise EvolutionError("A skill needs a title and an instruction.")
        if len(clean_instruction) > MAX_SKILL_CHARS:
            raise EvolutionError("That skill is too large to store safely.")
        slug = _safe_slug(clean_title)
        path = self.skills_dir / (slug + ".json")
        previous: dict[str, Any] = {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        except (OSError, ValueError):
            pass
        skill = {
            "id": slug,
            "title": clean_title,
            "instruction": clean_instruction,
            "reason": " ".join(str(reason or "Autonomous safe improvement").split())[:500],
            "origin": "jarvis",
            "created_at": int(previous.get("created_at") or _now()),
            "updated_at": _now(),
            "active": True,
            "kind": "external_skill",
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(skill, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        state["last_activity"] = _now()
        self._save_state(state)
        return skill

    def create_intent(self, instruction: Any, origin: Any = "user") -> dict[str, Any]:
        clean = " ".join(str(instruction or "").split())[:2000]
        normalized_origin = "jarvis" if str(origin).casefold() == "jarvis" else "user"
        if not clean:
            raise EvolutionError("Describe the change JARVIS should prepare.")
        proposal_id = f"{int(time.time())}-{_safe_slug(clean)[:36]}"
        proposal = {
            "id": proposal_id,
            "kind": "intent",
            "origin": normalized_origin,
            "instruction": clean,
            "reason": clean,
            "status": "needs_patch",
            "created_at": _now(),
            "updated_at": _now(),
            "requires_warning": normalized_origin == "user",
            "message": "Queued for a source-aware patch. No executable code has been changed.",
        }
        self._save_proposal(proposal)
        return self._public_proposal(proposal, include_diff=True)

    def propose_replacement(
        self,
        *,
        source_path: Any,
        find_text: Any,
        replacement_text: Any,
        reason: Any,
        origin: Any = "user",
    ) -> dict[str, Any]:
        state = self._state()
        if not state.get("enabled"):
            raise EvolutionError("Self-improvement is turned off.")
        workspace = self._workspace()
        relative = self._safe_relative_path(source_path)
        target = (workspace / relative).resolve()
        if workspace not in target.parents or not target.is_file():
            raise EvolutionError("That JARVIS source file was not found in the selected workspace.")
        before = target.read_text(encoding="utf-8")
        find_value = str(find_text or "")
        replacement_value = str(replacement_text or "")
        if not find_value:
            raise EvolutionError("Paste the exact existing line or block to replace.")
        if len(find_value) > MAX_REPLACEMENT_CHARS or len(replacement_value) > MAX_REPLACEMENT_CHARS:
            raise EvolutionError("That replacement is too large for the guarded line editor.")
        self._scan_replacement(replacement_value)
        occurrences = before.count(find_value)
        if occurrences != 1:
            raise EvolutionError(f"The existing text must match exactly once; JARVIS found {occurrences} matches.")
        after = before.replace(find_value, replacement_value, 1)
        if before == after:
            raise EvolutionError("That replacement would not change the file.")
        clean_reason = " ".join(str(reason or "Source improvement").split())[:1000]
        normalized_origin = "jarvis" if str(origin).casefold() == "jarvis" else "user"
        proposal_id = f"{int(time.time())}-{_safe_slug(relative.as_posix())[:40]}"
        diff = "".join(difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="a/" + relative.as_posix(),
            tofile="b/" + relative.as_posix(),
            n=4,
        ))
        proposal = {
            "id": proposal_id,
            "kind": "source_patch",
            "origin": normalized_origin,
            "path": relative.as_posix(),
            "reason": clean_reason,
            "status": "pending_review",
            "created_at": _now(),
            "updated_at": _now(),
            "base_sha256": _sha256_text(before),
            "find_text": find_value,
            "replacement_text": replacement_value,
            "diff": diff[:160_000],
            "requires_warning": normalized_origin == "user",
            "approval_phrase": "APPLY " + proposal_id,
            "message": "Patch staged. The running app and source file are unchanged.",
        }
        self._save_proposal(proposal)
        return self._public_proposal(proposal, include_diff=True)

    def _public_proposal(self, proposal: dict[str, Any], *, include_diff: bool = False) -> dict[str, Any]:
        keys = (
            "id", "kind", "origin", "path", "reason", "instruction", "status", "created_at",
            "updated_at", "requires_warning", "message", "test_summary", "approval_phrase",
        )
        public = {key: proposal.get(key) for key in keys if key in proposal}
        if include_diff:
            public["diff"] = str(proposal.get("diff") or "")
        return public

    def proposals(self, *, include_diff: bool = False) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in self.proposals_dir.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    result.append(self._public_proposal(value, include_diff=include_diff))
            except (OSError, ValueError):
                continue
        result.sort(key=lambda item: int(item.get("created_at") or 0), reverse=True)
        return result[:100]

    def skills(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in self.skills_dir.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    result.append(value)
            except (OSError, ValueError):
                continue
        result.sort(key=lambda item: int(item.get("updated_at") or 0), reverse=True)
        return result[:200]

    def status(self) -> dict[str, Any]:
        state = self._state()
        proposals = self.proposals()
        state.update({
            "pending_count": sum(1 for item in proposals if item.get("status") in {"pending_review", "needs_patch"}),
            "applied_count": sum(1 for item in proposals if item.get("status") == "applied"),
            "skill_count": len(self.skills()),
            "proposals": proposals,
            "skills": self.skills(),
            "guardrails": [
                "JARVIS may update external skills automatically.",
                "Executable source patches always require local approval.",
                "Every applied patch is backed up and tested.",
                "A failed validation automatically restores the previous file.",
                "The installed one-file EXE is never rewritten in place.",
            ],
        })
        return state

    def _run_validation(self, workspace: Path, relative: Path) -> tuple[bool, str]:
        commands: list[list[str]] = []
        if relative.suffix.casefold() == ".py":
            commands.append([sys.executable, "-m", "py_compile", str(relative)])
        elif relative.suffix.casefold() == ".js" and shutil.which("node"):
            commands.append(["node", "--check", str(relative)])
        if (workspace / "tests").is_dir():
            commands.append([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        output: list[str] = []
        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=240,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, ("Validation could not finish: " + str(exc))[:12_000]
            combined = (completed.stdout or "") + (completed.stderr or "")
            output.append("$ " + " ".join(command) + "\n" + combined[-8_000:])
            if completed.returncode != 0:
                return False, "\n".join(output)[-12_000:]
        return True, "\n".join(output)[-12_000:] or "No file-specific checker was available."

    def apply(self, proposal_id: Any, approval_phrase: Any) -> dict[str, Any]:
        proposal = self._load_proposal(str(proposal_id or ""))
        if proposal.get("kind") != "source_patch" or proposal.get("status") != "pending_review":
            raise EvolutionError("Only a pending source patch can be applied.")
        if str(approval_phrase or "").strip() != str(proposal.get("approval_phrase") or ""):
            raise EvolutionError("The approval phrase does not match this patch.")
        workspace = self._workspace()
        relative = self._safe_relative_path(proposal.get("path"))
        target = (workspace / relative).resolve()
        before = target.read_text(encoding="utf-8")
        if _sha256_text(before) != proposal.get("base_sha256"):
            raise EvolutionError("That source file changed after this proposal was created. Create a fresh proposal.")
        find_value = str(proposal.get("find_text") or "")
        replacement_value = str(proposal.get("replacement_text") or "")
        if before.count(find_value) != 1:
            raise EvolutionError("The proposed source block no longer has one exact match.")
        after = before.replace(find_value, replacement_value, 1)
        backup = self.backups_dir / str(proposal["id"]) / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(before, encoding="utf-8")
        temporary = target.with_name(target.name + ".jarvis-next")
        temporary.write_text(after, encoding="utf-8")
        os.replace(temporary, target)
        ok, summary = self._run_validation(workspace, relative)
        if not ok:
            restore = target.with_name(target.name + ".jarvis-restore")
            restore.write_text(before, encoding="utf-8")
            os.replace(restore, target)
            proposal.update({
                "status": "rolled_back",
                "updated_at": _now(),
                "test_summary": summary,
                "message": "Validation failed. JARVIS restored the previous source automatically.",
            })
            self._save_proposal(proposal)
            return self._public_proposal(proposal, include_diff=True)
        proposal.update({
            "status": "applied",
            "updated_at": _now(),
            "test_summary": summary,
            "backup_path": str(backup),
            "applied_sha256": _sha256_text(after),
            "message": "Source patch applied and validation passed. Rebuild the MSI to install it.",
        })
        self._save_proposal(proposal)
        return self._public_proposal(proposal, include_diff=True)

    def rollback(self, proposal_id: Any) -> dict[str, Any]:
        proposal = self._load_proposal(str(proposal_id or ""))
        if proposal.get("status") != "applied":
            raise EvolutionError("Only an applied patch can be rolled back.")
        workspace = self._workspace()
        relative = self._safe_relative_path(proposal.get("path"))
        target = (workspace / relative).resolve()
        backup = self.backups_dir / str(proposal["id"]) / relative
        if not backup.is_file():
            raise EvolutionError("The backup for that patch is missing.")
        current = target.read_text(encoding="utf-8")
        if _sha256_text(current) != proposal.get("applied_sha256"):
            raise EvolutionError("The source changed after this patch. JARVIS will not overwrite those newer edits.")
        previous = backup.read_text(encoding="utf-8")
        temporary = target.with_name(target.name + ".jarvis-rollback")
        temporary.write_text(previous, encoding="utf-8")
        os.replace(temporary, target)
        ok, summary = self._run_validation(workspace, relative)
        proposal.update({
            "status": "reverted" if ok else "reverted_validation_warning",
            "updated_at": _now(),
            "test_summary": summary,
            "message": "Previous source restored." if ok else "Previous source restored, but its current validation reported a problem.",
        })
        self._save_proposal(proposal)
        return self._public_proposal(proposal, include_diff=True)
