#!/usr/bin/env python3
"""
leanix_sync.py
==============
Pushes ABAP repository metadata and business summary to SAP LeanIX.

Uses the **LeanIX REST / GraphQL Fact Sheet API** to upsert an
IT Component (or Application) Fact Sheet with:
  • Description  ← business summary
  • Custom fields ← LoC, object counts, LoB categorisation

Environment variables (set via GitHub Secrets):
  LEANIX_API_TOKEN      - API token (OAuth2 client credentials grant)
  LEANIX_SUBDOMAIN      - e.g. "mycompany" -> mycompany.leanix.net
  LEANIX_WORKSPACE_ID   - target workspace UUID  (optional, for logging)
  LEANIX_FACT_SHEET_ID  - UUID of the Fact Sheet to update
                          If empty the script will attempt to find or
                          create one by name derived from the repo.

Reference:
  https://docs-eam.leanix.net/reference/  (Fact Sheet API)
  https://docs-eam.leanix.net/docs/graphql-api
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(os.environ.get("REPO_ROOT", ".")).resolve()
METADATA_FILE = REPO_ROOT / "metadata.json"
SUMMARY_FILE = REPO_ROOT / "artifacts" / "business_summary.md"

API_TOKEN = os.environ.get("LEANIX_API_TOKEN", "")
SUBDOMAIN = os.environ.get("LEANIX_SUBDOMAIN", "")
WORKSPACE_ID = os.environ.get("LEANIX_WORKSPACE_ID", "")
FACT_SHEET_ID = os.environ.get("LEANIX_FACT_SHEET_ID", "")

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds

# ---------------------------------------------------------------------------
# Auth - OAuth2 client-credentials grant
# ---------------------------------------------------------------------------


def _get_access_token() -> str:
    """Exchange the API token for a short-lived Bearer token."""
    url = f"https://{SUBDOMAIN}.leanix.net/services/mtm/v1/oauth2/token"
    resp = requests.post(
        url,
        data={"grant_type": "client_credentials"},
        auth=("apitoken", API_TOKEN),
        timeout=30,
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


# ---------------------------------------------------------------------------
# GraphQL helpers
# ---------------------------------------------------------------------------


def _graphql(access_token: str, query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL request against the LeanIX Pathfinder API."""
    url = f"https://{SUBDOMAIN}.leanix.net/services/pathfinder/v1/graphql"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 429:
            wait = RETRY_BACKOFF * attempt
            print(f"Rate-limited - retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data: dict = resp.json()
        if data.get("errors"):
            raise RuntimeError(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
        return data
    raise RuntimeError("Exceeded maximum retries due to rate limiting")


# ---------------------------------------------------------------------------
# Find or create Fact Sheet
# ---------------------------------------------------------------------------


def _find_fact_sheet(access_token: str, name: str) -> str | None:
    """Search for an existing Fact Sheet by display name."""
    query = """
    query ($filter: FilterInput!) {
      allFactSheets(filter: $filter) {
        edges { node { id displayName } }
      }
    }
    """
    variables = {
        "filter": {
            "facetFilters": [
                {"facetKey": "FactSheetTypes", "keys": ["ITComponent", "Application"]},
                {"facetKey": "displayName", "keys": [name]},
            ]
        }
    }
    data = _graphql(access_token, query, variables)
    edges = data.get("data", {}).get("allFactSheets", {}).get("edges", [])
    if edges:
        return str(edges[0]["node"]["id"])
    return None


def _create_fact_sheet(access_token: str, name: str, description: str) -> str:
    """Create a new IT Component Fact Sheet and return its ID."""
    mutation = """
    mutation ($input: BaseFactSheetInput!, $patches: [Patch!]!) {
      createFactSheet(input: $input, patches: $patches) {
        factSheet { id displayName }
      }
    }
    """
    variables = {
        "input": {"name": name, "type": "ITComponent"},
        "patches": [
            {
                "op": "replace",
                "path": "/description",
                "value": json.dumps(description),
            }
        ],
    }
    data = _graphql(access_token, mutation, variables)
    fs = data["data"]["createFactSheet"]["factSheet"]
    print(f"✓ Created Fact Sheet '{fs['displayName']}' ({fs['id']})")
    return str(fs["id"])


# ---------------------------------------------------------------------------
# Update Fact Sheet
# ---------------------------------------------------------------------------


def _update_fact_sheet(access_token: str, fs_id: str, description: str, metadata: dict) -> None:
    """Update description and custom fields on an existing Fact Sheet."""
    # Build a tag/comment string for metrics (LeanIX custom fields vary by
    # workspace config, so we encode metrics in the description to stay generic).
    metrics_block = (
        f"\n\n---\n### Repository Metrics\n"
        f"- **Total LoC:** {metadata.get('total_lines_of_code', 'n/a')}\n"
        f"- **Total Objects:** {metadata.get('total_objects', 'n/a')}\n"
        f"- **Categories:** {json.dumps(metadata.get('categories', {}))}\n"
        f"- **Lines of Business:** {json.dumps(metadata.get('lines_of_business', {}))}\n"
        f"- **Last synced:** {metadata.get('generated_at', 'n/a')}\n"
    )

    full_description = description + metrics_block

    # Fetch current revision for optimistic locking
    rev_query = """
    query ($id: ID!) {
      factSheet(id: $id) { id rev }
    }
    """
    rev_data = _graphql(access_token, rev_query, {"id": fs_id})
    revision = rev_data["data"]["factSheet"]["rev"]

    mutation = """
    mutation ($id: ID!, $rev: Long!, $patches: [Patch!]!) {
      updateFactSheet(id: $id, rev: $rev, patches: $patches) {
        factSheet { id displayName rev }
      }
    }
    """
    variables = {
        "id": fs_id,
        "rev": revision,
        "patches": [
            {
                "op": "replace",
                "path": "/description",
                "value": json.dumps(full_description),
            }
        ],
    }
    data = _graphql(access_token, mutation, variables)
    fs = data["data"]["updateFactSheet"]["factSheet"]
    print(f"✓ Updated Fact Sheet '{fs['displayName']}' (rev {fs['rev']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not API_TOKEN or not SUBDOMAIN:
        print("LEANIX_API_TOKEN or LEANIX_SUBDOMAIN not set - skipping LeanIX sync.", file=sys.stderr)
        return

    # Load artefacts
    if not METADATA_FILE.exists():
        print(f"{METADATA_FILE} not found - run generate_metadata.py first.", file=sys.stderr)
        sys.exit(1)

    metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))

    summary = "(No business summary available)"
    if SUMMARY_FILE.exists():
        summary = SUMMARY_FILE.read_text(encoding="utf-8")

    # Authenticate
    access_token = _get_access_token()

    # Resolve Fact Sheet
    fs_id: str | None = FACT_SHEET_ID or None
    repo_name = metadata.get("repository", "ABAP Repository")

    if not fs_id:
        fs_id = _find_fact_sheet(access_token, repo_name)

    if not fs_id:
        print(f"Fact Sheet '{repo_name}' not found - creating a new one.")
        fs_id = _create_fact_sheet(access_token, repo_name, summary)

    _update_fact_sheet(access_token, fs_id, summary, metadata)

    print("✓ LeanIX sync complete.")


if __name__ == "__main__":
    main()
