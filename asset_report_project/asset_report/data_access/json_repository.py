"""Read, validate, standardize, and map JSON asset data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from ..domain.models import (
    AssetItem,
    AssetStatement,
    Company,
    FinancialStatementData,
    FinancialTimeSeriesData,
    LiabilityItem,
    LiabilityStatement,
    Money,
    ReportingPeriod,
)


class DataValidationError(ValueError):
    """Raised when input data does not follow the documented schema."""


class JSONReader:
    def read(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as source:
                data = json.load(source)
        except FileNotFoundError as exc:
            raise DataValidationError(f"Input file not found: {path}") from exc
        except OSError as exc:
            raise DataValidationError(f"Could not read input file: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise DataValidationError(
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        if not isinstance(data, dict):
            raise DataValidationError("The JSON root must be an object")
        return data


class DataStandardizer:
    """Trim textual fields while preserving monetary values for exact parsing."""

    def standardize(self, data: dict[str, Any]) -> dict[str, Any]:
        standardized = dict(data)
        for key in ("company", "ticker", "reporting_period", "currency"):
            value = standardized.get(key)
            if isinstance(value, str):
                standardized[key] = value.strip()
        self._standardize_financial_sections(standardized)

        time_frame = standardized.get("time_frame")
        if isinstance(time_frame, dict):
            time_frame = dict(time_frame)
            for key in ("start", "end"):
                if isinstance(time_frame.get(key), str):
                    time_frame[key] = time_frame[key].strip()
            standardized["time_frame"] = time_frame

        periods = standardized.get("periods")
        if isinstance(periods, list):
            standardized_periods: list[object] = []
            for period in periods:
                if not isinstance(period, dict):
                    standardized_periods.append(period)
                    continue
                standardized_period = dict(period)
                if isinstance(standardized_period.get("reporting_period"), str):
                    standardized_period["reporting_period"] = standardized_period[
                        "reporting_period"
                    ].strip()
                self._standardize_financial_sections(standardized_period)
                standardized_periods.append(standardized_period)
            standardized["periods"] = standardized_periods
        return standardized

    def _standardize_financial_sections(self, data: dict[str, Any]) -> None:
        for statement_name in ("assets", "liabilities"):
            statement = data.get(statement_name)
            if not isinstance(statement, dict):
                continue
            standardized_statement = dict(statement)
            for section in ("current", "non_current"):
                items = standardized_statement.get(section)
                if isinstance(items, list):
                    standardized_statement[section] = [
                        self._standardize_item(item) for item in items
                    ]
            data[statement_name] = standardized_statement

    @staticmethod
    def _standardize_item(item: object) -> object:
        if not isinstance(item, dict):
            return item
        result = dict(item)
        if isinstance(result.get("name"), str):
            result["name"] = result["name"].strip()
        return result


class FinancialDataValidator:
    REQUIRED_ROOT = ("company", "reporting_period", "currency", "assets")

    def validate(self, data: dict[str, Any]) -> None:
        if "periods" in data:
            self._validate_time_series(data)
            return

        missing = [key for key in self.REQUIRED_ROOT if key not in data]
        if missing:
            raise DataValidationError(f"Missing required field(s): {', '.join(missing)}")

        for key in ("company", "reporting_period", "currency"):
            if not isinstance(data[key], str) or not data[key]:
                raise DataValidationError(f"'{key}' must be a non-empty string")

        ticker = data.get("ticker")
        if ticker is not None and not isinstance(ticker, str):
            raise DataValidationError("'ticker' must be a string when provided")

        self._validate_statement(data["assets"], "assets", require_item=True)

        liabilities = data.get("liabilities")
        if liabilities is not None:
            self._validate_statement(liabilities, "liabilities", require_item=False)

    def _validate_time_series(self, data: dict[str, Any]) -> None:
        required = ("company", "currency", "periods")
        missing = [key for key in required if key not in data]
        if missing:
            raise DataValidationError(f"Missing required field(s): {', '.join(missing)}")

        for key in ("company", "currency"):
            if not isinstance(data[key], str) or not data[key]:
                raise DataValidationError(f"'{key}' must be a non-empty string")
        ticker = data.get("ticker")
        if ticker is not None and not isinstance(ticker, str):
            raise DataValidationError("'ticker' must be a string when provided")

        periods = data["periods"]
        if not isinstance(periods, list):
            raise DataValidationError("'periods' must be an array")
        if len(periods) < 2:
            raise DataValidationError("A time frame requires at least two financial periods")

        labels: list[str] = []
        for index, period in enumerate(periods):
            location = f"periods[{index}]"
            if not isinstance(period, dict):
                raise DataValidationError(f"'{location}' must be an object")
            label = period.get("reporting_period")
            if not isinstance(label, str) or not label:
                raise DataValidationError(
                    f"'{location}.reporting_period' must be a non-empty string"
                )
            labels.append(label)
            if "assets" not in period:
                raise DataValidationError(f"Missing required field: {location}.assets")
            self._validate_statement(
                period["assets"], f"{location}.assets", require_item=True
            )
            liabilities = period.get("liabilities")
            if liabilities is not None:
                self._validate_statement(
                    liabilities, f"{location}.liabilities", require_item=False
                )

        normalized_labels = [label.casefold() for label in labels]
        if len(set(normalized_labels)) != len(normalized_labels):
            raise DataValidationError("Financial period labels must be unique")
        period_keys = [FinancialTimeSeriesData._period_key(label) for label in labels]
        if all(key is not None for key in period_keys):
            comparable_keys = [key for key in period_keys if key is not None]
            if comparable_keys != sorted(comparable_keys) or len(
                set(comparable_keys)
            ) != len(comparable_keys):
                raise DataValidationError(
                    "Financial periods must be in chronological order"
                )

        time_frame = data.get("time_frame")
        if time_frame is not None:
            if not isinstance(time_frame, dict):
                raise DataValidationError("'time_frame' must be an object")
            for key in ("start", "end"):
                if not isinstance(time_frame.get(key), str) or not time_frame[key]:
                    raise DataValidationError(
                        f"'time_frame.{key}' must be a non-empty string"
                    )
            if time_frame["start"].casefold() != labels[0].casefold():
                raise DataValidationError(
                    "'time_frame.start' must match the first reporting period"
                )
            if time_frame["end"].casefold() != labels[-1].casefold():
                raise DataValidationError(
                    "'time_frame.end' must match the last reporting period"
                )

    def _validate_statement(
        self, statement: object, statement_name: str, require_item: bool
    ) -> None:
        if not isinstance(statement, dict):
            raise DataValidationError(f"'{statement_name}' must be an object")
        for section in ("current", "non_current"):
            if section not in statement:
                raise DataValidationError(
                    f"Missing required {statement_name} section: {statement_name}.{section}"
                )
            if not isinstance(statement[section], list):
                raise DataValidationError(f"'{statement_name}.{section}' must be an array")
            self._validate_items(statement[section], statement_name, section)

        if require_item and not statement["current"] and not statement["non_current"]:
            raise DataValidationError("At least one asset item is required")

    @staticmethod
    def _validate_items(
        items: list[object], statement_name: str, section: str
    ) -> None:
        seen_names: set[str] = set()
        for index, item in enumerate(items):
            location = f"{statement_name}.{section}[{index}]"
            if not isinstance(item, dict):
                raise DataValidationError(f"'{location}' must be an object")
            if not isinstance(item.get("name"), str) or not item["name"]:
                raise DataValidationError(f"'{location}.name' must be a non-empty string")
            normalized_name = item["name"].casefold()
            if normalized_name in seen_names:
                raise DataValidationError(
                    f"Duplicate item name in {statement_name}.{section}: {item['name']}"
                )
            seen_names.add(normalized_name)
            if "amount" not in item:
                raise DataValidationError(f"Missing required field: {location}.amount")
            try:
                Money.from_value(item["amount"])
            except ValueError as exc:
                raise DataValidationError(f"Invalid '{location}.amount': {exc}") from exc


class FinancialStatementMapper:
    def map(
        self, data: dict[str, Any]
    ) -> FinancialStatementData | FinancialTimeSeriesData:
        if "periods" in data:
            return self._map_time_series(data)
        return self._map_statement(data, data)

    def _map_time_series(self, data: dict[str, Any]) -> FinancialTimeSeriesData:
        periods = tuple(
            self._map_statement(data, period) for period in data["periods"]
        )
        start = periods[0].reporting_period.label
        end = periods[-1].reporting_period.label
        return FinancialTimeSeriesData(
            company=Company(
                name=data["company"],
                ticker=data.get("ticker"),
                currency=data["currency"],
                reporting_period=ReportingPeriod(f"{start} to {end}"),
            ),
            statements=periods,
        )

    def _map_statement(
        self, identity: dict[str, Any], statement: dict[str, Any]
    ) -> FinancialStatementData:
        assets = statement["assets"]
        liabilities = statement.get(
            "liabilities", {"current": [], "non_current": []}
        )
        current_assets = tuple(self._map_asset(item) for item in assets["current"])
        non_current_assets = tuple(
            self._map_asset(item) for item in assets["non_current"]
        )
        current_liabilities = tuple(
            self._map_liability(item) for item in liabilities["current"]
        )
        non_current_liabilities = tuple(
            self._map_liability(item) for item in liabilities["non_current"]
        )
        return FinancialStatementData(
            company=Company(
                name=identity["company"],
                ticker=identity.get("ticker"),
                currency=identity["currency"],
                reporting_period=ReportingPeriod(statement["reporting_period"]),
            ),
            assets=AssetStatement.create(current_assets, non_current_assets),
            liabilities=LiabilityStatement.create(
                current_liabilities, non_current_liabilities
            ),
        )

    @staticmethod
    def _map_asset(item: dict[str, Any]) -> AssetItem:
        return AssetItem(name=item["name"], amount=Money.from_value(item["amount"]))

    @staticmethod
    def _map_liability(item: dict[str, Any]) -> LiabilityItem:
        return LiabilityItem(name=item["name"], amount=Money.from_value(item["amount"]))


AssetStatementMapper = FinancialStatementMapper


class JSONFinancialStatementRepository:
    """Concrete repository for the project's JSON input format."""

    def __init__(self, path: str | Path | Sequence[str | Path]) -> None:
        if isinstance(path, (str, Path)):
            paths = (Path(path),)
        else:
            paths = tuple(Path(item) for item in path)
        if not paths:
            raise DataValidationError("At least one input file is required")

        self.paths = paths
        self.path = paths[0]
        self.reader = JSONReader()
        self.standardizer = DataStandardizer()
        self.validator = FinancialDataValidator()
        self.mapper = FinancialStatementMapper()

    def load(self) -> FinancialStatementData | FinancialTimeSeriesData:
        if len(self.paths) == 1:
            return self._load_path(self.paths[0])

        statements: list[FinancialStatementData] = []
        for path in self.paths:
            statement = self._load_path(path, allow_embedded_time_series=False)
            if not isinstance(statement, FinancialStatementData):
                raise DataValidationError(
                    f"{path}: each time-frame file must contain exactly one period"
                )
            statements.append(statement)

        period_keys = [
            FinancialTimeSeriesData._period_key(item.reporting_period.label)
            for item in statements
        ]
        if all(key is not None for key in period_keys):
            statements.sort(
                key=lambda item: FinancialTimeSeriesData._period_key(
                    item.reporting_period.label
                )
                or (0, 0)
            )

        first = statements[0]
        start = statements[0].reporting_period.label
        end = statements[-1].reporting_period.label
        try:
            return FinancialTimeSeriesData(
                company=Company(
                    name=first.company.name,
                    ticker=first.company.ticker,
                    currency=first.company.currency,
                    reporting_period=ReportingPeriod(f"{start} to {end}"),
                ),
                statements=tuple(statements),
            )
        except ValueError as exc:
            raise DataValidationError(f"Invalid time-frame files: {exc}") from exc

    def _load_path(
        self, path: Path, allow_embedded_time_series: bool = True
    ) -> FinancialStatementData | FinancialTimeSeriesData:
        try:
            data = self.standardizer.standardize(self.reader.read(path))
            if not allow_embedded_time_series and "periods" in data:
                raise DataValidationError(
                    "each time-frame file must contain exactly one period"
                )
            self.validator.validate(data)
            return self.mapper.map(data)
        except DataValidationError as exc:
            if str(exc).startswith(str(path)):
                raise
            raise DataValidationError(f"{path}: {exc}") from exc
