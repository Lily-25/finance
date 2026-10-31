# Financial Position Report Generator

A small, dependency-free Python project that retrieves the three primary financial statements across a time frame, normalizes them to a selected accounting schema, and turns balance-sheet data into a polished, stand-alone HTML report. It supports CAS 2019, IFRS as adopted by the EU, and US GAAP/SEC profiles, preserves source provenance, verifies the accounting equation, calculates composition, liquidity, and leverage with decimal arithmetic, renders four inline SVG charts, and writes a concise interpretation grounded in the supplied values.

The report has no JavaScript, external fonts, remote stylesheets, or image files. The generated HTML can be emailed, archived, or opened locally in any modern browser.

## Requirements

- Python 3.9 or newer
- No third-party packages

## Quick start

Start the local analysis UI:

```sh
python3 -m asset_report --ui
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The UI can run three-statement normalization, a financial-position report, or both in one task. Every task gets a persistent timestamped directory below `output/`; the server binds only to localhost by default.

Use another address or port when needed:

```sh
python3 -m asset_report --ui --host 127.0.0.1 --port 9000
```

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
| `--ui` | No | Start the local analysis UI instead of generating a report |
| `--host` | No | UI bind host; defaults to `127.0.0.1` |
| `--port` | No | UI bind port; defaults to `8765` |
| `--version` | No | Print the application version and exit |

Generate the included 2023–2026Q3 time-frame analysis with the same command:

```sh
python3 -m asset_report \
  sample_data/gotion_high_tech_co_ltd_*.json \
  --output build/time-frame-report.html \
  --title "Gotion High-Tech 2023–2026Q3 Financial Position Trend"
