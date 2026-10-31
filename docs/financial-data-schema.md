# Financial data schema and field dictionary

## Standard and scope

The report runtime's canonical schema is a normalized **statement of financial
position** for a non-financial company. For the included Gotion High-Tech data it follows the
Chinese Ministry of Finance's **2019 consolidated financial statement format
(会合01表)** under Chinese Accounting Standards for Business Enterprises (CAS).
This is the format applicable to the supplied 2023–2026Q3 statements. The
[revised CAS 30](https://kjs.mof.gov.cn/zhengcefabu/202608/t20260805_3994927.htm)
is effective from 1 January 2027 and therefore is not retroactively applied to
these periods. See the Ministry of Finance's
[2019 format notice](https://kjs.mof.gov.cn/zhengcefabu/201905/t20190510_3254992.htm)
and the official
[consolidated statement template](https://www.mof.gov.cn/gkml/caizhengwengao/wg201901/wg201909/202005/P020200507337626447186.pdf).

The schema is intentionally normalized rather than tied to one company's exact
captions. Every input row retains its filed caption and mapping explanation, so
the normalized value can always be traced back to the source statement.

The broader [`schemas`](../schemas/README.md) library adds three-statement
profiles for CAS 2019, IFRS as adopted by the EU, and US GAAP with SEC
presentation. Each profile covers a balance sheet, income statement, and
statement of cash flows using the same provenance contract described here.

## Root object

| Field | Required | Meaning |
| --- | --- | --- |
| `company` | Yes | Legal or commonly reported company name. |
| `ticker` | No | Exchange ticker, normalized to uppercase. |
| `currency` | Yes | Reporting currency code, such as `CNY`; no conversion is performed. |
| `reporting_period` | Yes | Period label used for ordering and display, such as `2025` or `2026Q3`. |
| `schema` | No | Informational object identifying the accounting standard, statement format, scope, monetary unit, and amount scale used by the source. |
| `source` | No | Informational source provenance, normally report title, statement name, date, audit basis, and official URL. |
| `assets` | Yes | `current` and `non_current` item arrays. |
| `liabilities` | Yes | `current` and `non_current` item arrays. |
| `equity` | Yes | An `items` array containing signed equity components. |

## Indicator object

Every asset, liability, and equity indicator has the following traceability
contract:

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | Yes | Canonical English name, or a stable company-specific name when no canonical field fits. |
| `amount` | Yes | Exact amount in the root currency and scale. Decimal strings are recommended. Asset and liability values are non-negative; equity values may be signed. |
| `source_field` | Yes | Exact line caption in the filed source, including the source language, for example `货币资金` or `减：库存股`. |
| `description` | Yes | Short explanation of what the source caption represents and, when needed, why it maps to the canonical indicator. |
| `is_deduction` | Equity only, when applicable | Set to `true` when a source presents a positive number that must be subtracted from equity, such as treasury shares. |

Example:

```json
{
  "name": "Treasury shares",
  "amount": "441086989.87",
  "source_field": "减：库存股",
  "description": "Source field 减：库存股; reported positive amount is treated as a deduction from equity.",
  "is_deduction": true
}
```

## Mapping and mismatch policy

1. The adapter first matches `name` against a canonical name or alias.
2. If `name` is company-specific, it tries `source_field`. This allows a row such
   as `Company registered capital` with source caption `股本` to map to
   `share_capital` without losing the filed wording.
3. If neither value has a known mapping, the row is preserved as an additional
   indicator in its supplied section. It still contributes to totals,
   percentages, charts, and the report.
4. Missing canonical indicators default to zero. They do not need placeholder
   rows in JSON.
5. Source subtotals such as `流动资产合计`, `负债合计`, `归属于母公司所有者权益合计`,
   and `所有者权益合计` are not entered as components, because doing so would
   double-count their underlying rows.

This policy accommodates company disclosures such as derivative financial
assets, other payables, bonds payable, and long-term payables even when those
lines are outside the compact canonical field set.

## Asset fields

### Current assets

| Canonical field | Meaning |
| --- | --- |
| `cash_and_cash_equivalents` | Cash, bank deposits, and other highly liquid monetary balances. |
| `trading_financial_assets` | Financial assets held for trading or measured at fair value through profit or loss. |
| `notes_receivable` | Commercial or bank acceptance notes receivable from customers. |
| `accounts_receivable` | Trade amounts due from customers, net of applicable allowances. |
| `receivables_financing` | Receivables managed both to collect contractual cash flows and to sell or transfer. |
| `prepayments` | Amounts paid to suppliers before goods or services are received. |
| `other_receivables` | Non-trade receivables not presented in another current-asset line. |
| `inventory` | Materials, work in progress, finished goods, and related inventory balances. |
| `non_current_assets_due_within_one_year` | Non-current asset balances contractually due within twelve months. |
| `other_current_assets` | Current assets not presented in another standard current-asset line. |

### Non-current assets

| Canonical field | Meaning |
| --- | --- |
| `long_term_investments` | Long-term equity-accounted or strategic investments. |
| `debt_investments` | Debt instruments held as non-current investments. |
| `equity_investments` | Non-current equity instruments outside long-term equity-accounted investments. |
| `fixed_assets` | Property, plant, and equipment used in operations, net of depreciation and impairment. |
| `construction_in_progress` | Capital projects and equipment installation not yet ready for use. |
| `right_of_use_assets` | Recognized rights to use leased property or equipment. |
| `intangible_assets` | Identifiable non-monetary assets without physical substance. |
| `development_expenditure` | Qualifying development costs capitalized before transfer to intangible assets. |
| `goodwill` | Acquisition goodwill remaining after impairment. |
| `deferred_tax_assets` | Future tax benefits from deductible temporary differences and eligible losses. |
| `other_non_current_assets` | Non-current assets not presented in another standard line. |

Calculated asset values are `total_current_assets`,
`total_non_current_assets`, `total_assets`, and each component's percentage of
total assets.

## Liability fields

### Current liabilities

| Canonical field | Meaning |
| --- | --- |
| `accounts_payable` | Trade amounts owed to suppliers for goods and services received. |
| `short_term_debt` | Borrowings contractually due within twelve months. |
| `notes_payable` | Commercial or bank acceptance notes payable to suppliers or lenders. |
| `accrued_expenses` | Expenses recognized but not yet paid or separately presented. |
| `taxes_payable` | Taxes and statutory charges accrued but not yet remitted. |
| `deferred_revenue` | Customer consideration received before the related performance obligation is satisfied. |
| `payroll_payable` | Employee compensation and benefits accrued but unpaid. |
| `non_current_liabilities_due_within_one_year` | Current portion of borrowings and other non-current obligations. |
| `other_current_liabilities` | Current obligations not presented in another standard current-liability line. |

### Non-current liabilities

| Canonical field | Meaning |
| --- | --- |
| `long_term_debt` | Borrowings due more than twelve months after the reporting date. |
| `lease_liabilities` | Present value of unpaid lease payments classified as non-current. |
| `deferred_tax_liabilities` | Future tax obligations from taxable temporary differences. |
| `pension_liabilities` | Long-term obligations for pensions and other post-employment benefits. |
| `provisions` | Present obligations of uncertain timing or amount recognized under accounting standards. |
| `deferred_income` | Government grants or other income recognized over future periods. |
| `other_non_current_liabilities` | Non-current obligations not presented in another standard line. |

Calculated liability values are `total_current_liabilities`,
`total_non_current_liabilities`, `total_liabilities`, and each component's
percentage of total liabilities and total assets.

## Equity fields

| Canonical field | Meaning and sign treatment |
| --- | --- |
| `share_capital` | Registered or issued share capital attributable to the company's shareholders. |
| `other_equity_instruments` | Equity-classified instruments other than ordinary share capital, such as qualifying perpetual instruments. |
| `capital_reserve` | Share premium and other owner-related capital contributions or adjustments. |
| `treasury_shares` | Cost of the company's own shares held; always deducted from equity. A positive source value should use `is_deduction: true`. |
| `other_comprehensive_income` | Accumulated gains and losses recognized outside profit or loss; may be positive or negative. |
| `special_reserve` | Statutory or industry-specific reserves recognized directly in equity. |
| `surplus_reserve` | Appropriations from profit required or permitted by law and corporate policy. |
| `general_risk_reserve` | Risk reserve used primarily by financial institutions when applicable. |
| `retained_earnings` | Cumulative profit retained after distributions and reserve appropriations; may be negative for accumulated losses. |
| `non_controlling_interests` | Subsidiary equity attributable to shareholders outside the parent group. |

`parent_equity` is calculated as total equity less non-controlling interests.
`total_equity` is the signed sum of all standard and additional equity rows.
The source subtotal `归属于母公司所有者权益合计` is deliberately excluded from
input because it is derived from the parent-equity components.

## Reconciliation rule

Every period exposes:

```text
balance_difference = total_assets - total_liabilities - total_equity
```

The statement is marked balanced when the absolute difference is no more than
`0.01` in the stated monetary unit. This is an accounting-equation check, not a
claim that liabilities equal assets: the correct relationship is **assets =
liabilities + equity**.
