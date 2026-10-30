# Financial Position Report Generator

A small, dependency-free Python project that turns structured asset and liability data into a polished, stand-alone HTML report. It separates current from non-current items, calculates composition, liquidity, leverage, and net assets with decimal arithmetic, renders four inline SVG charts, and writes a concise interpretation grounded in the supplied values.

The report has no JavaScript, external fonts, remote stylesheets, or image files. The generated HTML can be emailed, archived, or opened locally in any modern browser.

## Requirements

- Python 3.9 or newer
- No third-party packages

## Quick start

From this directory, generate the included example:

```sh
python3 -m asset_report sample_data/assets.json --output build/financial-report.html
```

Direct-file execution is also supported:

```sh
python3 asset_report/__main__.py sample_data/assets.json --output build/financial-report.html
```

Then open `build/asset-report.html` in a browser. Use `--title "Custom page title"` to override the browser-page title.

Show all command-line options:

```sh
python3 -m asset_report --help
```

### Main input parameters

`asset_report.presentation.cli.main(argv)` accepts the same arguments as the command line:

| Parameter | Required | Description |
| --- | --- | --- |
| `input` | Yes | Path to a UTF-8 JSON financial statement |
| `-o`, `--output` | No | HTML destination; defaults to `build/financial-report.html` |
| `--title` | No | Custom browser-page title |
| `--version` | No | Print the application version and exit |

The comprehensive [`sample_data/main_input.json`](sample_data/main_input.json) supplies all 21 standard asset fields and all 16 standard liability fields. Run it with:

```sh
python3 -m asset_report \
  sample_data/main_input.json \
  --output build/main-input-report.html \
  --title "Orion 2025 Financial Position Report"
```

The equivalent programmatic call is:

```python
from asset_report.presentation.cli import main

exit_code = main([
    "sample_data/main_input.json",
    "--output", "build/main-input-report.html",
    "--title", "Orion 2025 Financial Position Report",
])
```

## Input format

Supply a UTF-8 JSON object with company details, asset arrays, and liability arrays:

```json
{
  "company": "Example Company Ltd.",
  "ticker": "EXM",
  "reporting_period": "Year ended 31 December 2025",
  "currency": "USD",
  "assets": {
    "current": [
      {"name": "Cash and cash equivalents", "amount": 1250000},
      {"name": "Inventory", "amount": "875000.50"}
    ],
    "non_current": [
      {"name": "Property, plant and equipment", "amount": 4200000}
    ]
  },
  "liabilities": {
    "current": [
      {"name": "Accounts payable", "amount": 640000}
    ],
    "non_current": [
      {"name": "Long-term debt", "amount": 2100000}
    ]
  }
}
```

Rules:

- `company`, `reporting_period`, and `currency` must be non-empty strings; `ticker` is optional.
- `assets.current` and `assets.non_current` must both be arrays; either one may be empty.
- `liabilities` is optional for backward compatibility. When supplied, `liabilities.current` and `liabilities.non_current` must both be arrays.
- Every asset or liability needs a non-empty `name` and a finite, non-negative `amount`.
- Amounts may be JSON numbers or decimal strings. Strings are useful when the source must preserve exact decimal notation.
- At least one item is required and total assets must be greater than zero.
- Names must be unique within each statement class, ignoring letter case.
- `currency` is displayed as supplied (uppercased); the program does not perform currency conversion.

Invalid input produces a concise error and a non-zero exit status. The output file is written atomically so an existing report is not left partially written.

## Domain model

`Company` contains `name`, optional `ticker`, `currency`, and `reporting_period`. The JSON adapter constructs this model from the root-level fields, while the generated report displays the ticker only when supplied.

`AssetStatement` exposes explicit, optional line items. Omitted values safely default to zero and numeric values are converted to exact `Money` objects.

- Current assets: `cash_and_cash_equivalents`, `trading_financial_assets`, `notes_receivable`, `accounts_receivable`, `receivables_financing`, `prepayments`, `other_receivables`, `inventory`, `non_current_assets_due_within_one_year`, and `other_current_assets`.
- Non-current assets: `long_term_investments`, `debt_investments`, `equity_investments`, `fixed_assets`, `construction_in_progress`, `right_of_use_assets`, `intangible_assets`, `development_expenditure`, `goodwill`, `deferred_tax_assets`, and `other_non_current_assets`.

