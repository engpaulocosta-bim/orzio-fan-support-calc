# SFSC Desktop Release Checklist

Use this checklist before distributing `SFSC.exe` or a portable ZIP package.

## Automated Validation

- [ ] `pytest -q` passes with coverage at or above 85%.
- [ ] `pip install -e .[dev]` succeeds in a fresh virtual environment.
- [ ] `ruff check` passes without new errors.
- [ ] `ruff format --check` passes.
- [ ] `mypy src/sfsc` passes without new errors.
- [ ] `validation_cases/` remain within documented tolerances.

## Desktop Build

- [ ] Build on a clean Windows machine or runner:
  `pyinstaller build_desktop/sfsc.spec --noconfirm`.
- [ ] The build log shows no machine-specific absolute path overrides.
- [ ] `dist/SFSC.exe` exists and is non-empty.
- [ ] `dist/SFSC_v<version>_Windows_Portable.zip` exists and is non-empty.
- [ ] File size is recorded and compared with the previous release.
- [ ] Windows file details show the same version as `pyproject.toml`.

## Smoke Tests

- [ ] The executable opens a native window without a console error.
- [ ] The backend starts on `127.0.0.1`; if port `8502` is occupied, the next free port is used.
- [ ] The default hanger case calculates successfully.
- [ ] A PDF export downloads from the embedded WebView.
- [ ] An Excel export downloads and contains all expected sheets, including warnings/assumptions.
- [ ] A CSV export opens correctly in Excel with classification and disclaimer columns.

## Engineering Review

- [ ] One `PASS` case is checked against an independent calculation memo.
- [ ] One `REQUIRES_SPECIALIST` case is checked against an independent calculation memo.
- [ ] PDF cover, provenance, disclaimer, and watermark behavior are inspected.
- [ ] The release notes state the weight scope policy and specialist-review limitation.

## Release Publication

- [ ] `CHANGELOG.md` is updated or release notes explicitly describe the changes.
- [ ] The git tag is created from the intended target branch/commit.
- [ ] `build_desktop/publish_release.ps1` is run with the intended `-TargetCommitish`, or the detected default branch is confirmed.
- [ ] Uploaded assets match the local SHA-256 hashes.
- [ ] VirusTotal or equivalent antivirus scan is recorded.
- [ ] Release notes include false-positive guidance for Windows SmartScreen/antivirus warnings.
- [ ] `LICENSE` and the disclaimer are visible in the package notes or release body.