```

## Input format

Supply a UTF-8 JSON object with company details and complete asset, liability,
and equity sections. Each indicator records the exact filed source caption and
a mapping explanation:

```json
{
  "company": "Example Company Ltd.",
  "ticker": "EXM",
  "reporting_period": "Year ended 31 December 2025",
  "currency": "USD",
  "assets": {
    "current": [
      {
        "name": "Cash and cash equivalents",
        "amount": 1250000,
        "source_field": "Cash and cash equivalents",
        "description": "Source balance-sheet line for cash and highly liquid monetary balances."
      },
      {
        "name": "Inventory",
        "amount": "875000.50",
        "source_field": "Inventories",
        "description": "Source balance-sheet line mapped to the canonical inventory indicator."
      }
    ],
    "non_current": [
      {
        "name": "Fixed assets",
        "amount": 4200000,
        "source_field": "Property, plant and equipment",
        "description": "Source line for operating fixed assets, net of depreciation and impairment."
      }
    ]
  },
  "liabilities": {
    "current": [
      {
        "name": "Accounts payable",
        "amount": 640000,
        "source_field": "Trade payables",
        "description": "Source line for amounts owed to suppliers."
      }
    ],
    "non_current": [
      {
        "name": "Long-term debt",
        "amount": 2100000,
        "source_field": "Long-term borrowings",
        "description": "Source line for borrowings due after twelve months."
      }
    ]
  },
  "equity": {
    "items": [
      {
        "name": "Share capital",
        "amount": "3585000.50",
        "source_field": "Issued capital",
        "description": "Source line for registered and issued shareholder capital."
      }
    ]
  }
}
```

Rules:

- `company`, `reporting_period`, and `currency` must be non-empty strings; `ticker` is optional.
- `assets.current`, `assets.non_current`, `liabilities.current`, and `liabilities.non_current` must be arrays. Each statement may have an empty classification, but assets and liabilities must each contain at least one item overall.
- `equity.items` is required and must contain at least one indicator.
- Every indicator needs a non-empty `name`, `source_field`, and `description` so the normalized value remains traceable to the filed statement.
- Every financial amount must be finite and may be positive, zero, or negative. Use a negative source value directly, or use `is_deduction: true` when a positive filed value reduces its containing balance. Reported rows marked `is_subtotal: true` are retained for traceability but are not added again when producing the financial-position report.
- Amounts may be JSON numbers or decimal strings. Strings are useful when the source must preserve exact decimal notation.
- Total assets must be greater than zero. The report checks `assets = liabilities + equity` with a tolerance of 0.01.
- Names must be unique within each statement class, ignoring letter case.
- `currency` is displayed as supplied (uppercased); the program does not perform currency conversion.

Invalid input produces a concise error and a non-zero exit status. The output file is written atomically so an existing report is not left partially written.

The canonical field list follows the 2019 CAS consolidated financial statement
format used by the included Chinese-company samples. Company-specific captions
map by `name` and then `source_field`; unmatched rows are retained as additional
indicators rather than discarded. See the complete
[financial data schema and field dictionary](docs/financial-data-schema.md) for
the standard basis, every supported field, sign rules, and mismatch examples.

### Multi-standard schema library

The [`schemas`](schemas/README.md) directory contains JSON Schema Draft 2020-12
definitions for three accounting-standard profiles:

| Profile | Balance sheet | Income statement | Cash flows |
| --- | --- | --- | --- |
| CAS 2019 | Yes | Yes | Yes |
| IFRS as adopted by the EU | Yes | Yes | Yes |
| US GAAP with SEC Regulation S-X | Yes | Yes | Yes |

All nine schemas require the same source-provenance fields and allow
company-specific lines through the `other` canonical field. The machine-readable
[`schema catalog`](schemas/catalog.json) resolves profile and statement type to
the appropriate file. The runtime uses that catalog to retrieve and normalize the
balance sheet, income statement, and statement of cash flows for every period in
an inclusive time frame.

### Three-statement retrieval and normalization

Place source JSON files in one directory or any nested subdirectories. Each file
identifies its `company`, `reporting_period`, `schema.profile`, and
`schema.statement_type`. A complete period contains exactly one `balance_sheet`,
one `income_statement`, and one `cash_flow_statement`.

The UI and `FinancialAnalysisApp.retrieve_three_statements(...)` select the
requested company, inclusive time frame, and profile; require all three statements
for every expected period; validate schema metadata, sections, provenance, and
decimal amounts; and add the permitted `canonical_field` to each indicator. An
unmatched company-specific field is retained as `other`, never silently discarded.
The export contains normalized JSON files and a source-to-output `manifest.json`.

```python
from asset_report import FinancialAnalysisApp

result = FinancialAnalysisApp().retrieve_three_statements(
    "sample_data/three_statements",
    "output/my-normalized-run",
    company="Gotion High-Tech Co., Ltd.",
    start_period="2024",
    end_period="2025",
    schema_profile="CAS_2019",
)
print(result.manifest_path)
```

The bundled `sample_data/three_statements/` directory contains a complete,
illustrative two-period CAS data set for exercising this workflow. Its figures are
synthetic and clearly labeled as illustrative; the separate Gotion files retain
their real-source balance-sheet data.

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
records that period's asset, liability, and equity items using the normal single-statement schema.

The supplied Gotion High-Tech files contain real consolidated balance-sheet closing
balances for 2023, 2024, 2025, and 2026Q3. They retain every non-zero published asset
liability, and equity line that contributes to the reported totals. Standard lines map to the
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
- Every file uses the same asset, liability, equity, and provenance schema as a single-period report.
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

`EquityStatement` adds signed, zero-safe fields for `share_capital`,
`other_equity_instruments`, `capital_reserve`, `treasury_shares`,
`other_comprehensive_income`, `special_reserve`, `surplus_reserve`,
`general_risk_reserve`, `retained_earnings`, and
`non_controlling_interests`. It calculates parent equity, total equity, and
component percentages. Treasury shares are deductions, while other
comprehensive income and retained earnings may be negative.

All three statements keep each indicator's `source_field` and `description`.
Recognized source captions map into canonical fields; unrecognized captions are
preserved as additional indicators and still contribute to totals.

`LiabilityStatement` calculates `total_current_liabilities`, `total_non_current_liabilities`, `total_liabilities`, `component_percentages`, and `percentage_of_total(component)`. `FinancialStatementData` combines `Company`, `AssetStatement`, `LiabilityStatement`, and `EquityStatement`; the analysis also calculates liabilities and equity as percentages of assets, the current ratio, and the accounting-equation difference.

`FinancialTimeSeriesData` contains one or more ordered `FinancialStatementData` snapshots. `TimeFrameAnalysisResult` is the only public analysis result exposed by `FinancialAnalysisApp`. With one period, `first` and `latest` refer to the same snapshot and change metrics are zero; with multiple periods, it compares first and latest totals, percentage changes, net assets, liability-to-asset percentage points, and current ratios.

```python
from asset_report.domain import AssetStatement, EquityStatement, LiabilityStatement

