"""Narrative, HTML composition, and file export for asset reports."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from pathlib import Path

from ..business.analysis import AssetAnalysisResult, AssetMetric
from .charts import Chart


def format_money(currency: str, value: Decimal) -> str:
    return f"{currency} {value:,.2f}"


class NarrativeGenerator:
    """Generate concise observations strictly from calculated report data."""

    def generate(self, result: AssetAnalysisResult) -> tuple[str, ...]:
        currency = result.data.currency
        if abs(result.current_percentage - result.non_current_percentage) < Decimal("5"):
            structure = (
                f"The asset base is broadly balanced: current assets are "
                f"{result.current_percentage:.1f}% and non-current assets are "
                f"{result.non_current_percentage:.1f}% of the total."
            )
        else:
            larger_name, larger_pct, smaller_name, smaller_pct = (
                (
                    "Non-current assets",
                    result.non_current_percentage,
                    "current assets",
                    result.current_percentage,
                )
                if result.non_current_percentage > result.current_percentage
                else (
                    "Current assets",
                    result.current_percentage,
                    "non-current assets",
                    result.non_current_percentage,
                )
            )
            structure = (
                f"{larger_name} represent {larger_pct:.1f}% of total assets, compared "
                f"with {smaller_pct:.1f}% for {smaller_name}."
            )

        ranked = result.all_metrics
        largest = ranked[0]
        top_count = min(3, len(ranked))
        top_total = sum(
            (metric.amount.amount for metric in ranked[:top_count]), Decimal("0")
        )
        top_pct = (top_total / result.total_assets.amount) * Decimal("100")
        concentration_label = {
            1: "the largest item",
            2: "the two largest items",
            3: "the three largest items",
        }[top_count]
        concentration_verb = "accounts" if top_count == 1 else "account"
        concentration = (
            f"The largest line item is {largest.name}, at "
            f"{format_money(currency, largest.amount.amount)} "
            f"({largest.percentage_of_total:.1f}% of total assets); {concentration_label} "
            f"{concentration_verb} for {top_pct:.1f}%."
        )

        composition_parts: list[str] = []
        if result.current_metrics:
            current = result.current_metrics[0]
            composition_parts.append(
                f"Within current assets, {current.name} is the largest component "
                f"at {current.percentage_of_class:.1f}%"
            )
        if result.non_current_metrics:
            non_current = result.non_current_metrics[0]
            composition_parts.append(
                f"within non-current assets, {non_current.name} leads at "
                f"{non_current.percentage_of_class:.1f}%"
            )
        composition = "; ".join(composition_parts) + "."
        composition = composition[0].upper() + composition[1:]
        return structure, concentration, composition


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
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: -18px; position: relative; padding: 0 22px; }
.kpi, .panel, .chart-card {
  background: var(--surface);
  border: 1px solid rgba(229,234,242,.9);
  box-shadow: 0 12px 36px rgba(23,32,51,.065);
}
.kpi { min-width: 0; padding: 23px 24px; border-radius: 16px; }
.kpi-label { color: var(--muted); font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .08em; }
.kpi-value { display: block; margin-top: 8px; font-size: clamp(21px, 2.5vw, 30px); font-weight: 780; letter-spacing: -.035em; overflow-wrap: anywhere; }
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
@media (max-width: 820px) {
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
  <meta name="description" content="Asset composition and concentration report">
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
        result: AssetAnalysisResult,
        charts: tuple[Chart, ...],
        report_title: str | None = None,
    ) -> str:
        data = result.data
        title = report_title or f"{data.company.name} — Asset Report"
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        narratives = self.narrative_generator.generate(result)
        ticker_meta = (
            f"<span><strong>Ticker</strong> · {escape(data.company.ticker)}</span>"
            if data.company.ticker
            else ""
        )
        body = f"""<main class="report">
  <header class="hero">
    <p class="eyebrow">Financial analysis · Asset report</p>
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
  <section class="section" aria-labelledby="detail-heading">
    <h2 id="detail-heading" class="section-heading">Asset detail</h2>
    <div class="panel table-wrap">{self._table(result)}</div>
  </section>
  <footer class="footer">Generated {generated} · Amounts shown in {escape(data.currency)}</footer>
</main>"""
        return self.template.render(title, body)

    @staticmethod
    def _kpis(result: AssetAnalysisResult) -> str:
        currency = escape(result.data.currency)
        return f"""<section class="kpis" aria-label="Key totals">
  <div class="kpi"><span class="kpi-label">Total assets</span><strong class="kpi-value">{currency} {result.total_assets.amount:,.2f}</strong><span class="kpi-note">100.0% of reported assets</span></div>
  <div class="kpi"><span class="kpi-label">Current assets</span><strong class="kpi-value">{currency} {result.current_total.amount:,.2f}</strong><span class="kpi-note">{result.current_percentage:.1f}% of total assets</span></div>
  <div class="kpi"><span class="kpi-label">Non-current assets</span><strong class="kpi-value">{currency} {result.non_current_total.amount:,.2f}</strong><span class="kpi-note">{result.non_current_percentage:.1f}% of total assets</span></div>
</section>"""

    @staticmethod
    def _chart_card(chart: Chart) -> str:
        return f"""<article class="chart-card">
  <div class="chart-copy"><h3>{escape(chart.title)}</h3><p>{escape(chart.subtitle)}</p></div>
  <div class="chart-frame">{chart.svg}</div>
</article>"""

    @staticmethod
    def _table(result: AssetAnalysisResult) -> str:
        rows: list[str] = []
        for metric in result.all_metrics:
            badge_class = "non-current" if metric.classification == "Non-current" else ""
            rows.append(
                f"""<tr>
  <td>{escape(metric.name)}</td>
  <td><span class="badge {badge_class}">{escape(metric.classification)}</span></td>
  <td class="number">{escape(result.data.currency)} {metric.amount.amount:,.2f}</td>
  <td class="number">{metric.percentage_of_total:.1f}%</td>
</tr>"""
            )
        rows.append(
            f"""<tr class="total-row"><td>Total assets</td><td>—</td><td class="number">{escape(result.data.currency)} {result.total_assets.amount:,.2f}</td><td class="number">100.0%</td></tr>"""
        )
        return f"""<table>
  <thead><tr><th>Asset</th><th>Classification</th><th class="number">Amount</th><th class="number">% of total</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""


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
