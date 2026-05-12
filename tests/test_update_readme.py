"""Tests for scripts/update_readme.py"""

from __future__ import annotations

import importlib
import pathlib

import pytest


@pytest.fixture()
def repo_with_artifacts(tmp_path: pathlib.Path) -> pathlib.Path:
    """Set up a temp dir with artifacts/ and an existing README."""
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "business_summary.md").write_text("## Overview\nThis app does billing.")
    (artifacts / "changelog.md").write_text("## Added\n- New billing report")
    return tmp_path


class TestInject:
    def test_replaces_existing_markers(self):
        from scripts.update_readme import _inject

        text = "# Title\n<!-- START -->\nold content\n<!-- END -->\nFooter"
        result = _inject(text, "<!-- START -->", "<!-- END -->", "new content")
        assert "new content" in result
        assert "old content" not in result
        assert "Footer" in result

    def test_appends_when_markers_missing(self):
        from scripts.update_readme import _inject

        text = "# Title\nSome text"
        result = _inject(text, "<!-- START -->", "<!-- END -->", "injected")
        assert "<!-- START -->" in result
        assert "injected" in result
        assert "<!-- END -->" in result
        assert result.startswith("# Title")

    def test_idempotent(self):
        from scripts.update_readme import _inject

        text = "# Title\n<!-- S -->\nfirst\n<!-- E -->"
        r1 = _inject(text, "<!-- S -->", "<!-- E -->", "second")
        r2 = _inject(r1, "<!-- S -->", "<!-- E -->", "second")
        assert r1 == r2


class TestReadArtifact:
    def test_reads_existing(self, repo_with_artifacts: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(repo_with_artifacts))
        import scripts.update_readme as mod

        importlib.reload(mod)
        assert "billing" in mod._read_artifact("business_summary.md")

    def test_missing_artifact(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "artifacts").mkdir()
        monkeypatch.setenv("REPO_ROOT", str(tmp_path))
        import scripts.update_readme as mod

        importlib.reload(mod)
        result = mod._read_artifact("nonexistent.md")
        assert "not yet generated" in result


class TestMainIntegration:
    def test_creates_readme_from_scratch(self, repo_with_artifacts: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(repo_with_artifacts))
        import scripts.update_readme as mod

        importlib.reload(mod)
        mod.REPO_ROOT = repo_with_artifacts
        mod.README = repo_with_artifacts / "README.md"
        mod.ARTIFACTS = repo_with_artifacts / "artifacts"
        mod.main()

        content = (repo_with_artifacts / "README.md").read_text()
        assert "<!-- BUSINESS_SUMMARY_START -->" in content
        assert "billing" in content
        assert "<!-- CHANGELOG_START -->" in content
        assert "billing report" in content

    def test_preserves_existing_content(self, repo_with_artifacts: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        readme = repo_with_artifacts / "README.md"
        readme.write_text(
            "# My Project\n\nCustom intro.\n\n"
            "<!-- BUSINESS_SUMMARY_START -->\nold summary\n<!-- BUSINESS_SUMMARY_END -->\n\n"
            "<!-- CHANGELOG_START -->\nold log\n<!-- CHANGELOG_END -->\n\n"
            "## Custom Section\nKeep me!\n"
        )

        monkeypatch.setenv("REPO_ROOT", str(repo_with_artifacts))
        import scripts.update_readme as mod

        importlib.reload(mod)
        mod.REPO_ROOT = repo_with_artifacts
        mod.README = readme
        mod.ARTIFACTS = repo_with_artifacts / "artifacts"
        mod.main()

        content = readme.read_text()
        assert "Custom intro." in content
        assert "Keep me!" in content
        assert "old summary" not in content
        assert "billing" in content

    def test_double_run_is_idempotent(self, repo_with_artifacts: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(repo_with_artifacts))
        import scripts.update_readme as mod

        importlib.reload(mod)
        mod.REPO_ROOT = repo_with_artifacts
        mod.README = repo_with_artifacts / "README.md"
        mod.ARTIFACTS = repo_with_artifacts / "artifacts"

        mod.main()
        first = (repo_with_artifacts / "README.md").read_text()
        mod.main()
        second = (repo_with_artifacts / "README.md").read_text()
        assert first == second
