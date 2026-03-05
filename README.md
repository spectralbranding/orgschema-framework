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

The validator implements 4 of the 6 TDD cascade validation levels:

| Level | Name | What It Checks |
|:------|:-----|:---------------|
| 1 | Schema Validation | YAML files conform to JSON Schema (structure, types, required fields) |
| 2 | Cross-Reference Integrity | `satisfies_signal` and `satisfies_experience` annotations reference valid targets |
| 4 | Signal Coverage | Every signal requirement in `perception/signal_requirements.yaml` has at least one satisfying specification |
| 5 | Experience Traceability | Every product and process traces upward to an L0 customer experience goal |

Levels 3 (contract satisfaction) and 6 (waste detection) are planned for future releases.

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
│   ├── validate.py          # CLI validator (4 validation levels)
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

- **[orgschema-demo](https://github.com/spectralbranding/orgschema-demo)** -- Spectra Coffee: a complete demonstration of the orgschema methodology (23 YAML files, 6 products, full TDD cascade)
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
