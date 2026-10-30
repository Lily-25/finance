"""Read, validate, standardize, and map JSON asset data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.models import (
    AssetItem,
    AssetReportData,
    AssetStatement,
    Company,
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
        assets = standardized.get("assets")
        if isinstance(assets, dict):
            assets = dict(assets)
            for section in ("current", "non_current"):
                items = assets.get(section)
                if isinstance(items, list):
                    assets[section] = [self._standardize_item(item) for item in items]
            standardized["assets"] = assets
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

        assets = data["assets"]
        if not isinstance(assets, dict):
            raise DataValidationError("'assets' must be an object")
        for section in ("current", "non_current"):
            if section not in assets:
                raise DataValidationError(f"Missing required asset section: assets.{section}")
            if not isinstance(assets[section], list):
                raise DataValidationError(f"'assets.{section}' must be an array")
            self._validate_items(assets[section], section)

        if not assets["current"] and not assets["non_current"]:
            raise DataValidationError("At least one asset item is required")

    @staticmethod
    def _validate_items(items: list[object], section: str) -> None:
        seen_names: set[str] = set()
        for index, item in enumerate(items):
            location = f"assets.{section}[{index}]"
            if not isinstance(item, dict):
                raise DataValidationError(f"'{location}' must be an object")
            if not isinstance(item.get("name"), str) or not item["name"]:
                raise DataValidationError(f"'{location}.name' must be a non-empty string")
            normalized_name = item["name"].casefold()
            if normalized_name in seen_names:
                raise DataValidationError(
                    f"Duplicate asset name in assets.{section}: {item['name']}"
                )
            seen_names.add(normalized_name)
            if "amount" not in item:
                raise DataValidationError(f"Missing required field: {location}.amount")
            try:
                Money.from_value(item["amount"])
            except ValueError as exc:
                raise DataValidationError(f"Invalid '{location}.amount': {exc}") from exc


class AssetStatementMapper:
    def map(self, data: dict[str, Any]) -> AssetReportData:
        assets = data["assets"]
        current = tuple(self._map_item(item) for item in assets["current"])
        non_current = tuple(self._map_item(item) for item in assets["non_current"])
        return AssetReportData(
            company=Company(
                name=data["company"],
                ticker=data.get("ticker"),
                currency=data["currency"],
                reporting_period=ReportingPeriod(data["reporting_period"]),
            ),
            statement=AssetStatement.create(current, non_current),
        )

    @staticmethod
    def _map_item(item: dict[str, Any]) -> AssetItem:
        return AssetItem(name=item["name"], amount=Money.from_value(item["amount"]))


class JSONFinancialStatementRepository:
    """Concrete repository for the project's JSON input format."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.reader = JSONReader()
        self.standardizer = DataStandardizer()
        self.validator = FinancialDataValidator()
        self.mapper = AssetStatementMapper()

    def load(self) -> AssetReportData:
        data = self.standardizer.standardize(self.reader.read(self.path))
        self.validator.validate(data)
        return self.mapper.map(data)
