"""Narrative, HTML composition, and file export for financial reports."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from pathlib import Path

from ..business.analysis import (
    FinancialAnalysisResult,
    FinancialMetric,
    TimeFrameAnalysisResult,
)
from .charts import Chart


def format_money(currency: str, value: Decimal) -> str:
    return f"{currency} {value:,.2f}"


class NarrativeGenerator:
    """Generate concise observations strictly from calculated report data."""

    def generate(
        self, result: FinancialAnalysisResult | TimeFrameAnalysisResult
    ) -> tuple[str, ...]:
        if isinstance(result, TimeFrameAnalysisResult):
            return self._generate_time_frame(result)
        currency = result.data.currency
        structure = self._asset_structure(result)

        largest_asset = result.all_asset_metrics[0]
        asset_concentration = (
            f"The largest asset line is {largest_asset.name}, at "
            f"{format_money(currency, largest_asset.amount.amount)} "
            f"({largest_asset.percentage_of_statement:.1f}% of total assets)."
        )

        if result.all_liability_metrics:
            largest_liability = result.all_liability_metrics[0]
            liability_structure = (
                f"Current liabilities represent "
                f"{result.current_liabilities_percentage:.1f}% of total liabilities; "
                f"the largest liability line is {largest_liability.name} at "
                f"{format_money(currency, largest_liability.amount.amount)} "
                f"({largest_liability.percentage_of_statement:.1f}% of liabilities)."
            )
        else:
            liability_structure = "No liabilities were reported for this period."

        ratio_text = (
            f"the current ratio is {result.current_ratio:.2f}:1"
            if result.current_ratio is not None
            else "the current ratio is not applicable because current liabilities are zero"
        )
        position = (
            f"Total liabilities equal {result.liability_to_assets_percentage:.1f}% of assets, "
            f"leaving net assets of {format_money(currency, result.net_assets)}; {ratio_text}."
        )
        return structure, asset_concentration, liability_structure, position

    def _generate_time_frame(
        self, result: TimeFrameAnalysisResult
    ) -> tuple[str, ...]:
        currency = result.data.currency
        start = result.data.start_period.label
        end = result.data.end_period.label
        asset_pct = self._change_text(result.asset_change_percentage)
        liability_pct = self._change_text(result.liability_change_percentage)
        net_asset_pct = self._change_text(result.net_asset_change_percentage)
        asset_direction = "increased" if result.asset_change >= 0 else "decreased"
        liability_direction = (
            "increased" if result.liability_change >= 0 else "decreased"
        )
        net_direction = "increased" if result.net_asset_change >= 0 else "decreased"

        assets = (
            f"Total assets {asset_direction} from "
            f"{format_money(currency, result.first.total_assets.amount)} in {start} to "
            f"{format_money(currency, result.latest.total_assets.amount)} in {end}, "
            f"a change of {asset_pct}."
        )
        liabilities = (
            f"Total liabilities {liability_direction} by {liability_pct} over the same "
            f"period, while liabilities as a share of assets moved from "
            f"{result.first.liability_to_assets_percentage:.1f}% to "
            f"{result.latest.liability_to_assets_percentage:.1f}% "
            f"({result.liability_ratio_change_points:+.1f} percentage points)."
        )
        net_assets = (
            f"Net assets {net_direction} from "
            f"{format_money(currency, result.first.net_assets)} to "
            f"{format_money(currency, result.latest.net_assets)}, a change of "
            f"{net_asset_pct}."
        )

        ratios = [
            (period.data.reporting_period.label, period.current_ratio)
            for period in result.period_results
            if period.current_ratio is not None
        ]
        if ratios:
            lowest_label, lowest_ratio = min(ratios, key=lambda item: item[1])
            latest_ratio = result.latest.current_ratio
            if latest_ratio is None:
                liquidity = (
                    f"The current ratio is not applicable in {end}; the lowest "
                    f"calculable level was {lowest_ratio:.2f}:1 in {lowest_label}."
                )
            else:
                liquidity = (
                    f"The current ratio is {latest_ratio:.2f}:1 in {end}; the lowest "
                    f"reported level was {lowest_ratio:.2f}:1 in {lowest_label}."
                )
        else:
            liquidity = (
                "No current ratio could be calculated because current liabilities "
                "were zero in every period."
            )
        return assets, liabilities, net_assets, liquidity

    @staticmethod
    def _change_text(value: Decimal | None) -> str:
        return "not comparable from a zero base" if value is None else f"{abs(value):.1f}%"

    @staticmethod
    def _asset_structure(result: FinancialAnalysisResult) -> str:
        if abs(result.current_percentage - result.non_current_percentage) < Decimal("5"):
            return (
                f"The asset base is broadly balanced: current assets are "
                f"{result.current_percentage:.1f}% and non-current assets are "
                f"{result.non_current_percentage:.1f}% of the total."
            )
        if result.non_current_percentage > result.current_percentage:
            larger_name = "Non-current assets"
            larger_pct = result.non_current_percentage
            smaller_name = "current assets"
            smaller_pct = result.current_percentage
        else:
            larger_name = "Current assets"
            larger_pct = result.current_percentage
            smaller_name = "non-current assets"
            smaller_pct = result.non_current_percentage
        return (
            f"{larger_name} represent {larger_pct:.1f}% of total assets, compared "
            f"with {smaller_pct:.1f}% for {smaller_name}."
        )


class ReportTemplate:
    CSS = r"""
