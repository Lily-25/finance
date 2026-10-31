# Accounting-standard JSON Schemas

This directory contains nine JSON Schema Draft 2020-12 documents: three
statements for each supported accounting-standard profile.

| Profile | Balance sheet | Income statement | Statement of cash flows |
| --- | --- | --- | --- |
| `CAS_2019` | `cas/balance-sheet.schema.json` | `cas/income-statement.schema.json` | `cas/cash-flow-statement.schema.json` |
| `IFRS_EU` | `ifrs-eu/balance-sheet.schema.json` | `ifrs-eu/income-statement.schema.json` | `ifrs-eu/cash-flow-statement.schema.json` |
| `US_GAAP_SEC` | `us-gaap/balance-sheet.schema.json` | `us-gaap/income-statement.schema.json` | `us-gaap/cash-flow-statement.schema.json` |

`catalog.json` is the machine-readable index. `common.schema.json` supplies the
shared metadata, source provenance, exact-decimal amount, and line-item
definitions referenced by all nine schemas.

## Line-item contract

Every reported indicator requires:

- `name`: stable display name;
- `amount`: signed JSON number or exact decimal string;
- `source_field`: exact caption from the filed source, preserving language and punctuation;
- `description`: accounting meaning and explanation of any mapping judgment.

`canonical_field` is optional so existing project data remains compatible. When
present, it must be one of the standard-specific identifiers allowed by the
containing section. Use `other` for an unmatched company-specific line and keep
the original wording in `name` and `source_field`.

Optional flags carry processing semantics:

- `is_deduction: true` means a positive source value reduces its subtotal;
- `is_subtotal: true` identifies a reported subtotal that must not be summed as a component;
- `cash_flow_direction` records whether a cash-flow line is an inflow, outflow, or net value;
- `is_non_cash: true` identifies a supplemental non-cash transaction.

## Profile boundaries

### CAS 2019

The CAS schemas follow the Ministry of Finance's 2019 consolidated formats:
会合01表, 会合02表, and 会合03表. Financial-industry-only lines are included so
the schema can preserve them when present. The cash-flow profile uses the direct
method prescribed by the published form.

Official source: <https://www.mof.gov.cn/gkml/caizhengwengao/wg201901/wg201909/202005/P020200507337626447186.pdf>

### IFRS/EU

The IFRS balance-sheet schema covers IAS 1 minimum line items and the
corresponding presentation requirements carried into IFRS 18. The income schema
supports both IAS 1-era presentation and IFRS 18 categories and subtotals. The
cash-flow schema follows IAS 7 and supports direct or indirect operating cash
flows.

`IFRS_EU` means IFRS as endorsed by the EU, not an assumption that every newly
issued IASB standard is already endorsed. Record the exact applied standard and
edition in `schema.presentation_standard`. IFRS 18 replaces IAS 1 for annual
periods beginning on or after 1 January 2027, with earlier application permitted.

Official sources:

- <https://finance.ec.europa.eu/financial-markets/company-reporting-and-auditing/company-reporting/financial-reporting_en>
- <https://www.ifrs.org/issued-standards/list-of-standards/ias-1-presentation-of-financial-statements.html/>
- <https://www.ifrs.org/issued-standards/list-of-standards/ifrs-18-presentation-and-disclosure-in-financial-statements/>
- <https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/>

### US GAAP/SEC

The US profile combines the FASB Codification with SEC Regulation S-X
presentation for commercial and industrial registrants. It therefore includes
SEC-specific captions and a separate `temporary_equity` section for redeemable
securities outside permanent stockholders' equity. Other industries may require
specialized SEC articles and additional fields.

Official sources:

- <https://www.fasb.org/standards>
- <https://www.ecfr.gov/current/title-17/chapter-II/part-210/section-210.5-02>
- <https://www.ecfr.gov/current/title-17/chapter-II/part-210/section-210.5-03>
- <https://www.ecfr.gov/current/title-17/chapter-II/part-210/section-210.3-02>

## Important limitations

The runtime schema catalog actively uses these contracts to retrieve and normalize
all three statement types for an inclusive company time frame. The HTML analysis
uses the selected balance sheets; normalized income and cash-flow statements remain
available as traceable JSON artifacts for downstream analysis.

These schemas define normalized data shape, presentation fields, provenance, and
extension behavior. They do not replace the recognition, measurement,
consolidation, disclosure, materiality, or industry-specific requirements of the
underlying accounting standards. A schema-valid document can still be
accounting-incomplete or incorrect.