It calculates `total_current_assets`, `total_non_current_assets`, `total_assets`, `component_percentages`, and `percentage_of_total(component)`. The existing list-based JSON input is mapped to these fields; recognized aliases such as “Prepaid expenses” and “Property, plant and equipment” map to `prepayments` and `fixed_assets`, while custom line items remain available.

`LiabilityStatement` follows the same zero-safe design and is connected to JSON input, analysis, charts, narrative, and HTML output.

- Current liabilities: `accounts_payable`, `short_term_debt`, `notes_payable`, `accrued_expenses`, `taxes_payable`, `deferred_revenue`, `payroll_payable`, `non_current_liabilities_due_within_one_year`, and `other_current_liabilities`.
- Non-current liabilities: `long_term_debt`, `lease_liabilities`, `deferred_tax_liabilities`, `pension_liabilities`, `provisions`, `deferred_income`, and `other_non_current_liabilities`.

It calculates `total_current_liabilities`, `total_non_current_liabilities`, `total_liabilities`, `component_percentages`, and `percentage_of_total(component)`. `FinancialStatementData` combines `Company`, `AssetStatement`, and `LiabilityStatement`; the analysis also calculates liabilities as a percentage of assets, net assets, and the current ratio. `AssetReportData` and `generate_asset_report(...)` remain available as compatibility names.

```python
from asset_report.domain import AssetStatement, LiabilityStatement

assets = AssetStatement(cash_and_cash_equivalents=100, fixed_assets=900)
liabilities = LiabilityStatement(accounts_payable=80, long_term_debt=320)

assert assets.total_assets.amount == 1000
assert assets.percentage_of_total("fixed_assets") == 90
assert liabilities.total_liabilities.amount == 400
```

## Report contents

The generated report includes:

1. Total assets, total liabilities, net assets, and current-ratio summary cards.
2. A short interpretation of asset structure, liability composition, leverage, and liquidity.
3. Four accessible inline SVG charts:
   - current versus non-current asset structure;
   - current versus non-current liability structure;
   - all asset categories ranked by share of total assets;
   - all liability categories ranked by share of total liabilities.
4. Detailed asset and liability tables with classification, amount, composition percentage, and liability share of assets.

All user-provided text is HTML-escaped in both the report and SVG charts.

## Architecture

The implementation follows the supplied layered PlantUML package plans with assets and liabilities carried consistently through every layer:

```text
asset_report/
├── presentation/       CLI parsing and user-facing messages
├── application/        application facade, configuration, use-case orchestration
├── business/           asset/liability metrics, ratios, immutable analysis result
├── domain/             company, money, asset/liability statements, repository contract
├── data_access/        JSON reader, standardizer, validator, mapper, repository adapter
└── output/             narratives, four SVG charts, HTML template, file exporter
```

Dependency direction follows the plans: presentation calls application; application coordinates business, data access, and output; business depends on domain; the JSON adapter implements the domain repository contract; output consumes analysis results.

Implementation-aligned PlantUML package and class diagrams are available in [`docs/plantuml`](docs/plantuml/README.md). The paired sets include a complete system view and one detailed view for every layer, with matching names, colors, and dependency directions.

## Programmatic use

```python
from asset_report import FinancialAnalysisApp

output = FinancialAnalysisApp().generate_financial_report(
    "sample_data/assets.json",
    "build/financial-report.html",
)
print(output)
```

## Tests

Run the standard-library test suite from this directory:

```sh
python3 -m unittest discover -s tests -v
```

The tests cover domain invariants, malformed asset and liability input, backward-compatible asset-only input, exact totals and ratios, rankings, narratives, SVG accessibility, HTML escaping, export behavior, CLI errors, and complete report generation.

## Project files

```text
README.md
asset_report/             source package
docs/plantuml/            system and per-layer class diagrams
sample_data/assets.json   ready-to-run asset and liability example
sample_data/main_input.json  comprehensive input with all standard fields
tests/                    unit and integration tests
build/                    generated example report
```