:root {
  color-scheme: light;
  --ink: #172033;
  --muted: #64748b;
  --line: #e5eaf2;
  --surface: #ffffff;
  --canvas: #f4f7fb;
  --blue: #2563eb;
  --purple: #7c3aed;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background: var(--canvas);
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
.report { width: min(1180px, calc(100% - 40px)); margin: 34px auto 56px; }
.hero {
  position: relative;
  overflow: hidden;
  padding: 48px 52px;
  border-radius: 24px;
  color: white;
  background: linear-gradient(125deg, #14213d 0%, #243b6b 58%, #4338ca 100%);
  box-shadow: 0 24px 70px rgba(20, 33, 61, .18);
}
.hero::after {
  content: "";
  position: absolute;
  width: 320px;
  height: 320px;
  right: -110px;
  top: -150px;
  border: 56px solid rgba(255,255,255,.09);
  border-radius: 50%;
}
.eyebrow { margin: 0 0 10px; text-transform: uppercase; letter-spacing: .14em; font-size: 12px; font-weight: 750; opacity: .78; }
h1 { max-width: 760px; margin: 0; font-size: clamp(34px, 5vw, 58px); line-height: 1.04; letter-spacing: -.045em; }
.hero-meta { display: flex; gap: 18px 32px; flex-wrap: wrap; margin-top: 24px; color: rgba(255,255,255,.82); }
.hero-meta strong { color: white; }
.section { margin-top: 26px; }
.section-heading { margin: 0 0 14px; font-size: 21px; letter-spacing: -.02em; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: -18px; position: relative; padding: 0 22px; }
.kpi, .panel, .chart-card {
  background: var(--surface);
  border: 1px solid rgba(229,234,242,.9);
  box-shadow: 0 12px 36px rgba(23,32,51,.065);
}
.kpi { min-width: 0; padding: 22px; border-radius: 16px; }
.kpi-label { color: var(--muted); font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .08em; }
.kpi-value { display: block; margin-top: 8px; font-size: clamp(19px, 2.2vw, 28px); font-weight: 780; letter-spacing: -.035em; overflow-wrap: anywhere; }
.kpi-note { display: block; color: var(--muted); margin-top: 3px; font-size: 13px; }
.panel { border-radius: 18px; padding: 27px 30px; }
.insights { margin: 0; padding: 0; list-style: none; display: grid; gap: 17px; }
.insights li { display: grid; grid-template-columns: 28px 1fr; gap: 12px; }
.insights li::before { content: ""; width: 10px; height: 10px; margin-top: 7px; border-radius: 3px; background: linear-gradient(135deg, var(--blue), var(--purple)); }
.chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 18px; }
.chart-card { overflow: hidden; border-radius: 18px; }
.chart-copy { padding: 24px 26px 6px; }
.chart-copy h3 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
.chart-copy p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
.chart-frame { padding: 6px 16px 18px; overflow-x: auto; }
.chart-svg { display: block; width: 100%; min-width: 540px; height: auto; }
.svg-kicker, .svg-note, .svg-label, .svg-value, .svg-value-sm, .svg-number { font-family: inherit; fill: var(--ink); }
.svg-kicker { font-size: 11px; fill: var(--muted); font-weight: 700; letter-spacing: .08em; }
.svg-value { font-size: 17px; font-weight: 750; }
.svg-value-sm { font-size: 19px; font-weight: 750; }
.svg-label { font-size: 13px; font-weight: 650; }
.svg-number { font-size: 13px; font-weight: 760; }
.svg-note { font-size: 11px; fill: var(--muted); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th { padding: 12px 15px; color: var(--muted); font-size: 11px; text-align: left; text-transform: uppercase; letter-spacing: .08em; border-bottom: 1px solid var(--line); }
td { padding: 14px 15px; border-bottom: 1px solid var(--line); }
th.number, td.number { text-align: right; }
tr:last-child td { border-bottom: 0; }
.badge { display: inline-flex; padding: 4px 9px; border-radius: 999px; background: #eef4ff; color: #1d4ed8; font-size: 12px; font-weight: 700; }
.badge.non-current { background: #f3efff; color: #6d28d9; }
.total-row td { background: #f8fafc; font-weight: 780; }
.footer { color: var(--muted); text-align: center; font-size: 12px; margin-top: 26px; }
@media (max-width: 900px) {
  .kpis { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 700px) {
  .report { width: min(100% - 24px, 1180px); margin-top: 12px; }
  .hero { padding: 36px 28px 48px; border-radius: 18px; }
  .kpis { grid-template-columns: 1fr; margin-top: -26px; }
  .chart-grid { grid-template-columns: 1fr; }
}
@media print {
  body { background: white; }
  .report { width: 100%; margin: 0; }
  .hero, .kpi, .panel, .chart-card { box-shadow: none; break-inside: avoid; }
  .chart-grid { grid-template-columns: 1fr 1fr; }
}
"""

    def render(self, title: str, body: str) -> str:
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Asset, liability, liquidity, and leverage report">
  <title>{escape(title)}</title>
  <style>{self.CSS}</style>
</head>
<body>{body}</body>
</html>
"""


class ReportBuilder:
    def __init__(
        self,
        narrative_generator: NarrativeGenerator | None = None,
        template: ReportTemplate | None = None,
    ) -> None:
        self.narrative_generator = narrative_generator or NarrativeGenerator()
        self.template = template or ReportTemplate()

    def build(
        self,
        result: FinancialAnalysisResult | TimeFrameAnalysisResult,
        charts: tuple[Chart, ...],
        report_title: str | None = None,
    ) -> str:
        if isinstance(result, TimeFrameAnalysisResult):
            return self._build_time_frame(result, charts, report_title)
        data = result.data
        title = report_title or f"{data.company.name} — Financial Position Report"
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        narratives = self.narrative_generator.generate(result)
        ticker_meta = (
            f"<span><strong>Ticker</strong> · {escape(data.company.ticker)}</span>"
            if data.company.ticker
            else ""
        )
        body = f"""<main class="report">
  <header class="hero">
    <p class="eyebrow">Financial analysis · Statement of financial position</p>
    <h1>{escape(data.company.name)}</h1>
    <div class="hero-meta">
      <span><strong>Period</strong> · {escape(data.reporting_period.label)}</span>
      <span><strong>Currency</strong> · {escape(data.currency)}</span>
      {ticker_meta}
    </div>
  </header>
  {self._kpis(result)}
  <section class="section" aria-labelledby="interpretation-heading">
    <h2 id="interpretation-heading" class="section-heading">Interpretation</h2>
    <div class="panel"><ul class="insights">{''.join(f'<li>{escape(item)}</li>' for item in narratives)}</ul></div>
  </section>
  <section class="section" aria-labelledby="visual-heading">
    <h2 id="visual-heading" class="section-heading">Visual analysis</h2>
    <div class="chart-grid">{''.join(self._chart_card(chart) for chart in charts)}</div>
  </section>
  <section class="section" aria-labelledby="asset-detail-heading">
    <h2 id="asset-detail-heading" class="section-heading">Asset detail</h2>
    <div class="panel table-wrap">{self._asset_table(result)}</div>
  </section>
  <section class="section" aria-labelledby="liability-detail-heading">
    <h2 id="liability-detail-heading" class="section-heading">Liability detail</h2>
    <div class="panel table-wrap">{self._liability_table(result)}</div>
  </section>
  <footer class="footer">Generated {generated} · Amounts shown in {escape(data.currency)}</footer>
</main>"""
        return self.template.render(title, body)

    def _build_time_frame(
        self,
        result: TimeFrameAnalysisResult,
        charts: tuple[Chart, ...],
        report_title: str | None,
    ) -> str:
        data = result.data
        title = report_title or f"{data.company.name} — Time-Frame Financial Report"
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        narratives = self.narrative_generator.generate(result)
        ticker_meta = (
            f"<span><strong>Ticker</strong> · {escape(data.company.ticker)}</span>"
            if data.company.ticker
            else ""
        )
        latest = result.latest
        body = f"""<main class="report">
  <header class="hero">
    <p class="eyebrow">Financial analysis · Time-frame comparison</p>
    <h1>{escape(data.company.name)}</h1>
    <div class="hero-meta">
      <span><strong>Time frame</strong> · {escape(data.time_frame)}</span>
      <span><strong>Periods</strong> · {len(result.period_results)}</span>
      <span><strong>Currency</strong> · {escape(data.currency)}</span>
      {ticker_meta}
    </div>
  </header>
  {self._time_frame_kpis(result)}
  <section class="section" aria-labelledby="interpretation-heading">
    <h2 id="interpretation-heading" class="section-heading">Trend interpretation</h2>
    <div class="panel"><ul class="insights">{''.join(f'<li>{escape(item)}</li>' for item in narratives)}</ul></div>
  </section>
  <section class="section" aria-labelledby="visual-heading">
    <h2 id="visual-heading" class="section-heading">Time-series analysis</h2>
    <div class="chart-grid">{''.join(self._chart_card(chart) for chart in charts)}</div>
  </section>
  <section class="section" aria-labelledby="period-heading">
    <h2 id="period-heading" class="section-heading">Period comparison</h2>
    <div class="panel table-wrap">{self._time_frame_table(result)}</div>
  </section>
  <section class="section" aria-labelledby="latest-asset-heading">
    <h2 id="latest-asset-heading" class="section-heading">Latest asset detail · {escape(latest.data.reporting_period.label)}</h2>
    <div class="panel table-wrap">{self._asset_table(latest)}</div>
  </section>
  <section class="section" aria-labelledby="latest-liability-heading">
    <h2 id="latest-liability-heading" class="section-heading">Latest liability detail · {escape(latest.data.reporting_period.label)}</h2>
    <div class="panel table-wrap">{self._liability_table(latest)}</div>
  </section>
  <footer class="footer">Generated {generated} · Amounts shown in {escape(data.currency)}</footer>
</main>"""
        return self.template.render(title, body)

    @staticmethod
    def _time_frame_kpis(result: TimeFrameAnalysisResult) -> str:
        currency = escape(result.data.currency)
        latest = result.latest
        asset_change = (
            "N/A"
            if result.asset_change_percentage is None
            else f"{result.asset_change_percentage:+.1f}%"
        )
        ratio = (
            f"{latest.current_ratio:.2f}:1"
            if latest.current_ratio is not None
            else "Not applicable"
        )
        return f"""<section class="kpis" aria-label="Latest period and trend totals">
  <div class="kpi"><span class="kpi-label">Latest assets</span><strong class="kpi-value">{currency} {latest.total_assets.amount:,.2f}</strong><span class="kpi-note">{asset_change} over the time frame</span></div>
  <div class="kpi"><span class="kpi-label">Latest liabilities</span><strong class="kpi-value">{currency} {latest.total_liabilities.amount:,.2f}</strong><span class="kpi-note">{latest.liability_to_assets_percentage:.1f}% of assets</span></div>
  <div class="kpi"><span class="kpi-label">Latest net assets</span><strong class="kpi-value">{currency} {latest.net_assets:,.2f}</strong><span class="kpi-note">Assets less liabilities</span></div>
  <div class="kpi"><span class="kpi-label">Latest current ratio</span><strong class="kpi-value">{ratio}</strong><span class="kpi-note">At {escape(latest.data.reporting_period.label)}</span></div>
</section>"""

    @staticmethod
    def _time_frame_table(result: TimeFrameAnalysisResult) -> str:
        rows: list[str] = []
        currency = escape(result.data.currency)
        for period in result.period_results:
            ratio = (
                f"{period.current_ratio:.2f}:1"
                if period.current_ratio is not None
                else "N/A"
            )
            rows.append(
                f"""<tr>
  <td>{escape(period.data.reporting_period.label)}</td>
  <td class="number">{currency} {period.total_assets.amount:,.2f}</td>
  <td class="number">{currency} {period.total_liabilities.amount:,.2f}</td>
  <td class="number">{currency} {period.net_assets:,.2f}</td>
  <td class="number">{period.liability_to_assets_percentage:.1f}%</td>
  <td class="number">{ratio}</td>
</tr>"""
            )
        return f"""<table>
  <thead><tr><th>Period</th><th class="number">Assets</th><th class="number">Liabilities</th><th class="number">Net assets</th><th class="number">Liabilities / assets</th><th class="number">Current ratio</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""

    @staticmethod
    def _kpis(result: FinancialAnalysisResult) -> str:
        currency = escape(result.data.currency)
        ratio = (
            f"{result.current_ratio:.2f}:1"
            if result.current_ratio is not None
            else "Not applicable"
        )
        return f"""<section class="kpis" aria-label="Key totals">
  <div class="kpi"><span class="kpi-label">Total assets</span><strong class="kpi-value">{currency} {result.total_assets.amount:,.2f}</strong><span class="kpi-note">100.0% of reported assets</span></div>
  <div class="kpi"><span class="kpi-label">Total liabilities</span><strong class="kpi-value">{currency} {result.total_liabilities.amount:,.2f}</strong><span class="kpi-note">{result.liability_to_assets_percentage:.1f}% of total assets</span></div>
  <div class="kpi"><span class="kpi-label">Net assets</span><strong class="kpi-value">{currency} {result.net_assets:,.2f}</strong><span class="kpi-note">Assets less liabilities</span></div>
  <div class="kpi"><span class="kpi-label">Current ratio</span><strong class="kpi-value">{ratio}</strong><span class="kpi-note">Current assets / current liabilities</span></div>
</section>"""

    @staticmethod
    def _chart_card(chart: Chart) -> str:
        return f"""<article class="chart-card">
  <div class="chart-copy"><h3>{escape(chart.title)}</h3><p>{escape(chart.subtitle)}</p></div>
  <div class="chart-frame">{chart.svg}</div>
</article>"""

    @classmethod
    def _asset_table(cls, result: FinancialAnalysisResult) -> str:
        rows = cls._metric_rows(
            result.all_asset_metrics,
            result.data.currency,
            "percentage_of_statement",
        )
        rows.append(
            f"""<tr class="total-row"><td>Total assets</td><td>—</td><td class="number">{escape(result.data.currency)} {result.total_assets.amount:,.2f}</td><td class="number">100.0%</td></tr>"""
        )
        return f"""<table>
  <thead><tr><th>Asset</th><th>Classification</th><th class="number">Amount</th><th class="number">% of assets</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""

    @classmethod
    def _liability_table(cls, result: FinancialAnalysisResult) -> str:
        rows = cls._metric_rows(
            result.all_liability_metrics,
            result.data.currency,
            "percentage_of_statement",
            include_assets_percentage=True,
        )
        if not rows:
            rows.append(
                '<tr><td colspan="5">No liabilities reported.</td></tr>'
            )
        rows.append(
            f"""<tr class="total-row"><td>Total liabilities</td><td>—</td><td class="number">{escape(result.data.currency)} {result.total_liabilities.amount:,.2f}</td><td class="number">{('100.0%' if result.total_liabilities.amount else '0.0%')}</td><td class="number">{result.liability_to_assets_percentage:.1f}%</td></tr>"""
        )
        return f"""<table>
  <thead><tr><th>Liability</th><th>Classification</th><th class="number">Amount</th><th class="number">% of liabilities</th><th class="number">% of assets</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""

    @staticmethod
    def _metric_rows(
        metrics: tuple[FinancialMetric, ...],
        currency: str,
        percentage_field: str,
        include_assets_percentage: bool = False,
    ) -> list[str]:
        rows: list[str] = []
        for metric in metrics:
            badge_class = "non-current" if metric.classification == "Non-current" else ""
            assets_cell = (
                f'<td class="number">{metric.percentage_of_assets:.1f}%</td>'
                if include_assets_percentage
                else ""
            )
            percentage = getattr(metric, percentage_field)
            rows.append(
                f"""<tr>
  <td>{escape(metric.name)}</td>
  <td><span class="badge {badge_class}">{escape(metric.classification)}</span></td>
  <td class="number">{escape(currency)} {metric.amount.amount:,.2f}</td>
  <td class="number">{percentage:.1f}%</td>{assets_cell}
</tr>"""
            )
        return rows


class ReportFileExporter:
    def export(self, html: str, destination: str | Path) -> Path:
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        try:
            temporary.write_text(html, encoding="utf-8")
            temporary.replace(output)
        except OSError as exc:
            raise OSError(f"Could not write report to {output}: {exc}") from exc
        return output.resolve()
