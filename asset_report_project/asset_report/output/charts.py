"""Accessible inline SVG charts implemented with the Python standard library."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from html import escape

from ..business.analysis import AssetAnalysisResult, AssetMetric


@dataclass(frozen=True)
class Chart:
    title: str
    subtitle: str
    svg: str


class ChartGenerator(ABC):
    @abstractmethod
    def generate(self, result: AssetAnalysisResult) -> tuple[Chart, ...]:
        """Create a report's complete chart set."""


class AssetCharts(ChartGenerator):
    BLUE = "#2563eb"
    PURPLE = "#7c3aed"
    TEAL = "#0f766e"
    AMBER = "#d97706"
    INK = "#172033"
    MUTED = "#64748b"
    TRACK = "#e9eef7"
    PALETTE = (BLUE, PURPLE, TEAL, AMBER, "#db2777", "#0891b2", "#65a30d")

    def generate(self, result: AssetAnalysisResult) -> tuple[Chart, ...]:
        return (
            Chart(
                "Asset structure",
                "Current and non-current share of total assets",
                self._structure_donut(result),
            ),
            Chart(
                "Current asset composition",
                "Each line item as a share of current assets",
                self._horizontal_bars(
                    result.current_metrics, "Current asset composition", "class"
                ),
            ),
            Chart(
                "Non-current asset composition",
                "Each line item as a share of non-current assets",
                self._horizontal_bars(
                    result.non_current_metrics,
                    "Non-current asset composition",
                    "class",
                ),
            ),
            Chart(
                "Largest asset categories",
                "All line items ranked by share of total assets",
                self._horizontal_bars(
                    result.all_metrics, "Largest asset categories", "total"
                ),
            ),
        )

    def _structure_donut(self, result: AssetAnalysisResult) -> str:
        current = float(result.current_percentage)
        current_label = self._percent(result.current_percentage)
        non_current_label = self._percent(result.non_current_percentage)
        currency = escape(result.data.currency)
        total = escape(self._amount(result.total_assets.amount))
        aria = escape(
            f"Current assets {current_label}; non-current assets {non_current_label}"
        )
        return f"""<svg class="chart-svg" viewBox="0 0 800 320" role="img" aria-label="{aria}">
  <title>Asset structure</title>
  <circle cx="190" cy="150" r="94" fill="none" stroke="{self.TRACK}" stroke-width="34"/>
  <circle cx="190" cy="150" r="94" fill="none" stroke="{self.PURPLE}" stroke-width="34"/>
  <circle cx="190" cy="150" r="94" fill="none" stroke="{self.BLUE}" stroke-width="34"
    pathLength="100" stroke-dasharray="{current:.4f} {100-current:.4f}"
    transform="rotate(-90 190 150)"/>
  <text x="190" y="143" text-anchor="middle" class="svg-kicker">TOTAL ASSETS</text>
  <text x="190" y="171" text-anchor="middle" class="svg-value">{currency} {total}</text>
  {self._legend_row(390, 115, self.BLUE, "Current assets", current_label)}
  {self._legend_row(390, 185, self.PURPLE, "Non-current assets", non_current_label)}
</svg>"""

    def _horizontal_bars(
        self,
        metrics: tuple[AssetMetric, ...],
        title: str,
        percentage_basis: str,
    ) -> str:
        if not metrics:
            return self._empty_chart(title)

        row_height = 58
        height = max(230, 78 + len(metrics) * row_height)
        max_amount = max(metric.amount.amount for metric in metrics)
        rows: list[str] = []
        for index, metric in enumerate(metrics):
            y = 54 + index * row_height
            ratio = float(metric.amount.amount / max_amount) if max_amount else 0
            width = max(0.0, ratio * 420)
            percentage = (
                metric.percentage_of_total
                if percentage_basis == "total"
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

    def _empty_chart(self, title: str) -> str:
        return f'''<svg class="chart-svg" viewBox="0 0 800 220" role="img" aria-label="{escape(title)} has no categories">
  <title>{escape(title)}</title>
  <rect x="20" y="20" width="760" height="180" rx="16" fill="{self.TRACK}"/>
  <text x="400" y="118" text-anchor="middle" class="svg-label">No categories reported</text>
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
