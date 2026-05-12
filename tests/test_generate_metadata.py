"""Tests for scripts/generate_metadata.py"""

from __future__ import annotations

import importlib
import json
import pathlib

import pytest


@pytest.fixture()
def abap_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal abapGit-style repo tree."""
    src = tmp_path / "src"
    src.mkdir()

    # Class
    cls = src / "zcl_fi_posting.clas.abap"
    cls.write_text("CLASS zcl_fi_posting DEFINITION.\nENDCLASS.\nCLASS zcl_fi_posting IMPLEMENTATION.\nENDCLASS.\n")

    # Report
    rpt = src / "z_sd_order_report.prog.abap"
    rpt.write_text("REPORT z_sd_order_report.\nWRITE: 'Hello'.\n")

    # CDS view
    cds = src / "z_mm_stock.ddls.asddls"
    cds.write_text(
        "@AbapCatalog.sqlViewName: 'ZV_MM_STOCK'\ndefine view Z_MM_STOCK as select from mard { matnr, werks, labst }\n"
    )

    # Interface
    intf = src / "zif_co_calculator.intf.abap"
    intf.write_text("INTERFACE zif_co_calculator PUBLIC.\n  METHODS calculate.\nENDINTERFACE.\n")

    # Generic ABAP file (no known qualifier)
    gen = src / "z_utility.abap"
    gen.write_text("* utility\nDATA lv_x TYPE string.\n")

    # Non-ABAP file (should be ignored)
    (src / "notes.txt").write_text("not abap")

    return tmp_path


@pytest.fixture()
def _patch_repo_root(abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Patch environment so generate_metadata uses the temp repo."""
    monkeypatch.setenv("REPO_ROOT", str(abap_repo))


class TestClassifyFile:
    def test_class(self, abap_repo: pathlib.Path):
        from scripts.generate_metadata import _classify_file

        assert _classify_file(abap_repo / "src" / "zcl_fi_posting.clas.abap") == "Class"

    def test_report(self, abap_repo: pathlib.Path):
        from scripts.generate_metadata import _classify_file

        assert _classify_file(abap_repo / "src" / "z_sd_order_report.prog.abap") == "Report"

    def test_cds_view(self, abap_repo: pathlib.Path):
        from scripts.generate_metadata import _classify_file

        assert _classify_file(abap_repo / "src" / "z_mm_stock.ddls.asddls") == "CDS View"

    def test_interface(self, abap_repo: pathlib.Path):
        from scripts.generate_metadata import _classify_file

        assert _classify_file(abap_repo / "src" / "zif_co_calculator.intf.abap") == "Interface"

    def test_generic_abap(self, abap_repo: pathlib.Path):
        from scripts.generate_metadata import _classify_file

        assert _classify_file(abap_repo / "src" / "z_utility.abap") == "ABAP Source"

    def test_non_abap_returns_none(self, abap_repo: pathlib.Path):
        from scripts.generate_metadata import _classify_file

        assert _classify_file(abap_repo / "src" / "notes.txt") is None


class TestInferLoB:
    def test_fi(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        # Re-import to pick up patched REPO_ROOT
        import scripts.generate_metadata as mod

        importlib.reload(mod)
        assert mod._infer_lob(abap_repo / "src" / "zcl_fi_posting.clas.abap") == "Finance (FI)"

    def test_sd(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.generate_metadata as mod

        importlib.reload(mod)
        assert mod._infer_lob(abap_repo / "src" / "z_sd_order_report.prog.abap") == "Sales & Distribution (SD)"

    def test_mm(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.generate_metadata as mod

        importlib.reload(mod)
        assert mod._infer_lob(abap_repo / "src" / "z_mm_stock.ddls.asddls") == "Materials Management (MM)"

    def test_unknown(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.generate_metadata as mod

        importlib.reload(mod)
        assert mod._infer_lob(abap_repo / "src" / "z_utility.abap") == "Cross-Application / Unknown"


class TestCountLines:
    def test_counts_correctly(self, abap_repo: pathlib.Path):
        from scripts.generate_metadata import _count_lines

        assert _count_lines(abap_repo / "src" / "z_sd_order_report.prog.abap") == 2

    def test_missing_file(self, tmp_path: pathlib.Path):
        from scripts.generate_metadata import _count_lines

        assert _count_lines(tmp_path / "nonexistent.abap") == 0


class TestMainIntegration:
    def test_produces_valid_metadata(self, abap_repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(abap_repo))
        import scripts.generate_metadata as mod

        importlib.reload(mod)
        mod.OUTPUT_FILE = abap_repo / "metadata.json"
        mod.REPO_ROOT = abap_repo
        mod.main()

        meta = json.loads((abap_repo / "metadata.json").read_text())

        assert meta["total_objects"] == 5
        assert meta["total_lines_of_code"] > 0
        assert "Class" in meta["categories"]
        assert "Report" in meta["categories"]
        assert "CDS View" in meta["categories"]
        assert "generated_at" in meta

    def test_empty_repo(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REPO_ROOT", str(tmp_path))
        import scripts.generate_metadata as mod

        importlib.reload(mod)
        mod.OUTPUT_FILE = tmp_path / "metadata.json"
        mod.REPO_ROOT = tmp_path
        mod.main()

        meta = json.loads((tmp_path / "metadata.json").read_text())
        assert meta["total_objects"] == 0
        assert meta["total_lines_of_code"] == 0
