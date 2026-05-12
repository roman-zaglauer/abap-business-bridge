# ABAP Business Bridge – Installation & Configuration Guide

## Prerequisites

| Requirement                        | Version               |
| ---------------------------------- | --------------------- |
| GitHub repository (abapGit layout) | any                   |
| Python                             | ≥ 3.10                |
| GitHub Actions                     | enabled               |
| SAP LeanIX workspace               | active                |
| GitHub Copilot subscription        | Business / Enterprise |

---

## 1. GitHub Secrets

Navigate to **Settings → Secrets and variables → Actions** in your repository and create the following secrets:

### 1.1 `COPILOT_TOKEN`

A GitHub **Personal Access Token (classic)** or a **Fine-Grained PAT** with the `copilot` scope enabled.

- Go to <https://github.com/settings/tokens>
- Select **"Generate new token (classic)"**
- Enable scope: **`copilot`**
- Copy the token and save it as the `COPILOT_TOKEN` secret.

> **Alternative:** If you use the [GitHub Copilot for Business API](https://docs.github.com/en/copilot/building-copilot-extensions/building-a-copilot-agent-for-your-copilot-extension), you can use the organisation-level Copilot API token instead.

### 1.2 `LEANIX_API_TOKEN`

An API token from your LeanIX workspace:

1. Log in to **LeanIX** → **Administration → API Tokens**.
2. Click **Create new API Token**.
3. Grant permission scope: **MEMBER** (minimum) or **ADMIN** for Fact Sheet creation.
4. Copy the token and store it as `LEANIX_API_TOKEN`.

### 1.3 `LEANIX_SUBDOMAIN`

Your LeanIX instance subdomain. If your workspace URL is `https://acme.leanix.net`, set this to `acme`.

### 1.4 `LEANIX_WORKSPACE_ID`

The UUID of your target LeanIX workspace. Find it under **Administration → Workspaces** in LeanIX.

### 1.5 `LEANIX_FACT_SHEET_ID` _(optional)_

The UUID of the IT Component / Application Fact Sheet to update. If omitted, the pipeline will search for a Fact Sheet matching the repository name, or create one automatically.

---

## 2. Repository Permissions

### 2.1 `GITHUB_TOKEN` (built-in)

The workflow uses the default `GITHUB_TOKEN`. Ensure the following is configured:

1. Go to **Settings → Actions → General**.
2. Under **Workflow permissions**, select **"Read and write permissions"**.
3. Check **"Allow GitHub Actions to create and approve pull requests"** (optional, for PR-based flows).

### 2.2 Token scope summary

| Secret             | Required Scope      | Used By                           |
| ------------------ | ------------------- | --------------------------------- |
| `GITHUB_TOKEN`     | `contents: write`   | Commit & push updated files       |
| `COPILOT_TOKEN`    | `copilot`           | AI summary & changelog generation |
| `LEANIX_API_TOKEN` | API Token (MEMBER+) | LeanIX Fact Sheet upsert          |

---

## 3. Repository Layout

The pipeline expects an **abapGit-style** repository layout:

```
src/
├── z_my_class.clas.abap
├── z_my_report.prog.abap
├── z_my_cds.ddls.asddls
└── ...
```

ABAP objects should use the standard abapGit file extensions (`.clas.abap`, `.prog.abap`, `.fugr.abap`, `.tabl.abap`, `.ddls.asddls`, etc.).

---

## 4. First Run

1. Push code to the `main` branch (or trigger the workflow manually via **Actions → ABAP Business Bridge Sync → Run workflow**).
2. The pipeline will:
   - Scan ABAP sources and produce `metadata.json`.
   - Call Copilot to generate a business summary and changelog.
   - Inject both into `README.md`.
   - Push metadata to your LeanIX workspace.
   - Commit the updated `README.md` and `metadata.json` (with `[skip ci]` to avoid loops).

---

## 5. Customisation

### Changing the Copilot prompts

Edit the system prompts in [`scripts/copilot_summarize.py`](scripts/copilot_summarize.py) to tailor the tone, structure, or depth of the AI-generated summaries.

### Adding custom LoB patterns

Edit `LOB_PATTERNS` in [`scripts/generate_metadata.py`](scripts/generate_metadata.py) to add company-specific naming conventions.

### LeanIX Fact Sheet type

The default type is `ITComponent`. If your workspace uses `Application`, change the `type` value in `_create_fact_sheet()` inside [`scripts/leanix_sync.py`](scripts/leanix_sync.py).

---

## 6. Troubleshooting

| Problem                               | Solution                                                                                |
| ------------------------------------- | --------------------------------------------------------------------------------------- |
| `COPILOT_TOKEN not set` warning       | Ensure the secret is created and spelled correctly.                                     |
| `401 Unauthorized` from LeanIX        | Regenerate the API token; ensure it has MEMBER permissions.                             |
| `429 Too Many Requests`               | The script retries automatically up to 3 times with exponential backoff.                |
| Commit step shows "nothing to commit" | No changes were detected — this is expected when sources haven't changed.               |
| Fact Sheet not found & creation fails | Check that your LeanIX token has ADMIN scope, or set `LEANIX_FACT_SHEET_ID` explicitly. |
