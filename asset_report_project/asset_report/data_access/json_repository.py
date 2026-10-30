"""Read, validate, standardize, and map JSON asset data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.models import (
    AssetItem,
    AssetStatement,
    Company,
    FinancialStatementData,
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
        for statement_name in ("assets", "liabilities"):
            statement = standardized.get(statement_name)
            if not isinstance(statement, dict):
                continue
            statement = dict(statement)
            for section in ("current", "non_current"):
                items = statement.get(section)
                if isinstance(items, list):
                    statement[section] = [self._standardize_item(item) for item in items]
            standardized[statement_name] = statement
        return standardized

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
    def map(self, data: dict[str, Any]) -> FinancialStatementData:
        assets = data["assets"]
        liabilities = data.get("liabilities", {"current": [], "non_current": []})
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
                name=data["company"],
                ticker=data.get("ticker"),
                currency=data["currency"],
                reporting_period=ReportingPeriod(data["reporting_period"]),
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

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.reader = JSONReader()
        self.standardizer = DataStandardizer()
        self.validator = FinancialDataValidator()
        self.mapper = FinancialStatementMapper()

    def load(self) -> FinancialStatementData:
        data = self.standardizer.standardize(self.reader.read(self.path))
        self.validator.validate(data)
        return self.mapper.map(data)
