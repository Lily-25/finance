"""Domain objects for schema-normalized three-statement time frames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping


STATEMENT_TYPES = (
    "balance_sheet",
    "income_statement",
    "cash_flow_statement",
)


def period_key(label: str) -> tuple[int, int] | None:
    """Return a sortable key for annual and quarterly period labels."""

    match = re.fullmatch(r"\s*(\d{4})(?:[- ]?Q([1-4]))?\s*", label, re.IGNORECASE)
    if not match:
        return None
    year = int(match.group(1))
    quarter = int(match.group(2) or 4)
    return year, quarter


@dataclass(frozen=True)
class StatementQuery:
    company: str
    start_period: str
    end_period: str
    schema_profile: str

    def __post_init__(self) -> None:
        for field_name in (
            "company",
            "start_period",
            "end_period",
            "schema_profile",
        ):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name.replace('_', ' ').title()} is required")
            object.__setattr__(self, field_name, value)
        start = period_key(self.start_period)
        end = period_key(self.end_period)
        if start is None or end is None:
            raise ValueError("Time-frame periods must use YYYY or YYYYQ1-YYYYQ4")
        if start > end:
            raise ValueError("Start period must not be later than end period")

    def includes(self, period: str) -> bool:
        key = period_key(period)
        if key is None:
            return False
        start = period_key(self.start_period)
        end = period_key(self.end_period)
        return start is not None and end is not None and start <= key <= end


@dataclass(frozen=True)
class NormalizedStatement:
    statement_type: str
    reporting_period: str
    schema_profile: str
    data: Mapping[str, Any]
    source_path: Path

    def __post_init__(self) -> None:
        if self.statement_type not in STATEMENT_TYPES:
            raise ValueError(f"Unsupported statement type: {self.statement_type}")


@dataclass(frozen=True)
class ThreeStatementBundle:
    query: StatementQuery
    statements: tuple[NormalizedStatement, ...]

    def __post_init__(self) -> None:
        if not self.statements:
            raise ValueError("A three-statement bundle cannot be empty")

        seen: set[tuple[str, str]] = set()
        by_period: dict[str, set[str]] = {}
        for statement in self.statements:
            key = (statement.reporting_period.casefold(), statement.statement_type)
            if key in seen:
                raise ValueError(
                    "Duplicate statement for "
                    f"{statement.reporting_period}: {statement.statement_type}"
                )
            seen.add(key)
            by_period.setdefault(statement.reporting_period, set()).add(
                statement.statement_type
            )

        expected = set(STATEMENT_TYPES)
        incomplete = {
            period: sorted(expected - available)
            for period, available in by_period.items()
            if available != expected
        }
        if incomplete:
            details = "; ".join(
                f"{period} missing {', '.join(missing)}"
                for period, missing in sorted(incomplete.items())
            )
            raise ValueError(f"Every period requires all three statements: {details}")

    @property
    def periods(self) -> tuple[str, ...]:
        labels = {statement.reporting_period for statement in self.statements}
        return tuple(sorted(labels, key=lambda label: period_key(label) or (0, 0)))

    def for_period(self, period: str) -> Mapping[str, NormalizedStatement]:
        return {
            statement.statement_type: statement
            for statement in self.statements
            if statement.reporting_period.casefold() == period.casefold()
        }
