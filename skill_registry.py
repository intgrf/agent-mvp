from __future__ import annotations

import json
import re
from pathlib import Path


_SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")


def validate_skill_name(name: str) -> bool:
    return bool(_SKILL_NAME_RE.fullmatch(name))


class SkillsRegistry:
    """Loads composite skills from ``skills/<name>/SKILL.md``.

    Frontmatter should include ``name`` and ``description``. Brief text for the
    agent prompt is taken from ``description`` when present; otherwise the first
    non-empty line of the body (heading markers stripped).
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or Path(__file__).resolve().parent / "skills"
        self._brief: dict[str, str] = {}
        self.refresh()

    @property
    def skills_dir(self) -> Path:
        return self._skills_dir

    def refresh(self) -> None:
        self._brief.clear()
        if not self._skills_dir.is_dir():
            return
        for sub in sorted(self._skills_dir.iterdir()):
            if not sub.is_dir():
                continue
            md = sub / "SKILL.md"
            if not md.is_file():
                continue
            name = sub.name
            text = md.read_text(encoding="utf-8")
            self._brief[name] = self._parse_brief(text, fallback=name)

    @staticmethod
    def _parse_frontmatter_description(fm: str) -> str | None:
        lines = fm.splitlines()
        i = 0
        while i < len(lines):
            ls = lines[i].strip()
            if not ls.lower().startswith("description:"):
                i += 1
                continue
            tail = ls.split(":", 1)[1].strip()
            if tail == "|":
                i += 1
                parts: list[str] = []
                while i < len(lines):
                    line = lines[i]
                    if line.startswith("  ") or line.startswith("\t"):
                        parts.append(
                            line[2:] if line.startswith("  ") else line[1:]
                        )
                        i += 1
                    elif not line.strip():
                        parts.append("")
                        i += 1
                    else:
                        break
                text = "\n".join(parts).rstrip()
                return text if text else None
            if tail.startswith('"') or tail.startswith("'"):
                try:
                    return json.loads(tail)
                except json.JSONDecodeError:
                    return tail.strip('"').strip("'") or None
            return tail or None
        return None

    @staticmethod
    def _parse_brief(text: str, fallback: str) -> str:
        t = text.lstrip("\ufeff")
        if t.startswith("---"):
            end = t.find("\n---", 3)
            if end != -1:
                fm = t[3:end]
                body = t[end + 4 :].lstrip("\n")
                desc = SkillsRegistry._parse_frontmatter_description(fm)
                if desc is not None:
                    return desc
                return SkillsRegistry._first_line_brief(body) or fallback
        return SkillsRegistry._first_line_brief(t) or fallback

    @staticmethod
    def _first_line_brief(body: str) -> str:
        for line in body.splitlines():
            s = line.strip()
            if not s:
                continue
            s = s.lstrip("#").strip()
            return s[:500]
        return ""

    def get_brief_descriptions(self) -> dict[str, str]:
        return dict(self._brief)

    def get_prompt_section(self) -> str:
        if not self._brief:
            return (
                "(No skills yet. You can define reusable procedures with "
                "the `create_skill` tool.)"
            )
        return "\n".join(
            f"- {name}: {brief}" for name, brief in sorted(self._brief.items())
        )

    def get_full(self, skill_name: str) -> str | None:
        if not validate_skill_name(skill_name):
            return None
        path = self._skills_dir / skill_name / "SKILL.md"
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def create_skill(self, skill_name: str, content: str) -> None:
        if not validate_skill_name(skill_name):
            raise ValueError(
                "Invalid skill name: use letters, digits, underscore or hyphen "
                "(1–63 chars), must start with a letter or digit."
            )
        d = self._skills_dir / skill_name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(content, encoding="utf-8")
        self.refresh()

    @property
    def names(self) -> list[str]:
        return sorted(self._brief.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._brief

    def __len__(self) -> int:
        return len(self._brief)

    def __repr__(self) -> str:
        return f"SkillsRegistry(dir={self._skills_dir!s}, skills={self.names})"
