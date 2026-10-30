"""Accessible inline SVG charts implemented with the Python standard library."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from html import escape

from ..business.analysis import (
    FinancialAnalysisResult,
    FinancialMetric,
    TimeFrameAnalysisResult,
)


@dataclass(frozen=True)
class Chart:
    title: str
    subtitle: str
    svg: str


class ChartGenerator(ABC):
    @abstractmethod
    def generate(
        self, result: FinancialAnalysisResult | TimeFrameAnalysisResult
    ) -> tuple[Chart, ...]:
        """Create the report's complete four-chart set."""


class FinancialCharts(ChartGenerator):
    BLUE = "#2563eb"
    PURPLE = "#7c3aed"
    TEAL = "#0f766e"
    AMBER = "#d97706"
    INK = "#172033"
    MUTED = "#64748b"
    TRACK = "#e9eef7"
    PALETTE = (BLUE, PURPLE, TEAL, AMBER, "#db2777", "#0891b2", "#65a30d")

    def generate(
        self, result: FinancialAnalysisResult | TimeFrameAnalysisResult
    ) -> tuple[Chart, ...]:
        if isinstance(result, TimeFrameAnalysisResult):
            return self._time_frame_charts(result)
        return (
            Chart(
                "Asset structure",
                "Current and non-current share of total assets",
                self._structure_donut(
                    "Asset structure",
                    "TOTAL ASSETS",
                    result.current_total.amount,
                    result.non_current_total.amount,
                    result.total_assets.amount,
                    result.current_percentage,
                    result.non_current_percentage,
                    result.data.currency,
                    "Current assets",
                    "Non-current assets",
                ),
            ),
            Chart(
                "Liability structure",
                "Current and non-current share of total liabilities",
                self._structure_donut(
                    "Liability structure",
                    "TOTAL LIABILITIES",
                    result.current_liabilities_total.amount,
                    result.non_current_liabilities_total.amount,
                    result.total_liabilities.amount,
                    result.current_liabilities_percentage,
                    result.non_current_liabilities_percentage,
                    result.data.currency,
                    "Current liabilities",
                    "Non-current liabilities",
                ),
            ),
            Chart(
                "Largest asset categories",
                "All asset line items ranked by share of total assets",
                self._horizontal_bars(
                    result.all_asset_metrics,
                    "Largest asset categories",
                    "statement",
                ),
            ),
            Chart(
                "Largest liability categories",
                "All liability line items ranked by share of total liabilities",
                self._horizontal_bars(
                    result.all_liability_metrics,
                    "Largest liability categories",
                    "statement",
                ),
            ),
        )

    def _time_frame_charts(
        self, result: TimeFrameAnalysisResult
    ) -> tuple[Chart, ...]:
        labels = tuple(
            period.data.reporting_period.label for period in result.period_results
        )
        return (
            Chart(
                "Assets and liabilities over time",
                "Period-end totals for the selected time frame",
                self._comparison_bars(result),
            ),
            Chart(
                "Net assets trend",
                "Total assets less total liabilities",
                self._line_chart(
                    "Net assets trend",
                    labels,
                    tuple(period.net_assets for period in result.period_results),
                    self.TEAL,
                    value_format="money",
                ),
            ),
            Chart(
                "Current ratio trend",
                "Current assets divided by current liabilities",
                self._line_chart(
                    "Current ratio trend",
                    labels,
                    tuple(period.current_ratio for period in result.period_results),
                    self.BLUE,
                    value_format="ratio",
                ),
            ),
            Chart(
                "Liabilities to assets",
                "Leverage as a percentage of total assets",
                self._line_chart(
                    "Liabilities to assets",
                    labels,
                    tuple(
                        period.liability_to_assets_percentage
                        for period in result.period_results
                    ),
                    self.PURPLE,
                    value_format="percent",
                ),
            ),
        )

    def _comparison_bars(self, result: TimeFrameAnalysisResult) -> str:
        periods = result.period_results
        maximum = max(period.total_assets.amount for period in periods)
        plot_top = 48
        plot_bottom = 270
        plot_height = plot_bottom - plot_top
        group_width = 650 / len(periods)
        bar_width = min(48, group_width * 0.3)
        rows: list[str] = []
        aria_parts: list[str] = []
        for index, period in enumerate(periods):
            center = 100 + group_width * index + group_width / 2
            asset_height = float(period.total_assets.amount / maximum) * plot_height
            liability_height = float(period.total_liabilities.amount / maximum) * plot_height
            asset_x = center - bar_width - 4
            liability_x = center + 4
            label = escape(period.data.reporting_period.label)
            asset_value = escape(self._compact_amount(period.total_assets.amount))
            liability_value = escape(self._compact_amount(period.total_liabilities.amount))
            aria_parts.append(
                f"{period.data.reporting_period.label}: assets {asset_value}, "
                f"liabilities {liability_value}"
            )
            rows.append(
                f'''<g>
  <rect x="{asset_x:.2f}" y="{plot_bottom - asset_height:.2f}" width="{bar_width:.2f}" height="{asset_height:.2f}" rx="5" fill="{self.BLUE}"/>
  <rect x="{liability_x:.2f}" y="{plot_bottom - liability_height:.2f}" width="{bar_width:.2f}" height="{liability_height:.2f}" rx="5" fill="{self.PURPLE}"/>
  <text x="{asset_x + bar_width / 2:.2f}" y="{plot_bottom - asset_height - 8:.2f}" text-anchor="middle" class="svg-note">{asset_value}</text>
  <text x="{liability_x + bar_width / 2:.2f}" y="{plot_bottom - liability_height - 8:.2f}" text-anchor="middle" class="svg-note">{liability_value}</text>
  <text x="{center:.2f}" y="296" text-anchor="middle" class="svg-label">{label}</text>
</g>'''
            )
        aria = escape("; ".join(aria_parts))
        return f'''<svg class="chart-svg" viewBox="0 0 800 340" role="img" aria-label="{aria}">
  <title>Assets and liabilities over time</title>
  <line x1="80" y1="270" x2="760" y2="270" stroke="{self.TRACK}" stroke-width="2"/>
  {"".join(rows)}
  {self._legend_row(280, 330, self.BLUE, "Assets", "")}
  {self._legend_row(470, 330, self.PURPLE, "Liabilities", "")}
</svg>'''

    def _line_chart(
        self,
        title: str,
        labels: tuple[str, ...],
        values: tuple[Decimal | None, ...],
        color: str,
        value_format: str,
    ) -> str:
        valid_values = [value for value in values if value is not None]
        if not valid_values:
            return self._empty_chart(title, "No comparable values")
        minimum = min(Decimal("0"), min(valid_values))
        maximum = max(valid_values)
        span = maximum - minimum
        if span == 0:
            span = Decimal("1")
        plot_left = 90
        plot_right = 730
        plot_top = 54
        plot_bottom = 250
        x_step = (plot_right - plot_left) / max(1, len(labels) - 1)
        points: list[str] = []
        circles: list[str] = []
        aria_parts: list[str] = []
        for index, (label, value) in enumerate(zip(labels, values)):
            x = plot_left + index * x_step
            escaped_label = escape(label)
            if value is None:
                circles.append(
                    f'<text x="{x:.2f}" y="150" text-anchor="middle" class="svg-note">N/A</text>'
                )
                continue
            y = plot_bottom - float((value - minimum) / span) * (
                plot_bottom - plot_top
            )
            formatted = self._format_trend_value(value, value_format)
            aria_parts.append(f"{label} {formatted}")
            points.append(f"{x:.2f},{y:.2f}")
            circles.append(
                f'''<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{color}" stroke="#ffffff" stroke-width="3"/>
  <text x="{x:.2f}" y="{y - 14:.2f}" text-anchor="middle" class="svg-number">{escape(formatted)}</text>
  <text x="{x:.2f}" y="278" text-anchor="middle" class="svg-label">{escaped_label}</text>'''
            )
        path = " ".join(points)
        aria = escape("; ".join(aria_parts))
        return f'''<svg class="chart-svg" viewBox="0 0 800 310" role="img" aria-label="{aria}">
  <title>{escape(title)}</title>
  <line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="{self.TRACK}" stroke-width="2"/>
  <polyline points="{path}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  {"".join(circles)}
</svg>'''

    def _format_trend_value(self, value: Decimal, value_format: str) -> str:
        if value_format == "money":
            return self._compact_amount(value)
        if value_format == "ratio":
            return f"{value:.2f}:1"
        return f"{value:.1f}%"

    def _structure_donut(
        self,
        title: str,
        total_label: str,
        current_amount: Decimal,
        non_current_amount: Decimal,
        total_amount: Decimal,
        current_percentage: Decimal,
        non_current_percentage: Decimal,
        currency: str,
        current_label_text: str,
        non_current_label_text: str,
    ) -> str:
        if total_amount == 0:
            return self._empty_chart(title, "No liabilities reported")
        current = float(current_percentage)
        current_label = self._percent(current_percentage)
        non_current_label = self._percent(non_current_percentage)
        escaped_currency = escape(currency)
        total = escape(self._amount(total_amount))
        aria = escape(
            f"{current_label_text} {current_label}; "
            f"{non_current_label_text} {non_current_label}"
        )
        return f"""<svg class="chart-svg" viewBox="0 0 800 320" role="img" aria-label="{aria}">
  <title>{escape(title)}</title>
  <circle cx="190" cy="150" r="94" fill="none" stroke="{self.TRACK}" stroke-width="34"/>
  <circle cx="190" cy="150" r="94" fill="none" stroke="{self.PURPLE}" stroke-width="34"/>
  <circle cx="190" cy="150" r="94" fill="none" stroke="{self.BLUE}" stroke-width="34"
    pathLength="100" stroke-dasharray="{current:.4f} {100-current:.4f}"
    transform="rotate(-90 190 150)"/>
  <text x="190" y="143" text-anchor="middle" class="svg-kicker">{escape(total_label)}</text>
  <text x="190" y="171" text-anchor="middle" class="svg-value">{escaped_currency} {total}</text>
  {self._legend_row(390, 115, self.BLUE, current_label_text, current_label)}
  {self._legend_row(390, 185, self.PURPLE, non_current_label_text, non_current_label)}
</svg>"""

    def _horizontal_bars(
        self,
        metrics: tuple[FinancialMetric, ...],
        title: str,
        percentage_basis: str,
    ) -> str:
        if not metrics:
            return self._empty_chart(title, "No categories reported")

        row_height = 58
        height = max(230, 78 + len(metrics) * row_height)
        max_amount = max(metric.amount.amount for metric in metrics)
        rows: list[str] = []
        for index, metric in enumerate(metrics):
            y = 54 + index * row_height
            ratio = float(metric.amount.amount / max_amount) if max_amount else 0
            width = max(0.0, ratio * 420)
            percentage = (
                metric.percentage_of_statement
                if percentage_basis == "statement"
                else metric.percentage_of_class
            )
            name = escape(metric.name)
            value = escape(self._amount(metric.amount.amount))
            pct = self._percent(percentage)
            color = self.PALETTE[index % len(self.PALETTE)]
            rows.append(
                f'''<g>
  <text x="24" y="{y + 7}" class="svg-label">{name}</text>
  <rect x="265" y="{y - 12}" width="420" height="22" rx="6" fill="{self.TRACK}"/>
  <rect x="265" y="{y - 12}" width="{width:.2f}" height="22" rx="6" fill="{color}"/>
  <text x="704" y="{y + 6}" class="svg-number">{pct}</text>
  <text x="265" y="{y + 28}" class="svg-note">{value}</text>
</g>'''
            )
        aria = escape(f"{title}, {len(metrics)} categories")
        return f'''<svg class="chart-svg" viewBox="0 0 800 {height}" role="img" aria-label="{aria}">
  <title>{escape(title)}</title>
  {"".join(rows)}
</svg>'''

    def _empty_chart(self, title: str, message: str) -> str:
        return f'''<svg class="chart-svg" viewBox="0 0 800 220" role="img" aria-label="{escape(title)} has no data">
  <title>{escape(title)}</title>
  <rect x="20" y="20" width="760" height="180" rx="16" fill="{self.TRACK}"/>
  <text x="400" y="118" text-anchor="middle" class="svg-label">{escape(message)}</text>
</svg>'''

    def _legend_row(self, x: int, y: int, color: str, label: str, value: str) -> str:
        return f'''<rect x="{x}" y="{y - 16}" width="16" height="16" rx="4" fill="{color}"/>
  <text x="{x + 30}" y="{y - 3}" class="svg-label">{escape(label)}</text>
  <text x="710" y="{y - 3}" text-anchor="end" class="svg-value-sm">{escape(value)}</text>'''

    @staticmethod
    def _percent(value: Decimal) -> str:
        return f"{value:.1f}%"

    @staticmethod
    def _amount(value: Decimal) -> str:
        return f"{value:,.2f}"

    @staticmethod
    def _compact_amount(value: Decimal) -> str:
        absolute = abs(value)
        if absolute >= Decimal("1000000000"):
            return f"{value / Decimal('1000000000'):.1f}B"
        if absolute >= Decimal("1000000"):
            return f"{value / Decimal('1000000'):.1f}M"
        if absolute >= Decimal("1000"):
            return f"{value / Decimal('1000'):.1f}K"
        return f"{value:,.0f}"


class AssetCharts(FinancialCharts):
    """Backward-compatible chart generator name."""
