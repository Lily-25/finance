"""Cross-statement financial ratios and time-frame trend analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

from ..domain.statement_bundle import ThreeStatementBundle


@dataclass(frozen=True)
class FinancialRatioPeriod:
    """Calculated ratios for one reporting period."""

    period: str
    days_in_period: int | None
    annualized_flows: bool
    current_ratio: Decimal | None
    quick_ratio: Decimal | None
    debt_ratio: Decimal | None
    debt_to_equity_ratio: Decimal | None
    interest_coverage_ratio: Decimal | None
    inventory_turnover: Decimal | None
    days_sales_in_inventory: Decimal | None
    receivables_turnover: Decimal | None
    days_sales_in_receivables: Decimal | None
    total_asset_turnover: Decimal | None
    fixed_asset_turnover: Decimal | None
    research_and_development_intensity: Decimal | None
    profit_margin: Decimal | None
    gross_profit_margin: Decimal | None
    return_on_assets: Decimal | None
    return_on_equity: Decimal | None
    earnings_per_share: Decimal | None
    price_earnings_ratio: Decimal | None


@dataclass(frozen=True)
class FinancialRatioAnalysisResult:
    """Ratio observations for a complete three-statement time frame."""

    company: str
    ticker: str | None
    currency: str
    schema_profile: str
    periods: tuple[FinancialRatioPeriod, ...]

    @property
    def first(self) -> FinancialRatioPeriod:
        return self.periods[0]

    @property
    def latest(self) -> FinancialRatioPeriod:
        return self.periods[-1]

    @property
    def time_frame(self) -> str:
        if len(self.periods) == 1:
            return self.first.period
        return f"{self.first.period} to {self.latest.period}"


@dataclass(frozen=True)
class _BalanceInputs:
    current_assets: Decimal
    current_liabilities: Decimal
    total_assets: Decimal
    total_equity: Decimal
    inventory: Decimal
    accounts_receivable: Decimal
    fixed_assets: Decimal


class FinancialRatioAnalysisService:
    """Calculate comparable ratios from normalized three-statement bundles."""

    SALES_FIELDS = (
        "total_operating_revenue",
        "net_sales_and_gross_revenues",
        "revenue",
        "operating_revenue",
    )
    COST_OF_SALES_FIELDS = (
        "cost_of_revenue",
        "cost_of_sales",
        "cost_of_tangible_goods_sold",
        "other_operating_costs_and_expenses",
    )
    RESEARCH_AND_DEVELOPMENT_FIELDS = (
        "research_and_development_expenses",
    )
    PROFIT_BEFORE_TAX_FIELDS = (
        "profit_before_tax",
        "profit_loss_before_tax",
        "income_loss_before_income_taxes",
    )
    INTEREST_EXPENSE_FIELDS = (
        "interest_expense",
        "interest_expense_and_debt_discount_amortisation",
        "finance_expenses",
    )
    NET_INCOME_FIELDS = (
        "net_profit",
        "profit_loss",
        "net_income_loss",
        "income_loss_from_continuing_operations",
    )
    DILUTED_EPS_FIELDS = (
        "diluted_earnings_per_share",
        "diluted_eps_net_income",
        "diluted_eps_continuing_operations",
    )
    INVENTORY_FIELDS = ("inventories", "inventory")
    RECEIVABLE_FIELDS = (
        "accounts_receivable",
        "accounts_receivable_trade",
        "trade_and_other_receivables",
    )
    FIXED_ASSET_FIELDS = (
        "property_plant_and_equipment_net",
        "property_plant_and_equipment",
        "fixed_assets",
    )

    def analyze(
        self,
        bundle: ThreeStatementBundle,
        market_prices: Mapping[str, Decimal | int | float | str] | None = None,
    ) -> FinancialRatioAnalysisResult:
        """Calculate all supported ratios, preserving unavailable values as ``None``."""

        prices = {
            period.casefold(): self._decimal(value)
            for period, value in (market_prices or {}).items()
        }
        balance_by_period: dict[str, _BalanceInputs] = {}
        calculated: list[FinancialRatioPeriod] = []

        for period in bundle.periods:
            statements = bundle.for_period(period)
            balance_data = statements["balance_sheet"].data
            income_data = statements["income_statement"].data
            balance = self._balance_inputs(balance_data)
            previous = balance_by_period.get(bundle.periods[len(calculated) - 1]) if calculated else None

            sales = self._line_amount(income_data, self.SALES_FIELDS)
            cost_of_sales = abs(
                self._line_amount(income_data, self.COST_OF_SALES_FIELDS)
            )
            research_and_development = abs(
                self._line_amount(
                    income_data,
                    self.RESEARCH_AND_DEVELOPMENT_FIELDS,
                    source_contains=("research and development", "r&d", "研发"),
                )
            )
            profit_before_tax = self._line_amount(
                income_data, self.PROFIT_BEFORE_TAX_FIELDS
            )
            interest_expense = abs(
                self._line_amount(income_data, self.INTEREST_EXPENSE_FIELDS)
            )
            net_income = self._line_amount(income_data, self.NET_INCOME_FIELDS)
            eps = self._line_amount(income_data, self.DILUTED_EPS_FIELDS)
            days_in_period = self._days_in_period(income_data)
            annualized = days_in_period is not None and days_in_period < 330
            annualization_factor = (
                Decimal("365") / Decimal(days_in_period)
                if annualized and days_in_period
                else Decimal("1")
            )

            current_ratio = self._ratio(
                balance.current_assets, balance.current_liabilities
            )
            quick_ratio = self._ratio(
                balance.current_assets - balance.inventory,
                balance.current_liabilities,
            )
            debt = balance.total_assets - balance.total_equity
            price = prices.get(period.casefold())

            average_inventory = self._average(
                previous.inventory if previous else None, balance.inventory
            )
            average_receivables = self._average(
                previous.accounts_receivable if previous else None,
                balance.accounts_receivable,
            )
            average_assets = self._average(
                previous.total_assets if previous else None, balance.total_assets
            )
            average_fixed_assets = self._average(
                previous.fixed_assets if previous else None, balance.fixed_assets
            )
            average_equity = self._average(
                previous.total_equity if previous else None, balance.total_equity
            )
            annualized_sales = sales * annualization_factor
            annualized_cost = cost_of_sales * annualization_factor
            annualized_income = net_income * annualization_factor
            inventory_turnover = self._ratio(annualized_cost, average_inventory)
            receivables_turnover = self._ratio(
                annualized_sales, average_receivables
            )

            calculated.append(
                FinancialRatioPeriod(
                    period=period,
                    days_in_period=days_in_period,
                    annualized_flows=annualized,
                    current_ratio=current_ratio,
                    quick_ratio=quick_ratio,
                    debt_ratio=self._ratio(debt, balance.total_assets),
                    debt_to_equity_ratio=self._ratio(debt, balance.total_equity),
                    interest_coverage_ratio=self._ratio(
                        profit_before_tax + interest_expense, interest_expense
                    ),
                    inventory_turnover=inventory_turnover,
                    days_sales_in_inventory=self._days_ratio(inventory_turnover),
                    receivables_turnover=receivables_turnover,
                    days_sales_in_receivables=self._days_ratio(
                        receivables_turnover
                    ),
                    total_asset_turnover=self._ratio(
                        annualized_sales, average_assets
                    ),
                    fixed_asset_turnover=self._ratio(
                        annualized_sales, average_fixed_assets
                    ),
                    research_and_development_intensity=self._ratio(
                        research_and_development, sales
                    ),
                    profit_margin=self._ratio(net_income, sales),
                    gross_profit_margin=self._ratio(
                        sales - cost_of_sales, sales
                    ),
                    return_on_assets=self._ratio(
                        annualized_income, average_assets
                    ),
                    return_on_equity=self._ratio(
                        annualized_income, average_equity
                    ),
                    earnings_per_share=eps if eps != 0 else None,
                    price_earnings_ratio=self._ratio(price, eps),
                )
            )
            balance_by_period[period] = balance

        first_statement = bundle.statements[0].data
        return FinancialRatioAnalysisResult(
            company=bundle.query.company,
            ticker=self._optional_text(first_statement.get("ticker")),
            currency=str(first_statement.get("currency", "")).upper(),
            schema_profile=bundle.query.schema_profile,
            periods=tuple(calculated),
        )

    def _balance_inputs(self, statement: Mapping[str, Any]) -> _BalanceInputs:
        assets = self._mapping(statement.get("assets"))
        liabilities = self._mapping(statement.get("liabilities"))
        equity = self._mapping(statement.get("equity"))
        current_assets = self._section_total(
            assets.get("current"), ("total current assets", "流动资产合计")
        )
        current_liabilities = self._section_total(
            liabilities.get("current"),
            ("total current liabilities", "流动负债合计"),
        )
        total_assets = self._amount_from_node(assets.get("reported_total"))
        total_equity = self._amount_from_node(equity.get("reported_total"))
        return _BalanceInputs(
            current_assets=current_assets,
            current_liabilities=current_liabilities,
            total_assets=total_assets,
            total_equity=total_equity,
            inventory=self._line_amount(statement, self.INVENTORY_FIELDS),
            accounts_receivable=self._line_amount(
                statement, self.RECEIVABLE_FIELDS
            ),
            fixed_assets=self._line_amount(
                statement,
                self.FIXED_ASSET_FIELDS,
                source_contains=(
                    "property and equipment, net",
                    "property, plant and equipment, net",
                    "fixed assets",
                    "固定资产",
                ),
            ),
        )

    def _section_total(
        self, node: object, total_labels: tuple[str, ...]
    ) -> Decimal:
        items = tuple(self._line_items(node))
        for item in items:
            text = f"{item.get('name', '')} {item.get('source_field', '')}".casefold()
            if item.get("is_subtotal") and any(
                label.casefold() in text for label in total_labels
            ):
                return self._amount_from_node(item)
        return sum(
            (
                self._signed_component_amount(item)
                for item in items
                if not item.get("is_subtotal", False)
            ),
            Decimal("0"),
        )

    def _line_amount(
        self,
        statement: Mapping[str, Any],
        canonical_fields: Iterable[str],
        source_contains: tuple[str, ...] = (),
    ) -> Decimal:
        items = tuple(self._line_items(statement))
        for field in canonical_fields:
            matches = [item for item in items if item.get("canonical_field") == field]
            if matches:
                non_zero = next(
                    (
                        self._amount_from_node(item)
                        for item in matches
                        if self._amount_from_node(item) != 0
                    ),
                    None,
                )
                if non_zero is not None:
                    return non_zero
        for token in source_contains:
            normalized = token.casefold()
            for item in items:
                text = f"{item.get('name', '')} {item.get('source_field', '')}".casefold()
                if normalized in text:
                    return self._amount_from_node(item)
        return Decimal("0")

    @classmethod
    def _line_items(cls, node: object) -> Iterable[Mapping[str, Any]]:
        if isinstance(node, Mapping):
            if "canonical_field" in node and "amount" in node:
                yield node
            for value in node.values():
                yield from cls._line_items(value)
        elif isinstance(node, list):
            for value in node:
                yield from cls._line_items(value)

    @staticmethod
    def _mapping(value: object) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @classmethod
    def _amount_from_node(cls, node: object) -> Decimal:
        if not isinstance(node, Mapping):
            return Decimal("0")
        return cls._decimal(node.get("amount", 0))

    @classmethod
    def _signed_component_amount(cls, item: Mapping[str, Any]) -> Decimal:
        amount = cls._amount_from_node(item)
        if item.get("is_deduction", False) and amount > 0:
            return -amount
        return amount

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if value is None:
            return Decimal("0")
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid decimal value: {value!r}") from exc
        if not amount.is_finite():
            raise ValueError(f"Decimal value must be finite: {value!r}")
        return amount

    @staticmethod
    def _optional_text(value: object) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    @staticmethod
    def _ratio(
        numerator: Decimal | None, denominator: Decimal | None
    ) -> Decimal | None:
        if numerator is None or denominator is None or denominator == 0:
            return None
        return numerator / denominator

    @staticmethod
    def _average(start: Decimal | None, end: Decimal) -> Decimal | None:
        if start is None:
            return None
        return (start + end) / Decimal("2")

    @staticmethod
    def _days_ratio(turnover: Decimal | None) -> Decimal | None:
        if turnover is None or turnover == 0:
            return None
        return Decimal("365") / turnover

    @staticmethod
    def _days_in_period(statement: Mapping[str, Any]) -> int | None:
        source = statement.get("source")
        if not isinstance(source, Mapping):
            return None
        start_value = source.get("period_start")
        end_value = source.get("period_end")
        if not isinstance(start_value, str) or not isinstance(end_value, str):
            return None
        try:
            return (date.fromisoformat(end_value) - date.fromisoformat(start_value)).days + 1
        except ValueError:
            return None
