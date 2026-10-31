"""Standalone HTML reporting for cross-statement financial-ratio trends."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from html import escape

from ..business.ratios import (
    FinancialRatioAnalysisResult,
    FinancialRatioPeriod,
)


class FinancialRatioNarrativeGenerator:
    """Create concise observations from calculated ratio movements."""

    def generate(self, result: FinancialRatioAnalysisResult) -> tuple[str, ...]:
        if len(result.periods) == 1:
            latest = result.latest
            return (
                self._single_period_liquidity(latest),
                self._single_period_leverage(latest),
                self._single_period_profitability(latest),
                "Trend comparisons require at least two reporting periods.",
            )

        first = result.first
        latest = result.latest
        observations = [
            self._movement_from_pair(
                "Current-ratio liquidity",
                (first.period, first.current_ratio),
                (latest.period, latest.current_ratio),
                suffix="×",
                higher_is_better=True,
            ).capitalize()
            + ".",
            self._movement_from_pair(
                "Debt as a share of assets",
                (first.period, first.debt_ratio),
                (latest.period, latest.debt_ratio),
                percent=True,
                higher_is_better=False,
            ).capitalize()
            + ".",
        ]

        earliest_inventory = self._first_available(
            result, "days_sales_in_inventory"
        )
        earliest_receivables = self._first_available(
            result, "days_sales_in_receivables"
        )
        inventory_text = self._movement_from_pair(
            "inventory days",
            earliest_inventory,
            (latest.period, latest.days_sales_in_inventory),
            suffix=" days",
            higher_is_better=False,
        )
        receivables_text = self._movement_from_pair(
            "receivables days",
            earliest_receivables,
            (latest.period, latest.days_sales_in_receivables),
            suffix=" days",
            higher_is_better=False,
        )
        observations.append(
            f"Working-capital efficiency: {inventory_text}; {receivables_text}."
        )

        observations.append(
            "Profitability: "
            + self._movement_from_pair(
                "gross margin",
                (first.period, first.gross_profit_margin),
                (latest.period, latest.gross_profit_margin),
                percent=True,
                higher_is_better=True,
            )
            + "; "
            + self._movement_from_pair(
                "profit margin",
                (first.period, first.profit_margin),
                (latest.period, latest.profit_margin),
                percent=True,
                higher_is_better=True,
            )
            + "."
        )
        return tuple(observations)

    @staticmethod
    def _single_period_liquidity(period: FinancialRatioPeriod) -> str:
        return (
            "Current-ratio liquidity is unavailable."
            if period.current_ratio is None
            else f"The current ratio is {period.current_ratio:.2f}×."
        )

    @staticmethod
    def _single_period_leverage(period: FinancialRatioPeriod) -> str:
        return (
            "Debt-to-assets is unavailable."
            if period.debt_ratio is None
            else f"Debt equals {period.debt_ratio * Decimal('100'):.1f}% of assets."
        )

    @staticmethod
    def _single_period_profitability(period: FinancialRatioPeriod) -> str:
        return (
            "Profit margin is unavailable."
            if period.profit_margin is None
            else f"Profit margin is {period.profit_margin * Decimal('100'):.1f}%."
        )

    @staticmethod
    def _first_available(
        result: FinancialRatioAnalysisResult, attribute: str
    ) -> tuple[str, Decimal | None]:
        for period in result.periods:
            value = getattr(period, attribute)
            if value is not None:
                return period.period, value
        return result.first.period, None

    @staticmethod
    def _movement_from_pair(
        label: str,
        start: tuple[str, Decimal | None],
        end: tuple[str, Decimal | None],
        *,
        suffix: str = "",
        percent: bool = False,
        higher_is_better: bool,
    ) -> str:
        start_label, start_value = start
        end_label, end_value = end
        if start_value is None or end_value is None:
            return f"{label} is not comparable"
        multiplier = Decimal("100") if percent else Decimal("1")
        start_display = start_value * multiplier
        end_display = end_value * multiplier
        display_suffix = "%" if percent else suffix
        if end_value == start_value:
            direction = "was unchanged"
            assessment = "stable"
        else:
            improved = (end_value > start_value) == higher_is_better
            direction = "increased" if end_value > start_value else "decreased"
            assessment = "an improvement" if improved else "a deterioration"
        return (
            f"{label} {direction} from {start_display:.2f}{display_suffix} in "
            f"{start_label} to {end_display:.2f}{display_suffix} in {end_label}, "
            f"which is {assessment}"
        )


class FinancialRatioReportBuilder:
    """Render a dependency-free, stand-alone financial-ratio trend report."""

    SECTIONS = (
        (
            "Liquidity, leverage, and coverage",
            (
                ("Current ratio", "current_ratio", "multiple"),
                ("Quick ratio", "quick_ratio", "multiple"),
                ("Debt ratio", "debt_ratio", "percent"),
                ("Debt / equity ratio", "debt_to_equity_ratio", "multiple"),
                ("Interest coverage ratio", "interest_coverage_ratio", "multiple"),
            ),
        ),
        (
            "Operating efficiency",
            (
                ("Inventory turnover", "inventory_turnover", "multiple"),
                ("Days’ sales in inventory", "days_sales_in_inventory", "days"),
                ("Accounts receivable turnover", "receivables_turnover", "multiple"),
                ("Days’ sales in receivables", "days_sales_in_receivables", "days"),
                ("Total asset turnover", "total_asset_turnover", "multiple"),
                ("Fixed asset turnover", "fixed_asset_turnover", "multiple"),
            ),
        ),
        (
            "Profitability and shareholder returns",
            (
                (
                    "R&D intensity",
                    "research_and_development_intensity",
                    "percent",
                ),
                ("Profit margin", "profit_margin", "percent"),
                ("Gross profit margin", "gross_profit_margin", "percent"),
                ("Return on assets", "return_on_assets", "percent"),
                ("Return on equity", "return_on_equity", "percent"),
                ("Diluted earnings per share", "earnings_per_share", "currency"),
                ("Price / earnings ratio", "price_earnings_ratio", "multiple"),
            ),
        ),
    )

    CSS = r"""
