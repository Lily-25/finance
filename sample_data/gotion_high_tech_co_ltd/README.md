# Gotion High-Tech CAS three-statement data set

This directory contains 12 CAS 2019-normalized JSON files for Gotion High-Tech
Co., Ltd. (`002074.SZ`): consolidated balance sheet, income statement, and cash
flow statement for each of 2023, 2024, 2025, and 2026Q3.

## Official sources

- 2023 comparative and 2024 current-period figures: [Gotion High-Tech 2024 Annual Report](https://disc.static.szse.cn/download/disc/disk03/finalpage/2025-04-24/f8cb55cb-b4b2-420a-bdf7-d354f7b8cf88.PDF), audited.
- 2025 figures: [Gotion High-Tech 2025 Annual Report](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-29/24ee6bf9-6daa-4f4f-ae46-12dfbe099287.pdf), audited.
- 2026Q3 figures: [Gotion High-Tech 2026 Third Quarter Report](https://static.cninfo.com.cn/finalpage/2026-10-29/1225634491.PDF), unaudited.

The 2026Q3 balance sheet is at 30 September 2026. Its income statement and cash
flow statement cover 1 January through 30 September 2026; they are not a full
year and are deliberately not annualized.

## Normalization policy

- Monetary amounts are exact CNY amounts at scale 1, not rounded millions.
- Every canonical field allowed by the corresponding CAS schema appears once in
  its section, including `other`.
- A source row with a blank amount, or a CAS field not separately reported by
  this industrial company, has amount `0`; its description records that decision.
- Every line carries the canonical identifier, stable English name, exact Chinese
  source caption, explanation, source-page reference, deduction/subtotal flags,
  cash-flow direction, and non-cash flag.
- Reported statement totals are retained independently. The balance sheets satisfy
  `assets = liabilities + equity`, and the cash-flow statements reconcile opening
  cash, movement, and closing cash.

Rebuild the data set from the project root with:

```sh
python3 scripts/build_gotion_cas_dataset.py
```
