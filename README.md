# ABAP Business Bridge

> Automated CI/CD pipeline that bridges SAP ABAP code with business stakeholders and SAP LeanIX Enterprise Architecture.

[![ABAP Business Bridge Sync](https://img.shields.io/badge/ABAP%20Sync-passing-brightgreen?logo=githubactions&logoColor=white)](../../actions/workflows/abap-sync.yml)
[![Tests & Quality](https://img.shields.io/badge/Tests%20%26%20Quality-passing-brightgreen?logo=pytest&logoColor=white)](../../actions/workflows/tests.yml)
[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-ABAP%20Business%20Bridge-blue?logo=github)](https://github.com/marketplace/actions/abap-business-bridge)

## What is this?

This pipeline automatically:

1. **Scans** ABAP source code and produces structured metadata (LoC, object types, SAP module alignment).
2. **Generates** a non-technical business summary using GitHub Copilot AI.
3. **Creates** a human-readable changelog from git diffs.
4. **Syncs** all metadata to SAP LeanIX Fact Sheets via the REST/GraphQL API.
5. **Commits** the updated README and metadata back to the repository.

## Quick Start

```yaml
- uses: roman-zaglauer/abap-business-bridge@v1
  with:
    copilot-token: ${{ secrets.COPILOT_TOKEN }}
    leanix-api-token: ${{ secrets.LEANIX_API_TOKEN }}
    leanix-subdomain: ${{ secrets.LEANIX_SUBDOMAIN }}
```

## Setup

See the [Installation & Configuration Guide](docs/SETUP.md).

## Business Summary

<!-- BUSINESS_SUMMARY_START -->

_(Business summary will be auto-generated on the next pipeline run.)_

<!-- BUSINESS_SUMMARY_END -->

## Changelog

<!-- CHANGELOG_START -->

_(Changelog will be auto-generated on the next pipeline run.)_

<!-- CHANGELOG_END -->

## Architecture Enhancements

See [docs/ENHANCEMENTS.md](docs/ENHANCEMENTS.md) for advanced ideas (ABAPLint, Mermaid diagrams, MCP servers, and more).

## Support & Donations

If you find this action useful, consider supporting its development:

[![Sponsor](https://img.shields.io/badge/Sponsor-roman--zaglauer-ea4aaa?logo=github-sponsors)](https://github.com/sponsors/roman-zaglauer)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/roman.zaglauer)

## Author

**Roman Zaglauer**

- Website: [rgz.digital](https://rgz.digital)
- GitHub: [@roman-zaglauer](https://github.com/roman-zaglauer)

## License

MIT
