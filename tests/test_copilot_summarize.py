"""Tests for scripts/copilot_summarize.py"""

from __future__ import annotations

import importlib
import pathlib
import subprocess
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def abap_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "zcl_test.clas.abap").write_text("CLASS zcl_test DEFINITION.\nENDCLASS.\n")
    (src / "z_report.prog.abap").write_text("REPORT z_report.\nWRITE: 'hi'.\n")
    return tmp_path


class TestCollectAbapSources:
    def test_collects_abap_files(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.copilot_summarize as mod

        importlib.reload(mod)
        result = mod._collect_abap_sources()
        assert "zcl_test" in result
        assert "z_report" in result

    def test_empty_repo(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(tmp_path))
        import scripts.copilot_summarize as mod

        importlib.reload(mod)
        result = mod._collect_abap_sources()
        assert result == "(no ABAP sources found)"

    def test_respects_context_limit(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        src = tmp_path / "src"
        src.mkdir()
        # Create a file that would exceed context if fully included
        big_content = "DATA lv TYPE string.\n" * 5000
        (src / "z_big.clas.abap").write_text(big_content)
        (src / "z_small.prog.abap").write_text("REPORT z_small.\n")

        monkeypatch.setenv("REPO_ROOT", str(tmp_path))
        import scripts.copilot_summarize as mod

        importlib.reload(mod)
        result = mod._collect_abap_sources()
        # Should not exceed the max context chars
        assert len(result) <= mod.MAX_CONTEXT_CHARS + 5000  # +buffer for last file


class TestGitDiffText:
    def test_fallback_on_no_tags(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.copilot_summarize as mod

        importlib.reload(mod)

        # Mock subprocess to simulate no tags
        with patch("subprocess.check_output") as mock_co:
            mock_co.side_effect = [
                "",  # git tag returns empty
                "diff --stat output",  # git diff
            ]
            mod._git_diff_text()
            # Should use HEAD~1..HEAD
            call_args = mock_co.call_args_list[1][0][0]
            assert "HEAD~1..HEAD" in call_args

    def test_uses_tags_when_available(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.copilot_summarize as mod

        importlib.reload(mod)

        with patch("subprocess.check_output") as mock_co:
            mock_co.side_effect = [
                "v2.0.0\nv1.0.0\n",  # two tags
                "diff output here",
            ]
            mod._git_diff_text()
            call_args = mock_co.call_args_list[1][0][0]
            assert "v1.0.0..v2.0.0" in call_args

    def test_handles_git_failure(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.copilot_summarize as mod

        importlib.reload(mod)

        with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git")):
            result = mod._git_diff_text()
            assert "no diff available" in result


class TestCallCopilot:
    def test_returns_placeholder_without_token(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", ".")
        monkeypatch.setenv("COPILOT_TOKEN", "")
        import scripts.copilot_summarize as mod

        importlib.reload(mod)
        result = mod._call_copilot("system", "user")
        assert "unavailable" in result

    def test_calls_api_with_correct_payload(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", ".")
        monkeypatch.setenv("COPILOT_TOKEN", "test-token-123")
        import scripts.copilot_summarize as mod

        importlib.reload(mod)

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "AI generated summary"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = mod._call_copilot("Be helpful", "Summarize this")

        assert result == "AI generated summary"
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["headers"]["Authorization"] == "Bearer test-token-123"
        payload = call_kwargs[1]["json"]
        assert payload["messages"][0]["content"] == "Be helpful"
        assert payload["messages"][1]["content"] == "Summarize this"


class TestGenerateSummary:
    def test_writes_summary_file(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        monkeypatch.setenv("COPILOT_TOKEN", "")
        import scripts.copilot_summarize as mod

        importlib.reload(mod)
        mod.generate_summary()
        out = abap_repo / "artifacts" / "business_summary.md"
        assert out.exists()
        assert "unavailable" in out.read_text()


class TestGenerateChangelog:
    def test_writes_changelog_file(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        monkeypatch.setenv("COPILOT_TOKEN", "")
        import scripts.copilot_summarize as mod

        importlib.reload(mod)

        with patch("subprocess.check_output", return_value=""):
            mod.generate_changelog()

        out = abap_repo / "artifacts" / "changelog.md"
        assert out.exists()