assets = AssetStatement(cash_and_cash_equivalents=100, fixed_assets=900)
liabilities = LiabilityStatement(accounts_payable=80, long_term_debt=320)
equity = EquityStatement(share_capital=600)

assert assets.total_assets.amount == 1000
assert assets.percentage_of_total("fixed_assets") == 90
assert liabilities.total_liabilities.amount == 400
assert equity.total_equity.amount == 600
```

## Report contents

The generated report includes:

1. Total assets, total liabilities, reported equity, accounting-equation status, and current-ratio summary cards.
2. A short interpretation of asset structure, liability composition, equity, leverage, and liquidity.
3. Four accessible inline SVG charts:
   - current versus non-current asset structure;
   - current versus non-current liability structure;
   - all asset categories ranked by share of total assets;
   - all liability categories ranked by share of total liabilities.
4. Detailed asset, liability, and equity tables with amount, composition, exact source caption, and mapping description.

All user-provided text is HTML-escaped in both the report and SVG charts.

In time-frame mode, the four charts change to assets/liabilities/equity, reported equity, current ratio, and liabilities-to-assets across periods. The report also includes a period comparison table, balance status for every period, and the latest-period asset, liability, and equity details.

## Architecture

The implementation follows the supplied layered PlantUML package plans with assets, liabilities, equity, and source provenance carried consistently through every layer:

```text
asset_report/
├── presentation/       CLI parsing and user-facing messages
├── application/        application facade, configuration, use-case orchestration
├── business/           asset/liability/equity metrics, ratios, immutable analysis result
├── domain/             company, money, complete financial position, repository contract
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

`analyze_time_frame(...)`, `generate_time_frame_report(...)`, and
`retrieve_three_statements(...)` form the public facade. Report operations accept
either one path or a sequence of paths. A single statement follows the same time-frame
pipeline as a multi-period comparison.

## Tests

Run the standard-library test suite from this directory and preserve the complete
output in a unique `output/unittest-<UTC timestamp>-<random>/` directory:

```sh
python3 scripts/run_tests.py
```

Each run stores `unittest-results.txt` and a machine-readable `summary.json` and is
retained locally for inspection. The tests cover domain invariants, all three
statement contracts, time-frame completeness, schema normalization, the task UI,
accounting-equation reconciliation, ratios, narratives, charts, export behavior,
CLI errors, and the unified report mode.

## Project files

```text
README.md
asset_report/             source package
docs/plantuml/            system and per-layer class diagrams
docs/financial-data-schema.md complete standard field dictionary and mapping rules
schemas/                  CAS, IFRS/EU, and US GAAP schemas for three statements
sample_data/gotion_high_tech_co_ltd_2023.json   audited 2023 closing balances
sample_data/gotion_high_tech_co_ltd_2024.json   audited 2024 closing balances
sample_data/gotion_high_tech_co_ltd_2025.json   audited 2025 closing balances
sample_data/gotion_high_tech_co_ltd_2026Q3.json unaudited 2026Q3 closing balances
sample_data/three_statements/ complete illustrative 2024–2025 three-statement set
tests/                    unit and integration tests
build/                    generated example report
output/                   ignored timestamped task and unittest results
```
