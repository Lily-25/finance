"""Pure business rules for asset totals, shares, and rankings."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..domain.models import AssetItem, AssetReportData, Money


class MetricsCalculator:
    @staticmethod
    def percentage(part: Money, whole: Money) -> Decimal:
        if whole.amount == 0:
            return Decimal("0")
        return (part.amount / whole.amount) * Decimal("100")


@dataclass(frozen=True)
class AssetMetric:
    name: str
    classification: str
    amount: Money
    percentage_of_class: Decimal
    percentage_of_total: Decimal


@dataclass(frozen=True)
class AssetAnalysisResult:
    data: AssetReportData
    current_total: Money
    non_current_total: Money
    total_assets: Money
    current_percentage: Decimal
    non_current_percentage: Decimal
    current_metrics: tuple[AssetMetric, ...]
    non_current_metrics: tuple[AssetMetric, ...]

    @property
    def all_metrics(self) -> tuple[AssetMetric, ...]:
        return tuple(
            sorted(
                self.current_metrics + self.non_current_metrics,
                key=lambda metric: metric.amount.amount,
                reverse=True,
            )
        )


class AssetAnalysisService:
    def __init__(self, calculator: MetricsCalculator | None = None) -> None:
        self.calculator = calculator or MetricsCalculator()

    def analyze(self, data: AssetReportData) -> AssetAnalysisResult:
        current_total = sum(
            (item.amount for item in data.statement.current_assets), Money.zero()
        )
        non_current_total = sum(
            (item.amount for item in data.statement.non_current_assets), Money.zero()
        )
        total_assets = current_total + non_current_total
        if total_assets.amount == 0:
            raise ValueError("Total assets must be greater than zero")

        current_metrics = self._metrics(
            data.statement.current_assets, "Current", current_total, total_assets
        )
        non_current_metrics = self._metrics(
            data.statement.non_current_assets,
            "Non-current",
            non_current_total,
            total_assets,
        )
        return AssetAnalysisResult(
            data=data,
            current_total=current_total,
            non_current_total=non_current_total,
            total_assets=total_assets,
            current_percentage=self.calculator.percentage(current_total, total_assets),
            non_current_percentage=self.calculator.percentage(non_current_total, total_assets),
            current_metrics=current_metrics,
            non_current_metrics=non_current_metrics,
        )

    def _metrics(
        self,
        items: tuple[AssetItem, ...],
        classification: str,
        class_total: Money,
        total_assets: Money,
    ) -> tuple[AssetMetric, ...]:
        metrics = (
            AssetMetric(
                name=item.name,
                classification=classification,
                amount=item.amount,
                percentage_of_class=self.calculator.percentage(item.amount, class_total),
                percentage_of_total=self.calculator.percentage(item.amount, total_assets),
            )
            for item in items
        )
        return tuple(sorted(metrics, key=lambda metric: metric.amount.amount, reverse=True))
