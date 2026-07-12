# Changelog

## [Unreleased]

### Changed

- Added macOS Intel and Apple Silicon integration smoke tests with pinned Feishu CLI installation, UTF-8 paths, archive permissions, and installed-Skill checks.
- Whiteboard CLI discovery now requires both version and help commands to succeed.

## [1.0.0] - 2026-07-11

### Added

- Complete-source OCR and framework-first course-note workflow.
- Editable Feishu SVG whiteboards with 13 semantic layout variants.
- Semantic key-point highlighting with a 30% document-level guardrail.
- Highlight inventory coverage auditing and long-source batch manifests.
- Diagram candidate scoring based on explicit relationship signals.
- User-identity Feishu create/update wrappers with dry-run, revision, and block checks.
- Automatic pre-update document snapshots.
- Deterministic self-tests, release packaging, and isolated installation support.
- Cross-platform Python entry points with Windows PowerShell and macOS Bash wrappers.
- First-use dependency, Feishu authentication, MCP capability, UTF-8, and temporary-directory checks.
- ZIP and tar.gz release archives with SHA-256 checksums and an allowlist-based package builder.
- Windows and macOS CI matrix with Unicode-path installation, backup, and rollback tests.

### Safety

- No automatic bot-identity, image, new-document, or format fallback.
- No automatic restore from snapshots or overwrite of user-edited documents.
- No silent dependency installation, account login, backend switch, or MCP capability assumption.
