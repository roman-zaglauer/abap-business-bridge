"""Tests for scripts/leanix_sync.py"""

from __future__ import annotations

import importlib
import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def repo_with_metadata(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create temp dir with metadata.json and business_summary.md."""
    metadata = {
        "generated_at": "2026-05-12T00:00:00+00:00",
        "repository": "test-abap-repo",
        "total_lines_of_code": 150,
        "total_objects": 5,
        "categories": {"Class": 2, "Report": 3},
        "lines_of_business": {"Finance (FI)": 3, "Sales & Distribution (SD)": 2},
        "objects": [],
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata))

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "business_summary.md").write_text("## Overview\nBilling application.")

    return tmp_path


def _reload_leanix(monkeypatch, tmp_path, api_token="tok", subdomain="acme", fs_id=""):
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("LEANIX_API_TOKEN", api_token)
    monkeypatch.setenv("LEANIX_SUBDOMAIN", subdomain)
    monkeypatch.setenv("LEANIX_WORKSPACE_ID", "ws-123")
    monkeypatch.setenv("LEANIX_FACT_SHEET_ID", fs_id)
    import scripts.leanix_sync as mod

    importlib.reload(mod)
    return mod


class TestGetAccessToken:
    def test_exchanges_token(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "bearer-xyz"}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            token = mod._get_access_token()

        assert token == "bearer-xyz"
        url = mock_post.call_args[0][0]
        assert "acme.leanix.net" in url
        assert "oauth2/token" in url


class TestGraphQL:
    def test_retries_on_429(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)

        rate_limited = MagicMock()
        rate_limited.status_code = 429

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.raise_for_status = MagicMock()
        ok_resp.json.return_value = {"data": {"result": "ok"}}

        with patch("requests.post", side_effect=[rate_limited, ok_resp]), patch("time.sleep"):
            result = mod._graphql("token", "query { test }")

        assert result["data"]["result"] == "ok"

    def test_raises_after_max_retries(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)

        rate_limited = MagicMock()
        rate_limited.status_code = 429

        with (
            patch("requests.post", return_value=rate_limited),
            patch("time.sleep"),
            pytest.raises(RuntimeError, match="rate limiting"),
        ):
            mod._graphql("token", "query { test }")

    def test_raises_on_graphql_errors(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"errors": [{"message": "Field not found"}]}

        with patch("requests.post", return_value=resp), pytest.raises(RuntimeError, match="GraphQL errors"):
            mod._graphql("token", "query { test }")


class TestFindFactSheet:
    def test_returns_id_when_found(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)

        with patch.object(mod, "_graphql") as mock_gql:
            mock_gql.return_value = {
                "data": {"allFactSheets": {"edges": [{"node": {"id": "fs-abc", "displayName": "test"}}]}}
            }
            result = mod._find_fact_sheet("token", "test")
        assert result == "fs-abc"

    def test_returns_none_when_not_found(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)

        with patch.object(mod, "_graphql") as mock_gql:
            mock_gql.return_value = {"data": {"allFactSheets": {"edges": []}}}
            result = mod._find_fact_sheet("token", "nonexistent")
        assert result is None


class TestUpdateFactSheet:
    def test_uses_optimistic_locking(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)
        metadata = json.loads((repo_with_metadata / "metadata.json").read_text())

        with patch.object(mod, "_graphql") as mock_gql:
            # First call: fetch revision
            mock_gql.side_effect = [
                {"data": {"factSheet": {"id": "fs-1", "rev": 42}}},
                {"data": {"updateFactSheet": {"factSheet": {"id": "fs-1", "displayName": "Test", "rev": 43}}}},
            ]
            mod._update_fact_sheet("token", "fs-1", "Summary text", metadata)

        # Second call should include the revision
        update_call = mock_gql.call_args_list[1]
        variables = update_call[1].get("variables") or update_call[0][2]
        assert variables["rev"] == 42


class TestMainSkips:
    def test_skips_without_credentials(self, repo_with_metadata, monkeypatch, capsys):
        mod = _reload_leanix(monkeypatch, repo_with_metadata, api_token="", subdomain="")
        mod.main()
        captured = capsys.readouterr()
        assert "skipping" in captured.err.lower() or "not set" in captured.err.lower()

    def test_fails_without_metadata_file(self, tmp_path, monkeypatch):
        mod = _reload_leanix(monkeypatch, tmp_path)
        with pytest.raises(SystemExit):
            mod.main()


class TestMainIntegration:
    def test_creates_fact_sheet_when_not_found(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata)

        with (
            patch.object(mod, "_get_access_token", return_value="tok"),
            patch.object(mod, "_find_fact_sheet", return_value=None),
            patch.object(mod, "_create_fact_sheet", return_value="new-fs") as mock_create,
            patch.object(mod, "_update_fact_sheet") as mock_update,
        ):
            mod.main()

        mock_create.assert_called_once()
        assert mock_create.call_args[0][1] == "test-abap-repo"
        mock_update.assert_called_once()

    def test_updates_existing_fact_sheet(self, repo_with_metadata, monkeypatch):
        mod = _reload_leanix(monkeypatch, repo_with_metadata, fs_id="existing-fs")

        with (
            patch.object(mod, "_get_access_token", return_value="tok"),
            patch.object(mod, "_update_fact_sheet") as mock_update,
        ):
            mod.main()

        mock_update.assert_called_once()
        assert mock_update.call_args[0][1] == "existing-fs"