:root { color-scheme: light; --ink:#172033; --muted:#64748b; --line:#e3e9f2; --paper:#fff; --bg:#f3f6fa; --blue:#2457d6; --teal:#0f766e; --purple:#6d28d9; }
* { box-sizing:border-box; }
body { margin:0; color:var(--ink); background:var(--bg); font:15px/1.55 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
.report { width:min(1160px,calc(100% - 36px)); margin:30px auto 54px; }
.hero { padding:44px 48px; color:#fff; border-radius:23px; background:linear-gradient(125deg,#14213d,#26487f 58%,#4338ca); box-shadow:0 22px 65px rgba(20,33,61,.18); }
.eyebrow { margin:0 0 9px; opacity:.76; text-transform:uppercase; letter-spacing:.14em; font-size:12px; font-weight:800; }
h1 { margin:0; font-size:clamp(32px,5vw,55px); line-height:1.05; letter-spacing:-.04em; }
.meta { display:flex; flex-wrap:wrap; gap:9px 28px; margin-top:21px; color:rgba(255,255,255,.83); }
.meta strong { color:#fff; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:13px; margin:-17px 20px 0; position:relative; }
.kpi,.panel { background:var(--paper); border:1px solid var(--line); box-shadow:0 11px 34px rgba(23,32,51,.06); }
.kpi { padding:20px; border-radius:15px; }
.kpi span { display:block; color:var(--muted); font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; }
.kpi strong { display:block; margin-top:7px; font-size:25px; letter-spacing:-.035em; }
.section { margin-top:25px; }
.section h2 { margin:0 0 12px; font-size:21px; letter-spacing:-.02em; }
.panel { border-radius:17px; padding:25px 28px; overflow:hidden; }
.insights { list-style:none; display:grid; gap:15px; margin:0; padding:0; }
.insights li { display:grid; grid-template-columns:12px 1fr; gap:12px; }
.insights li::before { content:""; width:9px; height:9px; margin-top:7px; border-radius:3px; background:linear-gradient(135deg,var(--blue),var(--purple)); }
.table-wrap { overflow-x:auto; padding:0; }
table { width:100%; min-width:760px; border-collapse:collapse; font-variant-numeric:tabular-nums; }
th { padding:13px 16px; color:var(--muted); background:#f8fafc; border-bottom:1px solid var(--line); text-align:right; font-size:11px; text-transform:uppercase; letter-spacing:.07em; }
th:first-child,td:first-child { text-align:left; }
td { padding:14px 16px; border-bottom:1px solid var(--line); text-align:right; }
tr:last-child td { border-bottom:0; }
.na { color:var(--muted); }
.notes { color:var(--muted); margin:0; padding-left:20px; }
.notes li+li { margin-top:7px; }
.footer { color:var(--muted); text-align:center; font-size:12px; margin-top:24px; }
@media(max-width:850px){.kpis{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.report{width:min(100% - 20px,1160px);margin-top:10px}.hero{padding:34px 25px 44px;border-radius:17px}.kpis{grid-template-columns:1fr;margin-top:-24px}.panel{padding:20px}}
@media print{body{background:#fff}.report{width:100%;margin:0}.hero,.kpi,.panel{box-shadow:none;break-inside:avoid}}
"""

    def __init__(
        self, narrative_generator: FinancialRatioNarrativeGenerator | None = None
    ) -> None:
        self.narrative_generator = (
            narrative_generator or FinancialRatioNarrativeGenerator()
        )

    def build(
        self,
        result: FinancialRatioAnalysisResult,
        report_title: str | None = None,
    ) -> str:
        title = report_title or f"{result.company} — Financial Ratio Trends"
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        latest = result.latest
        narratives = self.narrative_generator.generate(result)
        ticker = (
            f"<span><strong>Ticker</strong> · {escape(result.ticker)}</span>"
            if result.ticker
            else ""
        )
        sections = "".join(
            f'''<section class="section"><h2>{escape(heading)}</h2><div class="panel table-wrap">{self._table(result, metrics)}</div></section>'''
            for heading, metrics in self.SECTIONS
        )
        body = f"""<main class="report">
  <header class="hero">
    <p class="eyebrow">Three-statement analysis · Financial ratio trends</p>
    <h1>{escape(result.company)}</h1>
    <div class="meta"><span><strong>Time frame</strong> · {escape(result.time_frame)}</span><span><strong>Schema</strong> · {escape(result.schema_profile)}</span><span><strong>Currency</strong> · {escape(result.currency)}</span>{ticker}</div>
  </header>
  <section class="kpis" aria-label="Latest financial ratios">
    {self._kpi("Current ratio", latest.current_ratio, "multiple")}
    {self._kpi("Debt ratio", latest.debt_ratio, "percent")}
    {self._kpi("Profit margin", latest.profit_margin, "percent")}
    {self._kpi("Diluted EPS", latest.earnings_per_share, "currency", result.currency)}
  </section>
  <section class="section"><h2>Trend interpretation</h2><div class="panel"><ul class="insights">{''.join(f'<li>{escape(item)}</li>' for item in narratives)}</ul></div></section>
  {sections}
  <section class="section"><h2>Calculation notes</h2><div class="panel"><ul class="notes">
    <li>Turnover, ROA, and ROE use average opening and closing balances. They are unavailable for the first period when no earlier balance sheet is in the selected time frame.</li>
    <li>Flow-based turnover, ROA, and ROE values for partial periods are annualized using 365 divided by the inclusive statement-period day count. Margins, R&amp;D intensity, coverage, and EPS remain reported year-to-date values.</li>
    <li>EPS uses the normalized filed diluted EPS. P/E is unavailable unless period-specific market prices are supplied through the application API.</li>
  </ul></div></section>
  <footer class="footer">Generated {generated} · Based on the normalized balance sheet, income statement, and cash-flow statement bundle</footer>
</main>"""
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Financial ratio time-frame trend report"><title>{escape(title)}</title><style>{self.CSS}</style></head><body>{body}</body></html>
"""

    def _table(
        self,
        result: FinancialRatioAnalysisResult,
        metrics: tuple[tuple[str, str, str], ...],
    ) -> str:
        headers = "".join(
            f"<th>{escape(period.period)}{'*' if period.annualized_flows else ''}</th>"
            for period in result.periods
        )
        rows = []
        for label, attribute, kind in metrics:
            values = "".join(
                f"<td>{self._value(getattr(period, attribute), kind, result.currency)}</td>"
                for period in result.periods
            )
            rows.append(f"<tr><td>{escape(label)}</td>{values}</tr>")
        return f"<table><thead><tr><th>Indicator</th>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"

    def _kpi(
        self,
        label: str,
        value: Decimal | None,
        kind: str,
        currency: str = "",
    ) -> str:
        return f'<div class="kpi"><span>{escape(label)}</span><strong>{self._value(value, kind, currency)}</strong></div>'

    @staticmethod
    def _value(value: Decimal | None, kind: str, currency: str) -> str:
        if value is None:
            return '<span class="na">N/A</span>'
        if kind == "percent":
            return f"{value * Decimal('100'):.2f}%"
        if kind == "days":
            return f"{value:.2f} days"
        if kind == "currency":
            return f"{escape(currency)} {value:.2f}"
        return f"{value:.2f}×"
