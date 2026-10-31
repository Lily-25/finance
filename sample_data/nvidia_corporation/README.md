# NVIDIA US_GAAP_SEC three-statement data

This directory contains NVIDIA Corporation's three consolidated financial
statements for fiscal 2023, 2024, 2025, and fiscal 2026 Q3. There are 12 JSON
files: one balance sheet, income statement, and statement of cash flows for each
period. The files are ready for the application's `US_GAAP_SEC` profile.

## Period interpretation

NVIDIA uses a 52- or 53-week fiscal year rather than a calendar year. The
project's period labels therefore mean:

| Label | Source period | Income and cash-flow scope |
| --- | --- | --- |
| `2023` | 31 January 2022–29 January 2023 | Audited fiscal year |
| `2024` | 30 January 2023–28 January 2024 | Audited fiscal year |
| `2025` | 29 January 2024–26 January 2025 | Audited fiscal year |
| `2026Q3` | 27 January 2025–26 October 2025 | Unaudited nine-month year-to-date period |

The `2026Q3` balance sheet is the point-in-time position at 26 October 2025.

## Official sources

- [Fiscal 2024 Form 10-K](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/nvda-20240128.htm): fiscal 2023 comparative balance sheet and supporting notes.
- [Fiscal 2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm): fiscal 2024 and 2025 balance sheets, fiscal 2023–2025 income, comprehensive-income and cash-flow statements, and supporting notes.
- [Fiscal 2026 third-quarter Form 10-Q](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000230/nvda-20251026.htm): fiscal 2026 Q3 balance sheet and nine-month income, comprehensive-income and cash-flow statements.

Each JSON file records its filing URL, statement locator, source period, audit
status, and source XBRL statement concept. Every indicator records the exact
filed caption or an explicit "not separately reported" marker, a mapping
description, and a source locator.

## Normalization policy

- Filed monetary values are in USD millions. They are multiplied by 1,000,000
  and stored as full-USD decimal strings; no extra precision is invented.
- Per-share data remain USD per share and are not multiplied.
- Every canonical field allowed by the relevant US_GAAP_SEC statement section
  is present. A field that NVIDIA did not separately report is explicitly set to
  zero and identified as such in `source_field` and `description`.
- NVIDIA's combined captions are decomposed only where a note supplies the
  component. Any remaining amount is placed in the closest residual field and
  the calculation is disclosed in `description` and `source_reference`.
- Reported subtotals are retained with `is_subtotal: true`, preventing them from
  being summed a second time. Cash-flow signs use positive inflows and negative
  outflows, with filed activity totals retained.
- NVIDIA reports no non-controlling interest or temporary equity in these
  periods, so those canonical fields are explicit zeros.

Rebuild the files deterministically from the transcribed source figures:

```bash
python3 scripts/build_nvidia_us_gaap_sec_dataset.py
```

The tests verify complete field coverage, application retrieval, source
semantics, statement arithmetic, the balance-sheet equation, and cash
reconciliation.
