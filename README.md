# SFSC - Steel Fan Support Calc

SFSC is a Streamlit-based engineering application for sizing and verifying steel supports for industrial fans. The project combines load evaluation, seismic inputs, steel section selection, support verification, base plate checks, anchor checks, and exportable engineering reports in a single workflow.

The repository is structured for both developer usage and portable Windows desktop distribution. It includes the calculation engine, YAML-based catalogs, test coverage, PyInstaller packaging, a native desktop shell, and a PowerShell release publishing script.

## Highlights

- Support sizing and verification workflows from the same interface
- Multiple support families: `hanger`, `cantilever_1`, `cantilever_2`, `cantilever_3`, `pedestal`, `combined`, and `platform_frame_braced` (braced platform frame, recommended for Robot-type models)
- Per-module utilization breakdown (steel section, base plate, anchors, connections) with an independent status per module and a clearly separated global governing check
- Optional calculation modules (dynamic factor, biaxial bending, lateral-torsional buckling, base plate, concrete anchors, steel connections, seismic, serviceability) that actually gate the calculation and are recorded in the traceability hash
- Fixation to concrete (EN 1992-4 anchors) **or** to existing steel structure (EN 1993-1-8 steel-to-steel connections)
- Walking surface (grating/tramex/plate) modelled as a load-distribution surface — never confused with a base plate
- Robot benchmark calculation mode (bare member, no base plate/anchors/connections/seismic)
- Trilingual interface and reports (PT / EN / ES) via i18n keys
- Country and code-aware behavior for Portugal, Spain, Ireland, UK, France, Brazil, Chile, and generic EU cases
- Steel section selection from catalog data for `HEA`, `HEB`, `IPE`, `UPN`, and `RHS`
- Base plate and anchor checks when enabled
- Export outputs in PDF, Excel, and CSV
- Portable Windows desktop packaging with PyInstaller
- Native desktop window powered by `pywebview`, without opening Chrome or another browser tab
- Automated GitHub Release publication for desktop artifacts

## Repository Structure

```text
.
|-- app.py
|-- src/sfsc/
|   |-- catalogs/
|   |-- engines/
|   |-- reports/
|   `-- ui/
|-- data/catalogs/
|-- tests/
|-- build_desktop/
|   |-- sfsc.spec
|   `-- publish_release.ps1
|-- assumptions.yaml
|-- seismic_zones.yaml
|-- standards_registry.yaml
`-- steel_grades.yaml
```

## Functional Scope

The application currently supports:

- Interactive input for project data, fan units, geometry, seismic zone, steel grade, anti-vibration configuration, and optional base plate design
- Section recommendation and verification using the internal calculation engine
- Engineering outputs grouped into section checks, base plate checks, anchor checks, combinations, warnings, and references
- Report generation for PDF calculation memoranda, Excel workbooks, and CSV summary files
- Classification of results including `PASS`, `FAIL`, `MARGINAL`, and `REQUIRES_SPECIALIST`

### Weight scope policy

The supported operating range is governed by a single policy (`src/sfsc/policy.py`), applied consistently in validation, classification, UI, and reports:

| Total operating weight | Behaviour |
|---|---|
| < 35 kg | Allowed with warning — result classified `PRELIMINARY` |
| 35 – 500 kg | Validated product range — `ENGINEERING_ESTIMATE` |
| 500 – 600 kg | Allowed — result classified `REQUIRES_SPECIALIST` |
| 600 – 1000 kg | Outside the product range — requires explicit user confirmation; `REQUIRES_SPECIALIST` |
| > 1000 kg | Blocked (`OutOfScopeError`) |

Any result classified `REQUIRES_SPECIALIST` must be reviewed by a qualified structural engineer before use.

## Requirements

- Python `3.10+`
- Windows is recommended for portable desktop packaging
- Optional tooling for distribution: `pyinstaller`

## Getting Started

### 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

Runtime only:

```powershell
pip install -r requirements.txt
```

For development and tests (also installs Ruff, mypy, and pre-commit):

```powershell
pip install -e .[dev]
pre-commit install
```

For the portable desktop build (PyInstaller + pywebview):

```powershell
pip install -r requirements-build.txt
```

### 3. Run the application

```powershell
streamlit run app.py
```

There is also a convenience launcher for Windows:

```powershell
.\Start SFSC.bat
```

By default, the batch launcher starts Streamlit on port `8502`.

## Testing

Run the automated test suite with:

```powershell
pytest
```

The repository includes coverage for section catalogs, steel grades, seismic data, loads, section verification, and end-to-end calculation flows.

Numerical regression is protected by a reference-case library in `validation_cases/` — each case ships a hand-calculated memo (`memoria.md`) that justifies the expected values; see `validation_cases/README.md`.

## Code Quality

CI (GitHub Actions) runs Ruff lint/format checks, mypy, and the test suite with a coverage gate (≥85%) on every push. Locally:

```powershell
ruff check src tests
ruff format --check src tests
mypy src/sfsc
pytest --cov=src/sfsc
```

## Portable Desktop Build

### Build the portable executable

```powershell
pyinstaller build_desktop\sfsc.spec --noconfirm
```

This produces a portable executable at:

```text
dist\SFSC.exe
```

The executable runs as a standalone desktop application. It starts its internal Streamlit backend on `127.0.0.1`, opens the interface inside a native app window, and does not install files into `%LOCALAPPDATA%` or create Start Menu entries.

## Release Workflow

The repository includes a release helper script:

```powershell
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_desktop\publish_release.ps1
```

The script resolves the GitHub repository from `origin`, reads credentials from the configured Git credential helper, creates the GitHub Release if needed, and uploads the portable executable.

## Generated Outputs

At runtime, the application can generate:

- PDF calculation memorandum
- Excel workbook with summary, combinations, section data, base plate data, and anchor data
- CSV one-line summary for downstream workflows

At packaging time, the project can generate:

- `dist\SFSC.exe` portable Windows executable

## Engineering and Usage Notes

- This software is intended to support engineering workflows, not replace engineering judgment.
- National code behavior depends on the embedded enums, assumptions, and YAML datasets shipped with the repository.
- Results outside the covered scope may be marked as `REQUIRES_SPECIALIST` or include warnings and limitations in the report context.
- Before using the tool in production, confirm the assumptions, catalogs, and standards data match your governing design basis and internal QA process.

## Reports and Traceability

Every output (PDF, Excel, CSV) carries the software version and a dataset
provenance fingerprint (SHA-256 + modification date of each YAML), so a report
can be traced to the exact data it was computed from. The PDF memorandum
includes a cover page, an executive summary, a formula memory (intermediate
values for the governing checks), a traceability section, and a signature
block; it is watermarked **PRELIMINAR — NÃO APROVADO** whenever the result is
not a clean `PASS` or is classified `REQUIRES_SPECIALIST`. Exporting requires
the responsible engineer's name (it appears on the cover and signature block).

Both sizing (`DIMENSION`) and verification (`VERIFY`) modes are available from
the interface.

## Development Notes

- Main entry point: `app.py`
- UI layer: `src/sfsc/ui/streamlit_app.py` (thin orchestrator) + `src/sfsc/ui/components/`
- Core calculation orchestration: `src/sfsc/engines/selector.py`
- YAML-backed configuration and dataset provenance: `src/sfsc/config.py`
- Packaging scripts and assets: `build_desktop/`

## License

This repository is distributed under the proprietary license in [LICENSE](LICENSE).

Copyright (c) 2026 Tensor - Construcao Civil Lda. All rights reserved.
