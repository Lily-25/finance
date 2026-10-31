# Financial Position Report Generator

A small, dependency-free Python project that turns structured asset and liability data into a polished, stand-alone HTML report. It separates current from non-current items, calculates composition, liquidity, leverage, and net assets with decimal arithmetic, renders four inline SVG charts, and writes a concise interpretation grounded in the supplied values.

The report has no JavaScript, external fonts, remote stylesheets, or image files. The generated HTML can be emailed, archived, or opened locally in any modern browser.

## Requirements

- Python 3.9 or newer
- No third-party packages

## Quick start

From this directory, generate the included example:

```sh
python3 -m asset_report
```

With no arguments, the module loads the four supplied Gotion High-Tech period files and writes
`build/time-frame-report.html`. Direct-file execution uses the same defaults:

```sh
python3 asset_report/__main__.py
```

Then open `build/time-frame-report.html` in a browser. You can still supply explicit inputs,
output, and title; use `--title "Custom page title"` to override the browser-page title.

Show all command-line options:

```sh
python3 -m asset_report --help
```

### Main input parameters

`asset_report.presentation.cli.main(argv)` accepts the same arguments as the command line:

| Parameter | Required | Description |
| --- | --- | --- |
| `input` | Yes | One or more UTF-8 JSON period statements |
| `-o`, `--output` | No | HTML destination; defaults to `build/time-frame-report.html` |
| `--title` | No | Custom browser-page title |
| `--version` | No | Print the application version and exit |

Generate the included 2023–2026Q3 time-frame analysis with the same command:

