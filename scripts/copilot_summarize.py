#!/usr/bin/env python3
"""
copilot_summarize.py
====================
Orchestrates GitHub Copilot (via the Models API / Chat Completions endpoint)
to produce:
  • A non-technical business summary of the ABAP repository.
  • A human-readable changelog derived from the git diff between the two
    most recent tags (or HEAD~1..HEAD when no tags exist).

Usage:
  python scripts/copilot_summarize.py              # business summary
  python scripts/copilot_summarize.py --changelog   # changelog

Outputs are written to:
  artifacts/business_summary.md
  artifacts/changelog.md
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import textwrap

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(os.environ.get("REPO_ROOT", ".")).resolve()
ARTIFACTS = REPO_ROOT / "artifacts"

# GitHub Copilot Models API (chat completions)
# See: https://docs.github.com/en/copilot/building-copilot-extensions/
COPILOT_API_URL = "https://api.githubcopilot.com/chat/completions"
COPILOT_TOKEN = os.environ.get("COPILOT_TOKEN", "")

MAX_CONTEXT_CHARS = 60_000  # keep prompt within model context window


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _collect_abap_sources() -> str:
    """Return concatenated ABAP source snippets (truncated to fit context)."""
    extensions = {".abap", ".clas.abap", ".fugr.abap", ".prog.abap", ".tabl.abap"}
    snippets: list[str] = []
    total = 0
    for p in sorted(REPO_ROOT.rglob("*")):
        if p.is_file() and any(p.name.endswith(ext) for ext in extensions):
            try:
                text = p.read_text(errors="replace")[:4000]
            except OSError:
                continue
            header = f"\n--- {p.relative_to(REPO_ROOT)} ---\n"
            if total + len(header) + len(text) > MAX_CONTEXT_CHARS:
                break
            snippets.append(header + text)
            total += len(header) + len(text)
    return "".join(snippets) if snippets else "(no ABAP sources found)"


def _git_diff_text() -> str:
    """Return the diff between the two most recent tags, or HEAD~1..HEAD."""
    try:
        tags = (
            subprocess.check_output(
                ["git", "tag", "--sort=-creatordate"],
                cwd=REPO_ROOT,
                text=True,
            )
            .strip()
            .splitlines()
        )
    except subprocess.CalledProcessError:
        tags = []

    diff_range = f"{tags[1]}..{tags[0]}" if len(tags) >= 2 else "HEAD~1..HEAD"

    try:
        diff = subprocess.check_output(
            ["git", "diff", "--stat", "--patch", diff_range],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        diff = "(no diff available)"

    return diff[:MAX_CONTEXT_CHARS]


def _call_copilot(system_prompt: str, user_content: str) -> str:
    """Call the Copilot Chat Completions API and return the assistant reply."""
    import requests  # lazily imported so script loads even without requests

    if not COPILOT_TOKEN:
        print("⚠  COPILOT_TOKEN not set - writing placeholder output.", file=sys.stderr)
        return "(Copilot summary unavailable - token not configured)"

    headers = {
        "Authorization": f"Bearer {COPILOT_TOKEN}",
        "Content-Type": "application/json",
        "Copilot-Integration-Id": "abap-business-bridge",
    }

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    resp = requests.post(COPILOT_API_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return str(data["choices"][0]["message"]["content"])


# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------
def generate_summary() -> None:
    ARTIFACTS.mkdir(exist_ok=True)

    sources = _collect_abap_sources()
    system_prompt = textwrap.dedent("""\
        You are a senior SAP business analyst. Given ABAP source code from a
        repository, produce a clear, concise, non-technical **business summary**
        written for stakeholders and enterprise architects.

        Structure your answer as Markdown with these sections:
        ## Overview
        ## Core Business Processes
        ## Key Capabilities
        ## SAP Module Alignment (e.g. FI, CO, SD, MM, PP …)
    """)
    user_content = f"Here is the ABAP source code from the repository:\n\n{sources}"

    summary = _call_copilot(system_prompt, user_content)
    out = ARTIFACTS / "business_summary.md"
    out.write_text(summary, encoding="utf-8")
    print(f"✓ Business summary written to {out}")


def generate_changelog() -> None:
    ARTIFACTS.mkdir(exist_ok=True)

    diff = _git_diff_text()
    system_prompt = textwrap.dedent("""\
        You are a release manager. Given the Git diff below, produce a concise
        **changelog** in Markdown. Group changes under:
        ## Added
        ## Changed
        ## Fixed
        ## Removed

        Use bullet points. Write for a non-technical audience. Omit noise.
    """)
    user_content = f"Git diff:\n\n```\n{diff}\n```"

    changelog = _call_copilot(system_prompt, user_content)
    out = ARTIFACTS / "changelog.md"
    out.write_text(changelog, encoding="utf-8")
    print(f"✓ Changelog written to {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Copilot ABAP summarization")
    parser.add_argument("--changelog", action="store_true", help="Generate changelog instead of summary")
    args = parser.parse_args()

    if args.changelog:
        generate_changelog()
    else:
        generate_summary()


if __name__ == "__main__":
    main()
