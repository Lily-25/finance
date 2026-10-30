"""Pure business rules for assets, liabilities, liquidity, and leverage."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from ..domain.models import (
    AssetItem,
    FinancialStatementData,
    FinancialTimeSeriesData,
    LiabilityItem,
    Money,
)


class MetricsCalculator:
    @staticmethod
    def percentage(part: Money, whole: Money) -> Decimal:
        if whole.amount == 0:
            return Decimal("0")
        return (part.amount / whole.amount) * Decimal("100")

    @staticmethod
    def ratio(numerator: Money, denominator: Money) -> Decimal | None:
        if denominator.amount == 0:
            return None
        return numerator.amount / denominator.amount

    @staticmethod
    def change_percentage(start: Decimal, end: Decimal) -> Decimal | None:
        if start == 0:
            return None
        return ((end - start) / abs(start)) * Decimal("100")


@dataclass(frozen=True)
class FinancialMetric:
    name: str
    statement_type: str
    classification: str
    amount: Money
    percentage_of_class: Decimal
    percentage_of_statement: Decimal
    percentage_of_assets: Decimal

    @property
    def percentage_of_total(self) -> Decimal:
        """Backward-compatible name for asset metrics."""

        return self.percentage_of_statement


AssetMetric = FinancialMetric
LiabilityMetric = FinancialMetric


@dataclass(frozen=True)
class FinancialAnalysisResult:
    data: FinancialStatementData
    current_total: Money
    non_current_total: Money
    total_assets: Money
    current_percentage: Decimal
    non_current_percentage: Decimal
    current_metrics: tuple[FinancialMetric, ...]
    non_current_metrics: tuple[FinancialMetric, ...]
    current_liabilities_total: Money
    non_current_liabilities_total: Money
    total_liabilities: Money
    current_liabilities_percentage: Decimal
    non_current_liabilities_percentage: Decimal
    current_liability_metrics: tuple[FinancialMetric, ...]
    non_current_liability_metrics: tuple[FinancialMetric, ...]
    liability_to_assets_percentage: Decimal
    net_assets: Decimal
    current_ratio: Decimal | None

    @property
    def all_metrics(self) -> tuple[FinancialMetric, ...]:
        """Backward-compatible accessor for all asset metrics."""

        return self.all_asset_metrics

    @property
    def all_asset_metrics(self) -> tuple[FinancialMetric, ...]:
        return self._rank(self.current_metrics + self.non_current_metrics)

    @property
    def all_liability_metrics(self) -> tuple[FinancialMetric, ...]:
        return self._rank(
            self.current_liability_metrics + self.non_current_liability_metrics
        )

    @staticmethod
    def _rank(
        metrics: tuple[FinancialMetric, ...]
    ) -> tuple[FinancialMetric, ...]:
        return tuple(
            sorted(metrics, key=lambda metric: metric.amount.amount, reverse=True)
        )


AssetAnalysisResult = FinancialAnalysisResult


@dataclass(frozen=True)
class TimeFrameAnalysisResult:
    data: FinancialTimeSeriesData
    period_results: tuple[FinancialAnalysisResult, ...]

    @property
    def first(self) -> FinancialAnalysisResult:
        return self.period_results[0]

    @property
    def latest(self) -> FinancialAnalysisResult:
        return self.period_results[-1]

    @property
    def asset_change(self) -> Decimal:
        return self.latest.total_assets.amount - self.first.total_assets.amount

    @property
    def asset_change_percentage(self) -> Decimal | None:
        return MetricsCalculator.change_percentage(
            self.first.total_assets.amount, self.latest.total_assets.amount
        )

    @property
    def liability_change(self) -> Decimal:
        return self.latest.total_liabilities.amount - self.first.total_liabilities.amount

    @property
    def liability_change_percentage(self) -> Decimal | None:
        return MetricsCalculator.change_percentage(
            self.first.total_liabilities.amount,
            self.latest.total_liabilities.amount,
        )

    @property
    def net_asset_change(self) -> Decimal:
        return self.latest.net_assets - self.first.net_assets

    @property
    def net_asset_change_percentage(self) -> Decimal | None:
        return MetricsCalculator.change_percentage(
            self.first.net_assets, self.latest.net_assets
        )

    @property
    def liability_ratio_change_points(self) -> Decimal:
        return (
            self.latest.liability_to_assets_percentage
            - self.first.liability_to_assets_percentage
        )


class FinancialAnalysisService:
    def __init__(self, calculator: MetricsCalculator | None = None) -> None:
        self.calculator = calculator or MetricsCalculator()

    def analyze(
        self, data: FinancialStatementData | FinancialTimeSeriesData
    ) -> FinancialAnalysisResult | TimeFrameAnalysisResult:
        if isinstance(data, FinancialTimeSeriesData):
            return TimeFrameAnalysisResult(
                data=data,
                period_results=tuple(
                    self._analyze_statement(statement)
                    for statement in data.statements
                ),
            )
        return self._analyze_statement(data)

    def _analyze_statement(
        self, data: FinancialStatementData
    ) -> FinancialAnalysisResult:
        current_total = data.assets.total_current_assets
        non_current_total = data.assets.total_non_current_assets
        total_assets = data.assets.total_assets
        if total_assets.amount == 0:
            raise ValueError("Total assets must be greater than zero")

        current_liabilities_total = data.liabilities.total_current_liabilities
        non_current_liabilities_total = data.liabilities.total_non_current_liabilities
        total_liabilities = data.liabilities.total_liabilities

        current_metrics = self._metrics(
            data.assets.current_assets,
            "Assets",
            "Current",
            current_total,
            total_assets,
            total_assets,
        )
        non_current_metrics = self._metrics(
            data.assets.non_current_assets,
            "Assets",
            "Non-current",
            non_current_total,
            total_assets,
            total_assets,
        )
        current_liability_metrics = self._metrics(
            data.liabilities.current_liabilities,
            "Liabilities",
            "Current",
            current_liabilities_total,
            total_liabilities,
            total_assets,
        )
        non_current_liability_metrics = self._metrics(
            data.liabilities.non_current_liabilities,
            "Liabilities",
            "Non-current",
            non_current_liabilities_total,
            total_liabilities,
            total_assets,
        )

        return FinancialAnalysisResult(
            data=data,
            current_total=current_total,
            non_current_total=non_current_total,
            total_assets=total_assets,
            current_percentage=self.calculator.percentage(current_total, total_assets),
            non_current_percentage=self.calculator.percentage(
                non_current_total, total_assets
            ),
            current_metrics=current_metrics,
            non_current_metrics=non_current_metrics,
            current_liabilities_total=current_liabilities_total,
            non_current_liabilities_total=non_current_liabilities_total,
            total_liabilities=total_liabilities,
            current_liabilities_percentage=self.calculator.percentage(
                current_liabilities_total, total_liabilities
            ),
            non_current_liabilities_percentage=self.calculator.percentage(
                non_current_liabilities_total, total_liabilities
            ),
            current_liability_metrics=current_liability_metrics,
            non_current_liability_metrics=non_current_liability_metrics,
            liability_to_assets_percentage=self.calculator.percentage(
                total_liabilities, total_assets
            ),
            net_assets=total_assets.amount - total_liabilities.amount,
            current_ratio=self.calculator.ratio(
                current_total, current_liabilities_total
            ),
        )

    def _metrics(
        self,
        items: Iterable[AssetItem | LiabilityItem],
        statement_type: str,
        classification: str,
        class_total: Money,
        statement_total: Money,
        total_assets: Money,
    ) -> tuple[FinancialMetric, ...]:
        metrics = (
            FinancialMetric(
                name=item.name,
                statement_type=statement_type,
                classification=classification,
                amount=item.amount,
                percentage_of_class=self.calculator.percentage(
                    item.amount, class_total
                ),
                percentage_of_statement=self.calculator.percentage(
                    item.amount, statement_total
                ),
                percentage_of_assets=self.calculator.percentage(
                    item.amount, total_assets
                ),
            )
            for item in items
        )
        return tuple(
            sorted(metrics, key=lambda metric: metric.amount.amount, reverse=True)
        )


class AssetAnalysisService(FinancialAnalysisService):
    """Backward-compatible service name."""
