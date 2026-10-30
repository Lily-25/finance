"""Accessible inline SVG charts implemented with the Python standard library."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from html import escape

from ..business.analysis import FinancialAnalysisResult, FinancialMetric


@dataclass(frozen=True)
class Chart:
    title: str
    subtitle: str
    svg: str


class ChartGenerator(ABC):
    @abstractmethod
    def generate(self, result: FinancialAnalysisResult) -> tuple[Chart, ...]:
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

    def generate(self, result: FinancialAnalysisResult) -> tuple[Chart, ...]:
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


class AssetCharts(FinancialCharts):
    """Backward-compatible chart generator name."""
