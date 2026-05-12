#!/usr/bin/env python3
"""
generate_metadata.py
====================
Scans the ABAP repository to produce ``metadata.json`` containing:
  • Lines of Code (LoC) per object and total.
  • Object categorisation (Class, Report, CDS View, Function Group, …).
  • Inferred Line of Business (LoB) based on naming conventions.

The output file ``metadata.json`` is written to the repository root.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
from collections import defaultdict
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(os.environ.get("REPO_ROOT", ".")).resolve()
OUTPUT_FILE = REPO_ROOT / "metadata.json"

# ---------------------------------------------------------------------------
# Object type detection
# ---------------------------------------------------------------------------
# abapGit stores objects in folders like  src/<package>/<name>.<type>.abap
ABAP_TYPE_MAP: dict[str, str] = {
    ".clas.abap": "Class",
    ".intf.abap": "Interface",
    ".prog.abap": "Report",
    ".fugr.abap": "Function Group",
    ".tabl.abap": "Table / Structure",
    ".dtel.abap": "Data Element",
    ".doma.abap": "Domain",
    ".msag.abap": "Message Class",
    ".ttyp.abap": "Table Type",
    ".enho.abap": "Enhancement",
    ".enhs.abap": "Enhancement Spot",
    ".shlp.abap": "Search Help",
    ".tran.abap": "Transaction",
    ".xslt.abap": "XSLT Transformation",
}

# CDS views are typically stored as .ddls.asddls or .ddls.asdefinition
CDS_EXTENSIONS = {".ddls.asddls", ".ddls.asdefinition", ".dcls.asdcls", ".ddlx.asddlxs"}

# ---------------------------------------------------------------------------
# LoB inference heuristics (SAP module prefixes / naming patterns)
# ---------------------------------------------------------------------------
LOB_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(^|[_/])FI($|[_/])", re.I), "Finance (FI)"),
    (re.compile(r"(^|[_/])CO($|[_/])", re.I), "Controlling (CO)"),
    (re.compile(r"(^|[_/])SD($|[_/])", re.I), "Sales & Distribution (SD)"),
    (re.compile(r"(^|[_/])MM($|[_/])", re.I), "Materials Management (MM)"),
    (re.compile(r"(^|[_/])PP($|[_/])", re.I), "Production Planning (PP)"),
    (re.compile(r"(^|[_/])HR($|[_/])", re.I), "Human Resources (HR)"),
    (re.compile(r"(^|[_/])HCM($|[_/])", re.I), "Human Capital Management (HCM)"),
    (re.compile(r"(^|[_/])PM($|[_/])", re.I), "Plant Maintenance (PM)"),
    (re.compile(r"(^|[_/])QM($|[_/])", re.I), "Quality Management (QM)"),
    (re.compile(r"(^|[_/])WM($|[_/])", re.I), "Warehouse Management (WM)"),
    (re.compile(r"(^|[_/])EWM($|[_/])", re.I), "Extended Warehouse Management (EWM)"),
    (re.compile(r"(^|[_/])PS($|[_/])", re.I), "Project System (PS)"),
    (re.compile(r"(^|[_/])CS($|[_/])", re.I), "Customer Service (CS)"),
    (re.compile(r"(^|[_/])LE($|[_/])", re.I), "Logistics Execution (LE)"),
    (re.compile(r"(^|[_/])RE($|[_/])", re.I), "Real Estate (RE)"),
    (re.compile(r"(^|[_/])TR($|[_/])", re.I), "Treasury (TR)"),
    (re.compile(r"(^|[_/])BW($|[_/])", re.I), "Business Warehouse (BW)"),
    (re.compile(r"(^|[_/])CRM($|[_/])", re.I), "Customer Relationship Management (CRM)"),
    (re.compile(r"(^|[_/])SRM($|[_/])", re.I), "Supplier Relationship Management (SRM)"),
    (re.compile(r"(^|[_/])BC($|[_/])", re.I), "Basis / Cross-Application (BC)"),
]


def _classify_file(path: pathlib.Path) -> str | None:
    """Return the ABAP object type or None if not an ABAP artefact."""
    name = path.name.lower()
    for ext, obj_type in ABAP_TYPE_MAP.items():
        if name.endswith(ext):
            return obj_type
    for cds_ext in CDS_EXTENSIONS:
        if name.endswith(cds_ext):
            return "CDS View"
    # Plain .abap without a known qualifier - count as generic ABAP source
    if name.endswith(".abap"):
        return "ABAP Source"
    return None


def _infer_lob(path: pathlib.Path) -> str:
    """Infer the SAP Line of Business from file path or name."""
    candidate = str(path.relative_to(REPO_ROOT))
    for pattern, lob in LOB_PATTERNS:
        if pattern.search(candidate):
            return lob
    return "Cross-Application / Unknown"


def _count_lines(path: pathlib.Path) -> int:
    try:
        return len(path.read_text(errors="replace").splitlines())
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    objects: list[dict] = []
    category_counts: dict[str, int] = defaultdict(int)
    lob_counts: dict[str, int] = defaultdict(int)
    total_loc = 0

    for p in sorted(REPO_ROOT.rglob("*")):
        if not p.is_file():
            continue
        obj_type = _classify_file(p)
        if obj_type is None:
            continue

        loc = _count_lines(p)
        lob = _infer_lob(p)
        total_loc += loc
        category_counts[obj_type] += 1
        lob_counts[lob] += 1
        objects.append(
            {
                "path": str(p.relative_to(REPO_ROOT)),
                "type": obj_type,
                "lines_of_code": loc,
                "line_of_business": lob,
            }
        )

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": os.environ.get("GITHUB_REPOSITORY", REPO_ROOT.name),
        "total_lines_of_code": total_loc,
        "total_objects": len(objects),
        "categories": dict(category_counts),
        "lines_of_business": dict(lob_counts),
        "objects": objects,
    }

    OUTPUT_FILE.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ metadata.json written ({len(objects)} objects, {total_loc} LoC)")


if __name__ == "__main__":
    main()
