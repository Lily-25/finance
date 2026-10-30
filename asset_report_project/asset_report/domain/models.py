"""Immutable financial domain objects used by the report application."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from typing import ClassVar, Iterable


def _normalize_name(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "_" for character in value)
    return "_".join(part for part in normalized.split("_") if part)


def _percentage(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return Decimal("0")
    return (part / whole) * Decimal("100")


@dataclass(frozen=True)
class Money:
    """A non-negative decimal monetary amount."""

    amount: Decimal

    def __post_init__(self) -> None:
        if not self.amount.is_finite():
            raise ValueError("Money amount must be finite")
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

    @classmethod
    def from_value(cls, value: object) -> "Money":
        if isinstance(value, Money):
            return value
        if isinstance(value, bool):
            raise ValueError("Boolean values are not valid monetary amounts")
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid monetary amount: {value!r}") from exc
        return cls(amount)

    @classmethod
    def zero(cls) -> "Money":
        return cls(Decimal("0"))

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount + other.amount)

    def __radd__(self, other: object) -> "Money":
        if other == 0:
            return self
        if isinstance(other, Money):
            return other + self
        return NotImplemented


@dataclass(frozen=True)
class ReportingPeriod:
    label: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, str):
            raise ValueError("Reporting period must be a string")
        label = self.label.strip()
        if not label:
            raise ValueError("Reporting period cannot be blank")
        object.__setattr__(self, "label", label)


@dataclass(frozen=True)
class Company:
    """Identity and reporting context for one company."""

    name: str
    currency: str
    reporting_period: ReportingPeriod
    ticker: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise ValueError("Company name must be a string")
        if not isinstance(self.currency, str):
            raise ValueError("Company currency must be a string")
        if not isinstance(self.reporting_period, ReportingPeriod):
            raise ValueError("Company reporting_period must be a ReportingPeriod")
        if self.ticker is not None and not isinstance(self.ticker, str):
            raise ValueError("Company ticker must be a string when provided")
        name = self.name.strip()
        currency = self.currency.strip().upper()
        ticker = self.ticker.strip().upper() if self.ticker and self.ticker.strip() else None
        if not name:
            raise ValueError("Company name cannot be blank")
        if not currency:
            raise ValueError("Company currency cannot be blank")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "ticker", ticker)


@dataclass(frozen=True)
class AssetItem:
    name: str
    amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise ValueError("Asset name must be a string")
        name = self.name.strip()
        if not name:
            raise ValueError("Asset name cannot be blank")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "amount", Money.from_value(self.amount))


@dataclass(frozen=True)
class AssetStatement:
    """Asset line items with zero-safe defaults and calculated composition."""

    CURRENT_FIELDS: ClassVar[tuple[str, ...]] = (
        "cash_and_cash_equivalents",
        "trading_financial_assets",
        "notes_receivable",
        "accounts_receivable",
        "receivables_financing",
        "prepayments",
        "other_receivables",
        "inventory",
        "non_current_assets_due_within_one_year",
        "other_current_assets",
    )
    NON_CURRENT_FIELDS: ClassVar[tuple[str, ...]] = (
        "long_term_investments",
        "debt_investments",
        "equity_investments",
        "fixed_assets",
        "construction_in_progress",
        "right_of_use_assets",
        "intangible_assets",
        "development_expenditure",
        "goodwill",
        "deferred_tax_assets",
        "other_non_current_assets",
    )
    DISPLAY_NAMES: ClassVar[dict[str, str]] = {
        "cash_and_cash_equivalents": "Cash and cash equivalents",
        "trading_financial_assets": "Trading financial assets",
        "notes_receivable": "Notes receivable",
        "accounts_receivable": "Accounts receivable",
        "receivables_financing": "Receivables financing",
        "prepayments": "Prepayments",
        "other_receivables": "Other receivables",
        "inventory": "Inventory",
        "non_current_assets_due_within_one_year": "Non-current assets due within one year",
        "other_current_assets": "Other current assets",
        "long_term_investments": "Long-term investments",
        "debt_investments": "Debt investments",
        "equity_investments": "Equity investments",
        "fixed_assets": "Fixed assets",
        "construction_in_progress": "Construction in progress",
        "right_of_use_assets": "Right-of-use assets",
        "intangible_assets": "Intangible assets",
        "development_expenditure": "Development expenditure",
        "goodwill": "Goodwill",
        "deferred_tax_assets": "Deferred tax assets",
        "other_non_current_assets": "Other non-current assets",
    }
    ALIASES: ClassVar[dict[str, str]] = {
        "cash": "cash_and_cash_equivalents",
        "cash_equivalents": "cash_and_cash_equivalents",
        "prepaid_expenses": "prepayments",
        "property_plant_and_equipment": "fixed_assets",
        "property_plant_equipment": "fixed_assets",
        "ppe": "fixed_assets",
    }

    cash_and_cash_equivalents: Money = field(default_factory=Money.zero)
    trading_financial_assets: Money = field(default_factory=Money.zero)
    notes_receivable: Money = field(default_factory=Money.zero)
    accounts_receivable: Money = field(default_factory=Money.zero)
    receivables_financing: Money = field(default_factory=Money.zero)
    prepayments: Money = field(default_factory=Money.zero)
    other_receivables: Money = field(default_factory=Money.zero)
    inventory: Money = field(default_factory=Money.zero)
    non_current_assets_due_within_one_year: Money = field(default_factory=Money.zero)
    other_current_assets: Money = field(default_factory=Money.zero)
    long_term_investments: Money = field(default_factory=Money.zero)
    debt_investments: Money = field(default_factory=Money.zero)
    equity_investments: Money = field(default_factory=Money.zero)
    fixed_assets: Money = field(default_factory=Money.zero)
    construction_in_progress: Money = field(default_factory=Money.zero)
    right_of_use_assets: Money = field(default_factory=Money.zero)
    intangible_assets: Money = field(default_factory=Money.zero)
    development_expenditure: Money = field(default_factory=Money.zero)
    goodwill: Money = field(default_factory=Money.zero)
    deferred_tax_assets: Money = field(default_factory=Money.zero)
    other_non_current_assets: Money = field(default_factory=Money.zero)
    additional_current_assets: tuple[AssetItem, ...] = ()
    additional_non_current_assets: tuple[AssetItem, ...] = ()

    def __post_init__(self) -> None:
        for field_name in self.CURRENT_FIELDS + self.NON_CURRENT_FIELDS:
            object.__setattr__(self, field_name, Money.from_value(getattr(self, field_name)))
        object.__setattr__(self, "additional_current_assets", tuple(self.additional_current_assets))
        object.__setattr__(
            self, "additional_non_current_assets", tuple(self.additional_non_current_assets)
        )

    @classmethod
    def create(
        cls,
        current_assets: Iterable[AssetItem] = (),
        non_current_assets: Iterable[AssetItem] = (),
    ) -> "AssetStatement":
        values = {name: Money.zero() for name in cls.CURRENT_FIELDS + cls.NON_CURRENT_FIELDS}
        additional_current: list[AssetItem] = []
        additional_non_current: list[AssetItem] = []
        cls._collect_items(current_assets, cls.CURRENT_FIELDS, values, additional_current)
        cls._collect_items(
            non_current_assets, cls.NON_CURRENT_FIELDS, values, additional_non_current
        )
        return cls(
            **values,
            additional_current_assets=tuple(additional_current),
            additional_non_current_assets=tuple(additional_non_current),
        )

    @classmethod
    def _collect_items(
        cls,
        items: Iterable[AssetItem],
        allowed_fields: tuple[str, ...],
        values: dict[str, Money],
        additional: list[AssetItem],
    ) -> None:
        for item in items:
            field_name = cls._resolve_field(item.name, allowed_fields)
            if field_name is None:
                additional.append(item)
            else:
                values[field_name] = values[field_name] + item.amount

    @classmethod
    def _resolve_field(cls, name: str, allowed_fields: tuple[str, ...]) -> str | None:
        normalized = _normalize_name(name)
        display_aliases = {
            _normalize_name(label): field_name for field_name, label in cls.DISPLAY_NAMES.items()
        }
        field_name = cls.ALIASES.get(normalized, display_aliases.get(normalized, normalized))
        return field_name if field_name in allowed_fields else None

    def _standard_items(self, field_names: tuple[str, ...]) -> tuple[AssetItem, ...]:
        return tuple(
            AssetItem(self.DISPLAY_NAMES[name], getattr(self, name))
            for name in field_names
            if getattr(self, name).amount > 0
        )

    @property
    def current_assets(self) -> tuple[AssetItem, ...]:
        return self._standard_items(self.CURRENT_FIELDS) + self.additional_current_assets

    @property
    def non_current_assets(self) -> tuple[AssetItem, ...]:
        return self._standard_items(self.NON_CURRENT_FIELDS) + self.additional_non_current_assets

    @property
    def all_assets(self) -> tuple[AssetItem, ...]:
        return self.current_assets + self.non_current_assets

    @property
    def total_current_assets(self) -> Money:
        standard = (getattr(self, name) for name in self.CURRENT_FIELDS)
        return sum(standard, Money.zero()) + sum(
            (item.amount for item in self.additional_current_assets), Money.zero()
        )

    @property
    def total_non_current_assets(self) -> Money:
        standard = (getattr(self, name) for name in self.NON_CURRENT_FIELDS)
        return sum(standard, Money.zero()) + sum(
            (item.amount for item in self.additional_non_current_assets), Money.zero()
        )

    @property
    def total_assets(self) -> Money:
        return self.total_current_assets + self.total_non_current_assets

    @property
    def component_percentages(self) -> dict[str, Decimal]:
        total = self.total_assets.amount
        percentages = {
            name: _percentage(getattr(self, name).amount, total)
            for name in self.CURRENT_FIELDS + self.NON_CURRENT_FIELDS
        }
        for item in self.additional_current_assets + self.additional_non_current_assets:
            percentages[item.name] = _percentage(item.amount.amount, total)
        return percentages

    def percentage_of_total(self, component: str) -> Decimal:
        normalized = _normalize_name(component)
        resolved = self._resolve_field(component, self.CURRENT_FIELDS + self.NON_CURRENT_FIELDS)
        key = resolved or component
        if key in self.component_percentages:
            return self.component_percentages[key]
        for name, value in self.component_percentages.items():
            if _normalize_name(name) == normalized:
                return value
        raise KeyError(f"Unknown asset component: {component}")


@dataclass(frozen=True)
class LiabilityItem:
    name: str
    amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise ValueError("Liability name must be a string")
        name = self.name.strip()
        if not name:
            raise ValueError("Liability name cannot be blank")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "amount", Money.from_value(self.amount))


@dataclass(frozen=True)
class LiabilityStatement:
    """Liability line items with zero-safe defaults and composition calculations."""

    CURRENT_FIELDS: ClassVar[tuple[str, ...]] = (
        "accounts_payable",
        "short_term_debt",
        "notes_payable",
        "accrued_expenses",
        "taxes_payable",
        "deferred_revenue",
        "payroll_payable",
        "non_current_liabilities_due_within_one_year",
        "other_current_liabilities",
    )
    NON_CURRENT_FIELDS: ClassVar[tuple[str, ...]] = (
        "long_term_debt",
        "lease_liabilities",
        "deferred_tax_liabilities",
        "pension_liabilities",
        "provisions",
        "deferred_income",
        "other_non_current_liabilities",
    )
    DISPLAY_NAMES: ClassVar[dict[str, str]] = {
        "accounts_payable": "Accounts payable",
        "short_term_debt": "Short-term debt",
        "notes_payable": "Notes payable",
        "accrued_expenses": "Accrued expenses",
        "taxes_payable": "Taxes payable",
        "deferred_revenue": "Deferred revenue",
        "payroll_payable": "Payroll payable",
        "non_current_liabilities_due_within_one_year": "Non-current liabilities due within one year",
        "other_current_liabilities": "Other current liabilities",
        "long_term_debt": "Long-term debt",
        "lease_liabilities": "Lease liabilities",
        "deferred_tax_liabilities": "Deferred tax liabilities",
        "pension_liabilities": "Pension liabilities",
        "provisions": "Provisions",
        "deferred_income": "Deferred income",
        "other_non_current_liabilities": "Other non-current liabilities",
    }
    ALIASES: ClassVar[dict[str, str]] = {
        "current_portion_of_long_term_debt": "non_current_liabilities_due_within_one_year",
        "current_maturities_of_long_term_debt": "non_current_liabilities_due_within_one_year",
        "accounts_payable_and_accruals": "accounts_payable",
        "tax_payable": "taxes_payable",
    }

    accounts_payable: Money = field(default_factory=Money.zero)
    short_term_debt: Money = field(default_factory=Money.zero)
    notes_payable: Money = field(default_factory=Money.zero)
    accrued_expenses: Money = field(default_factory=Money.zero)
    taxes_payable: Money = field(default_factory=Money.zero)
    deferred_revenue: Money = field(default_factory=Money.zero)
    payroll_payable: Money = field(default_factory=Money.zero)
    non_current_liabilities_due_within_one_year: Money = field(default_factory=Money.zero)
    other_current_liabilities: Money = field(default_factory=Money.zero)
    long_term_debt: Money = field(default_factory=Money.zero)
    lease_liabilities: Money = field(default_factory=Money.zero)
    deferred_tax_liabilities: Money = field(default_factory=Money.zero)
    pension_liabilities: Money = field(default_factory=Money.zero)
    provisions: Money = field(default_factory=Money.zero)
    deferred_income: Money = field(default_factory=Money.zero)
    other_non_current_liabilities: Money = field(default_factory=Money.zero)
    additional_current_liabilities: tuple[LiabilityItem, ...] = ()
    additional_non_current_liabilities: tuple[LiabilityItem, ...] = ()

    def __post_init__(self) -> None:
        for field_name in self.CURRENT_FIELDS + self.NON_CURRENT_FIELDS:
            object.__setattr__(self, field_name, Money.from_value(getattr(self, field_name)))
        object.__setattr__(
            self, "additional_current_liabilities", tuple(self.additional_current_liabilities)
        )
        object.__setattr__(
            self,
            "additional_non_current_liabilities",
            tuple(self.additional_non_current_liabilities),
        )

    @classmethod
    def create(
        cls,
        current_liabilities: Iterable[LiabilityItem] = (),
        non_current_liabilities: Iterable[LiabilityItem] = (),
    ) -> "LiabilityStatement":
        values = {name: Money.zero() for name in cls.CURRENT_FIELDS + cls.NON_CURRENT_FIELDS}
        additional_current: list[LiabilityItem] = []
        additional_non_current: list[LiabilityItem] = []
        cls._collect_items(current_liabilities, cls.CURRENT_FIELDS, values, additional_current)
        cls._collect_items(
            non_current_liabilities,
            cls.NON_CURRENT_FIELDS,
            values,
            additional_non_current,
        )
        return cls(
            **values,
            additional_current_liabilities=tuple(additional_current),
            additional_non_current_liabilities=tuple(additional_non_current),
        )

    @classmethod
    def _collect_items(
        cls,
        items: Iterable[LiabilityItem],
        allowed_fields: tuple[str, ...],
        values: dict[str, Money],
        additional: list[LiabilityItem],
    ) -> None:
        display_aliases = {
            _normalize_name(label): field_name for field_name, label in cls.DISPLAY_NAMES.items()
        }
        for item in items:
            normalized = _normalize_name(item.name)
            field_name = cls.ALIASES.get(
                normalized, display_aliases.get(normalized, normalized)
            )
            if field_name in allowed_fields:
                values[field_name] = values[field_name] + item.amount
            else:
                additional.append(item)

    def _standard_items(self, field_names: tuple[str, ...]) -> tuple[LiabilityItem, ...]:
        return tuple(
            LiabilityItem(self.DISPLAY_NAMES[name], getattr(self, name))
            for name in field_names
            if getattr(self, name).amount > 0
        )

    @property
    def current_liabilities(self) -> tuple[LiabilityItem, ...]:
        return self._standard_items(self.CURRENT_FIELDS) + self.additional_current_liabilities

    @property
    def non_current_liabilities(self) -> tuple[LiabilityItem, ...]:
        return self._standard_items(self.NON_CURRENT_FIELDS) + self.additional_non_current_liabilities

    @property
    def all_liabilities(self) -> tuple[LiabilityItem, ...]:
        return self.current_liabilities + self.non_current_liabilities

    @property
    def total_current_liabilities(self) -> Money:
        standard = (getattr(self, name) for name in self.CURRENT_FIELDS)
        return sum(standard, Money.zero()) + sum(
            (item.amount for item in self.additional_current_liabilities), Money.zero()
        )

    @property
    def total_non_current_liabilities(self) -> Money:
        standard = (getattr(self, name) for name in self.NON_CURRENT_FIELDS)
        return sum(standard, Money.zero()) + sum(
            (item.amount for item in self.additional_non_current_liabilities), Money.zero()
        )

    @property
    def total_liabilities(self) -> Money:
        return self.total_current_liabilities + self.total_non_current_liabilities

    @property
    def component_percentages(self) -> dict[str, Decimal]:
        total = self.total_liabilities.amount
        percentages = {
            name: _percentage(getattr(self, name).amount, total)
            for name in self.CURRENT_FIELDS + self.NON_CURRENT_FIELDS
        }
        for item in self.additional_current_liabilities + self.additional_non_current_liabilities:
            percentages[item.name] = _percentage(item.amount.amount, total)
        return percentages

    def percentage_of_total(self, component: str) -> Decimal:
        normalized = _normalize_name(component)
        if normalized in self.component_percentages:
            return self.component_percentages[normalized]
        for name, value in self.component_percentages.items():
            if _normalize_name(name) == normalized:
                return value
        raise KeyError(f"Unknown liability component: {component}")


@dataclass(frozen=True)
class FinancialStatementData:
    """Complete statement of financial position used by the reporting pipeline."""

    company: Company
    assets: AssetStatement
    liabilities: LiabilityStatement = field(default_factory=LiabilityStatement)

    @property
    def statement(self) -> AssetStatement:
        """Backward-compatible asset statement accessor."""

        return self.assets

    @property
    def asset_statement(self) -> AssetStatement:
        return self.assets

    @property
    def liability_statement(self) -> LiabilityStatement:
        return self.liabilities

    @property
    def currency(self) -> str:
        return self.company.currency

    @property
    def reporting_period(self) -> ReportingPeriod:
        return self.company.reporting_period


@dataclass(frozen=True)
class FinancialTimeSeriesData:
    """Chronologically ordered financial statements for one company."""

    company: Company
    statements: tuple[FinancialStatementData, ...]

    def __post_init__(self) -> None:
        statements = tuple(self.statements)
        if len(statements) < 2:
            raise ValueError("A time frame requires at least two financial periods")

        labels = [statement.reporting_period.label for statement in statements]
        normalized_labels = [label.casefold() for label in labels]
        if len(set(normalized_labels)) != len(normalized_labels):
            raise ValueError("Financial period labels must be unique")

        keys = [self._period_key(label) for label in labels]
        if all(key is not None for key in keys):
            comparable_keys = [key for key in keys if key is not None]
            if comparable_keys != sorted(comparable_keys) or len(set(comparable_keys)) != len(
                comparable_keys
            ):
                raise ValueError("Financial periods must be in chronological order")

        for statement in statements:
            if statement.company.name != self.company.name:
                raise ValueError("All periods must belong to the same company")
            if statement.company.currency != self.company.currency:
                raise ValueError("All periods must use the same currency")
            if statement.company.ticker != self.company.ticker:
                raise ValueError("All periods must use the same ticker")
        object.__setattr__(self, "statements", statements)

    @staticmethod
    def _period_key(label: str) -> tuple[int, int] | None:
        match = re.fullmatch(r"(\d{4})(?:\s*Q([1-4]))?", label.strip(), re.IGNORECASE)
        if not match:
            return None
        year = int(match.group(1))
        quarter = int(match.group(2)) if match.group(2) else 4
        return year, quarter

    @property
    def start_period(self) -> ReportingPeriod:
        return self.statements[0].reporting_period

    @property
    def end_period(self) -> ReportingPeriod:
        return self.statements[-1].reporting_period

    @property
    def time_frame(self) -> str:
        return f"{self.start_period.label} to {self.end_period.label}"

    @property
    def currency(self) -> str:
        return self.company.currency


class AssetReportData(FinancialStatementData):
    """Backward-compatible constructor for the former asset-only aggregate."""

    def __init__(
        self,
        company: Company,
        statement: AssetStatement,
        liabilities: LiabilityStatement | None = None,
    ) -> None:
        super().__init__(company, statement, liabilities or LiabilityStatement())
