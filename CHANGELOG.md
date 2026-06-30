# Changelog

All notable changes to SpeedDeploy are documented here using a simple Keep a Changelog style.

## Unreleased

### Added

- Future changes will be listed here.

## 0.5.0 - 2026-06-28

### Added

- Automated test coverage for the V1 and V2 flows.
- GitHub Actions CI with install, lint, tests, and CLI smoke checks.
- Bounded Python dependencies and a development requirements file.
- Hardened SSL provisioning with non-interactive Certbot commands.
- Hardened Gunicorn, Apache, and Nginx templates.
- `speeddeploy v2 audit` for preflight diagnostics.
- Persistent deployment state in `.speeddeploy/state.json`.
- `speeddeploy v2 info` for release and deployment state inspection.
- `speeddeploy v2 rollback --to <release>` for targeted rollback.
- `system_packages` and `system_user` controls in V2 project YAML.
- `speeddeploy v2 diagnose` for service, logs, healthcheck, and deployment-state inspection.
- Detailed documentation pages under `docs/`.

### Changed

- Release deployments now record success, failure, and rollback status.
- Project examples were aligned with the current V2 schema.
- The README now points to focused documentation pages.

## 0.1.0

Initial SpeedDeploy release line for the existing V1 workflow and the V2 foundation.
