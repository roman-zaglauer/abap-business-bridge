#!/usr/bin/env python3
"""
update_readme.py
================
Merges the AI-generated business summary and changelog into README.md.

The README uses fenced marker comments so that repeated runs replace only
the managed sections, leaving any hand-written content intact:

  <!-- BUSINESS_SUMMARY_START -->
  …auto-generated…
  <!-- BUSINESS_SUMMARY_END -->

  <!-- CHANGELOG_START -->
  …auto-generated…
  <!-- CHANGELOG_END -->

If the markers do not exist yet the script bootstraps a new README.
"""

from __future__ import annotations

import os
import pathlib
import re

REPO_ROOT = pathlib.Path(os.environ.get("REPO_ROOT", ".")).resolve()
README = REPO_ROOT / "README.md"
ARTIFACTS = REPO_ROOT / "artifacts"

SUMMARY_MARKER_START = "<!-- BUSINESS_SUMMARY_START -->"
SUMMARY_MARKER_END = "<!-- BUSINESS_SUMMARY_END -->"
CHANGELOG_MARKER_START = "<!-- CHANGELOG_START -->"
CHANGELOG_MARKER_END = "<!-- CHANGELOG_END -->"


def _read_artifact(name: str) -> str:
    path = ARTIFACTS / name
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return f"_({name} not yet generated)_"


def _inject(text: str, start_marker: str, end_marker: str, content: str) -> str:
    """Replace content between markers, or append markers + content."""
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    replacement = f"{start_marker}\n{content}\n{end_marker}"
    if pattern.search(text):
        return pattern.sub(replacement, text)
    # Markers missing → append
    return text.rstrip() + f"\n\n{replacement}\n"


def main() -> None:
    summary = _read_artifact("business_summary.md")
    changelog = _read_artifact("changelog.md")

    if README.exists():
        readme_text = README.read_text(encoding="utf-8")
    else:
        repo_name = os.environ.get("GITHUB_REPOSITORY", REPO_ROOT.name)
        readme_text = f"# {repo_name}\n\n"

    readme_text = _inject(readme_text, SUMMARY_MARKER_START, SUMMARY_MARKER_END, summary)
    readme_text = _inject(readme_text, CHANGELOG_MARKER_START, CHANGELOG_MARKER_END, changelog)

    README.write_text(readme_text, encoding="utf-8")
    print(f"✓ README.md updated ({len(readme_text)} chars)")


if __name__ == "__main__":
    main()
