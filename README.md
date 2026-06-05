[![MIT License](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![CC-BY 4.0](https://img.shields.io/badge/Data-CC--BY_4.0-lightgrey.svg)](LICENSE-data)
![Last Updated](https://img.shields.io/badge/updated-2026--05--29-success)

# Orgschema Framework

A schema validator for [Organizational Schema Theory](https://github.com/spectralbranding/orgschema-demo) specifications -- reverse-design TDD for business operations.

## What is Orgschema?

Organizational Schema Theory is a methodology where businesses are designed **backward** from customer experience goals using testable, version-controlled YAML specifications. Each operational layer validates the layer above it, forming a multi-level TDD cascade:

```
L0: Customer Experience Contract  →  acceptance tests
L1: Signal Requirements           →  integration tests
L2: Process Contracts              →  unit tests
L3: Procedures                     →  implementation
L4: Input Specifications           →  dependencies
L5: Sourcing Requirements          →  infrastructure
```

This framework provides the **validation tooling**: JSON schemas and a CLI validator that checks your specifications for structural correctness, cross-reference integrity, signal coverage, and experience traceability.

## Installation

Requires Python 3.12+.

```bash
# Clone the framework
git clone https://github.com/spectralbranding/orgschema-framework.git
cd orgschema-framework

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## Quick Start

Validate the [Spectra Coffee demo](https://github.com/spectralbranding/orgschema-demo) specifications:

```bash
# Clone the demo repository
git clone https://github.com/spectralbranding/orgschema-demo.git

# Run the validator against it
orgschema-validate ./orgschema-demo
```

Expected output (all levels passing):

```
=== Orgschema TDD Cascade Validator ===
Validating: ./orgschema-demo

Level 1: Schema Validation
  [PASS] organization.yaml
  [PASS] products/espresso.yaml
  [PASS] products/oat_latte.yaml
  ...

Level 2: Cross-Reference Integrity
  [PASS] All satisfies_signal references resolve
  [PASS] All satisfies_experience references resolve

Level 4: Signal Coverage
  [PASS] All 18 signal requirements have satisfying specifications

Level 5: Experience Traceability
  [PASS] All products trace to experience goals
  [PASS] All processes trace to experience goals

Results: 0 errors, 0 warnings
```

## Validation Levels

The validator implements all 6 TDD cascade validation levels:

| Level | Name | What It Checks |
|:------|:-----|:---------------|
| 1 | Schema Validation | YAML files conform to JSON Schema (structure, types, required fields) |
| 2 | Cross-Reference Integrity | `satisfies_signal` and `satisfies_experience` annotations reference valid targets |
| 3 | Contract Satisfaction | Every declared L0 `constraint_contracts` / `commitment_contracts` is satisfied: its `validated_by` provider exists, every `satisfies_constraint` / `satisfies_commitment` reference resolves to a declared contract of the matching kind, and no declared contract is left uncovered |
| 4 | Signal Coverage | Every signal requirement in `perception/signal_requirements.yaml` has at least one satisfying specification |
| 5 | Experience Traceability | Every product and process traces upward to an L0 customer experience goal |
| 6 | Waste Detection | Declared units that are never consumed: orphaned `organization.yaml` roles, unconsumed products (no `implemented_by`, no references), empty contracts (no `requires`), and duplicate `implemented_by` allocations |

Levels 1–3 emit **errors** (non-zero exit code); Levels 4–6 emit advisory **warnings**.

## Deterministic Query CLI

`orgschema-query` is a plain deterministic query interface over the Level 3 and Level 6 checks — there is **no natural-language / LLM layer**. OrgSchema's constraint space is boolean (a contract is satisfied or it is not; a unit is consumed or it is not), so the appropriate interface is a deterministic query rather than a grounded NL→DSL pipeline. Results are exactly the validator's, so the two tools never disagree.

```bash
# Run all deterministic checks (contracts + waste) over a schema
orgschema-query --schema ./orgschema-demo

# Run a single check
orgschema-query --schema ./orgschema-demo --check contracts
orgschema-query --schema ./orgschema-demo --check waste

# Select by level number (3 = contracts, 6 = waste)
orgschema-query --schema ./orgschema-demo --level 6

# Machine-readable JSON output (for CI / tooling)
orgschema-query --schema ./orgschema-demo --format json
```

Exit code is `1` when an error-severity check (contracts) reports a violation, else `0` — usable in CI alongside `orgschema-validate`.

## Schemas

Four JSON Schema files define the structure of orgschema specifications:

| Schema | Validates | Required Fields |
|:-------|:----------|:----------------|
| `organization.json` | `organization.yaml` | name, type, version |
| `product.json` | `products/*.yaml` | version, id, name, category, available |
| `process.json` | `processes/*.yaml` | version |
| `compliance.json` | `compliance/*.yaml` | version |

All schemas use JSON Schema Draft 2020-12 and allow additional properties for extensibility.

### Key Patterns

**Product IDs** must be lowercase with underscores: `^[a-z][a-z0-9_]*$`

**Version strings** follow semver: `^\d+\.\d+\.\d+$`

**Signal references** link to L1: `satisfies_signal: ["L1_taste_quality", "L1_craft_preparation"]`

**Experience references** link to L0: `satisfies_experience: ["L0_product_excellence"]`

## Project Structure

```
orgschema-framework/
├── orgschema_framework/
│   ├── __init__.py
│   ├── validate.py          # CLI validator (6 validation levels)
│   ├── query.py             # Deterministic query CLI (orgschema-query)
│   └── schemas/
│       ├── compliance.json
│       ├── organization.json
│       ├── process.json
│       └── product.json
├── CITATION.cff
└── pyproject.toml
```

## CI/CD Integration

Add the validator to your GitHub Actions workflow:

```yaml
- name: Validate orgschema specifications
  run: |
    pip install -e path/to/orgschema-framework
    orgschema-validate .
```

The validator returns exit code 1 on errors, making it suitable for CI/CD pipelines. Warnings are non-fatal.

See [orgschema-demo/.github/workflows/ci.yml](https://github.com/spectralbranding/orgschema-demo/blob/main/.github/workflows/ci.yml) for a working example.

## Writing Your First Specification

Start with `organization.yaml`:

```yaml
name: "My Coffee Shop"
type: "food_and_beverage"
version: "0.1.0"
mission: "Serve excellent coffee with transparency"
```

Then specify a product:

```yaml
version: "0.1.0"
id: "espresso"
name: "Espresso"
category: "hot_beverage"
available: true

preparation:
  method: "espresso_extraction"
  equipment: ["espresso_machine", "grinder"]

ingredients:
  coffee_beans:
    origin: "Ethiopia"
    weight_g: 18

pricing:
  price: 3.50
  currency: "EUR"

satisfies_signal:
  - "L1_taste_quality"
  - "L1_craft_preparation"

satisfies_experience:
  - "L0_product_excellence"
```

Run `orgschema-validate .` to check your work. The validator will tell you what is missing or misconfigured.

## Related Projects

- **[orgschema-demo](https://github.com/spectralbranding/orgschema-demo)** -- Spectra Coffee: a complete demonstration of the orgschema methodology (25 YAML files, 6 products, full TDD cascade)
- **[sbt-framework](https://github.com/spectralbranding/sbt-framework)** -- Spectral Brand Theory: the perception measurement framework that provides orgschema's L0-L1 test specification language

## Citation

If you use this framework in academic work:

```bibtex
@software{zharnikov2026orgschema,
  author = {Zharnikov, Dmitri},
  title = {Organizational Schema Theory Framework},
  year = {2026},
  url = {https://github.com/spectralbranding/orgschema-framework},
  version = {0.1.0}
}
```

See `CITATION.cff` for the full citation metadata.

## License

MIT

---

## 1 | Getting Started

Clone the repository and enter the directory:

```bash
git clone https://github.com/spectralbranding/orgschema-framework.git
cd orgschema-framework
```

Python dependencies are managed via `uv` (Python ≥ 3.12):

```bash
uv sync --extra dev
```

The project anchor is `pyproject.toml` at the repository root.

---

## 2 | Project Layout

```
.
├── orgschema_framework/    # Python package (CLI validator + JSON schemas)
│   ├── __init__.py
│   ├── validate.py
│   └── schemas/
│       ├── compliance.json
│       ├── organization.json
│       ├── process.json
│       └── product.json
├── output/                 # Generated artifacts
│   ├── figures/
│   ├── tables/
│   └── logs/               # reproduce.sh master_run.log lands here
├── CITATION.cff            # Machine-readable citation
├── LICENSE                 # MIT (code)
├── LICENSE-data            # CC BY 4.0 (data + figures + schemas)
├── pyproject.toml          # Python project anchor + dependencies
├── reproduce.sh            # Single-command reproduction
├── README.md               # This file
└── .gitignore              # Excludes secrets, env, build artifacts
```

---

## 3 | Quick Start

Reproduce dependency install + test suite + CLI smoke check:

```bash
./reproduce.sh
```

The script runs `uv sync --extra dev`, executes the pytest suite (if any tests are collected), verifies the `orgschema-validate` CLI installs, and logs run details to `output/logs/master_run.log`.

To validate a target specifications directory directly, see the "Quick Start" section above.

---

## 4 | Dependencies

### Python ≥ 3.12

Runtime dependencies (pinned in `pyproject.toml`):

- `pyyaml >= 6.0`
- `jsonschema >= 4.20.0`

Development dependencies (install via `uv sync --extra dev`):

- `pytest >= 7.0`
- `black >= 24.0`, `flake8 >= 7.0`, `mypy >= 1.8`
- `types-PyYAML`

Install with `uv sync` (runtime) or `uv sync --extra dev` (with dev tools).

---

## 5 | Script Map

| Block | Entry point | Inputs | Outputs |
|-------|-------------|--------|---------|
| Validation CLI | `orgschema-validate <path>` | YAML specs at `<path>` | stdout PASS/FAIL summary; exit code 0/1 |
| Query CLI | `orgschema-query --schema <path>` | YAML specs at `<path>` | structural text/JSON of L3/L6 violations; exit code 0/1 |
| Schema files | `orgschema_framework/schemas/*.json` | — | Reused by `validate.py` |
| Test suite | `pytest` | `tests/` (if present) | `output/logs/master_run.log` |
| Full reproduction | `./reproduce.sh` | repo root | `output/logs/master_run.log` |

---

## 6 | Citation

If you build on this framework, please cite:

> Dmitry Zharnikov (2026). "Organizational Schema Theory Framework." https://github.com/spectralbranding/orgschema-framework

Machine-readable citation: see [`CITATION.cff`](CITATION.cff). GitHub's "Cite this repository" button, Zotero, Mendeley, and Pandoc all read this format natively.

---

## 7 | Licence

- **Code** — © Dmitry Zharnikov, 2026. [MIT Licence](LICENSE).
- **Data, schemas, figures, tables** — © Dmitry Zharnikov, 2026. [CC BY 4.0](LICENSE-data).

Both licences permit reuse with attribution. The MIT Licence permits modification and redistribution of code; CC BY 4.0 permits any reuse of data, schemas, and rendered artifacts with attribution to the author.

---

*Last updated: 2026-05-29*