```sh
python3 -m asset_report \
  sample_data/gotion_high_tech_co_ltd_*.json \
  --output build/time-frame-report.html \
  --title "Gotion High-Tech 2023–2026Q3 Financial Position Trend"
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

### Time-frame input

Store every reporting period as a complete, independent statement using this naming
convention:

```text
sample_data/
├── {company_name}_2023.json
├── {company_name}_2024.json
├── {company_name}_2025.json
└── {company_name}_2026Q3.json
```

Pass one or more files to the same command. Recognized `YYYY` and `YYYYQ1`–`YYYYQ4`
periods are ordered automatically, so shell expansion order does not affect the report.
Each file repeats `company`, optional `ticker`, `currency`, and `reporting_period`, then
records that period's asset and liability items using the normal single-statement schema.

The supplied Gotion High-Tech files contain real consolidated balance-sheet closing
balances for 2023, 2024, 2025, and 2026Q3. They retain every non-zero published asset
and liability line that contributes to the reported totals. Standard lines map to the
domain model; additional published lines such as derivative financial liabilities,
bonds payable, long-term payables, and other non-current financial assets remain
explicit custom items. Missing standard fields safely default to zero.

Each sample file includes a top-level `source` object with the report name, statement
date, audit status, and official disclosure URL. This metadata is informational and is
ignored by the report pipeline. The 2023 figures use the audited comparative column in
the 2024 annual report; 2024 and 2025 are audited year-end figures; 2026Q3 is the
unaudited consolidated balance sheet at 30 September 2026. Amounts are exact CNY values,
not rounded millions.

Time-frame rules:

- Supply one or more single-period JSON files for one company, ticker, and currency.
- A single file produces a one-period `TimeFrameAnalysisResult`; no separate snapshot-analysis interface is required.
- Period labels must be unique. Annual and quarterly periods may be combined, such as `2023`, `2024`, `2025`, and `2026Q3`.
- Every file uses the same asset and liability schema as a single-period report.
- Percentage change is calculated from the earliest supplied period to the latest. The report does not annualize a partial period such as `2026Q3`.
- The former embedded `periods` array remains readable for backward compatibility, but separate files are the recommended format.

## Domain model

`Company` contains `name`, optional `ticker`, `currency`, and `reporting_period`. The JSON adapter constructs this model from the root-level fields, while the generated report displays the ticker only when supplied.

`AssetStatement` exposes explicit, optional line items. Omitted values safely default to zero and numeric values are converted to exact `Money` objects.

- Current assets: `cash_and_cash_equivalents`, `trading_financial_assets`, `notes_receivable`, `accounts_receivable`, `receivables_financing`, `prepayments`, `other_receivables`, `inventory`, `non_current_assets_due_within_one_year`, and `other_current_assets`.
- Non-current assets: `long_term_investments`, `debt_investments`, `equity_investments`, `fixed_assets`, `construction_in_progress`, `right_of_use_assets`, `intangible_assets`, `development_expenditure`, `goodwill`, `deferred_tax_assets`, and `other_non_current_assets`.

It calculates `total_current_assets`, `total_non_current_assets`, `total_assets`, `component_percentages`, and `percentage_of_total(component)`. The existing list-based JSON input is mapped to these fields; recognized aliases such as “Prepaid expenses” and “Property, plant and equipment” map to `prepayments` and `fixed_assets`, while custom line items remain available.

`LiabilityStatement` follows the same zero-safe design and is connected to JSON input, analysis, charts, narrative, and HTML output.

- Current liabilities: `accounts_payable`, `short_term_debt`, `notes_payable`, `accrued_expenses`, `taxes_payable`, `deferred_revenue`, `payroll_payable`, `non_current_liabilities_due_within_one_year`, and `other_current_liabilities`.
- Non-current liabilities: `long_term_debt`, `lease_liabilities`, `deferred_tax_liabilities`, `pension_liabilities`, `provisions`, `deferred_income`, and `other_non_current_liabilities`.

It calculates `total_current_liabilities`, `total_non_current_liabilities`, `total_liabilities`, `component_percentages`, and `percentage_of_total(component)`. `FinancialStatementData` combines `Company`, `AssetStatement`, and `LiabilityStatement`; the analysis also calculates liabilities as a percentage of assets, net assets, and the current ratio.

`FinancialTimeSeriesData` contains one or more ordered `FinancialStatementData` snapshots. `TimeFrameAnalysisResult` is the only public analysis result exposed by `FinancialAnalysisApp`. With one period, `first` and `latest` refer to the same snapshot and change metrics are zero; with multiple periods, it compares first and latest totals, percentage changes, net assets, liability-to-asset percentage points, and current ratios.

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

In time-frame mode, the four charts change to assets versus liabilities, net assets, current ratio, and liabilities-to-assets across periods. The report also includes a period comparison table and the latest-period asset and liability details.

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

period_files = [
    "sample_data/gotion_high_tech_co_ltd_2023.json",
    "sample_data/gotion_high_tech_co_ltd_2024.json",
    "sample_data/gotion_high_tech_co_ltd_2025.json",
    "sample_data/gotion_high_tech_co_ltd_2026Q3.json",
]

app = FinancialAnalysisApp()
analysis = app.analyze_time_frame(period_files)
print(analysis.data.time_frame)
print(analysis.asset_change_percentage)
print(analysis.liability_change_percentage)
print(analysis.net_asset_change)

output = app.generate_time_frame_report(
    period_files,
    "build/time-frame-report.html",
)
print(output)
```

`analyze_time_frame(...)` and `generate_time_frame_report(...)` are the complete public
facade. Both accept either one path or a sequence of paths. A single statement follows
the same time-frame pipeline as a multi-period comparison.

## Tests

Run the standard-library test suite from this directory:

```sh
python3 -m unittest discover -s tests -v
```

The tests cover domain invariants, malformed asset and liability input, one-period and multi-period time frames, exact totals and trend changes, ratios, rankings, narratives, SVG accessibility, HTML escaping, export behavior, CLI errors, and the unified report mode.

## Project files

```text
README.md
asset_report/             source package
docs/plantuml/            system and per-layer class diagrams
sample_data/gotion_high_tech_co_ltd_2023.json   audited 2023 closing balances
sample_data/gotion_high_tech_co_ltd_2024.json   audited 2024 closing balances
sample_data/gotion_high_tech_co_ltd_2025.json   audited 2025 closing balances
sample_data/gotion_high_tech_co_ltd_2026Q3.json unaudited 2026Q3 closing balances
tests/                    unit and integration tests
build/                    generated example report
```
