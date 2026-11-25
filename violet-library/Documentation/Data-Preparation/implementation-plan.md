# Implementation plan — 2026-11-14

This plan implements the approved data-preparation phase on branch `prepare-doab-data`.

| Step | Files | Verification |
| --- | --- | --- |
| Define package and schema | `pyproject.toml`, `src/libraries_data/schema.py`, tests | Schema and field mapping tests |
| Stream and validate DOAB's full export | `src/libraries_data/source.py`, tests | Synthetic multiline CSV and changed-header tests |
| Normalize book records | `src/libraries_data/records.py`, tests | Multilingual text, multi-value fields, deduplication, edition tests |
| Write catalog and quality report | `src/libraries_data/prepare.py`, tests | End-to-end synthetic feed and small-feed rejection |
| Publish a checked result | `src/libraries_data/publish.py`, tests | Local artifact checks; no network publish in tests |
| Automate and document | `.github/workflows/*.yml`, README, Documentation | Lint, tests, workflow run, remote artifact inspection |

The workflow can be started manually, or by changes to data-preparation code, dependencies, or the workflow on `main`. Documentation-only changes do not download the full feed. It runs quality checks before any Hugging Face write. Publish is a separate command so teammates can test preparation without credentials.
