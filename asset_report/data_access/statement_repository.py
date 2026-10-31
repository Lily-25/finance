"""Schema catalog, normalization, and directory retrieval for three statements."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any, Mapping

from ..domain.statement_bundle import (
    NormalizedStatement,
    STATEMENT_TYPES,
    StatementQuery,
    ThreeStatementBundle,
    period_key,
)
from .json_repository import DataValidationError, JSONReader


class SchemaCatalog:
    """Resolve accounting profiles and statement types to local JSON Schemas."""

    def __init__(self, schema_root: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.schema_root = Path(schema_root or project_root / "schemas").resolve()
        self._catalog = JSONReader().read(self.schema_root / "catalog.json")

    @property
    def profiles(self) -> tuple[Mapping[str, Any], ...]:
        profiles = self._catalog.get("profiles")
        if not isinstance(profiles, list):
            raise DataValidationError("Schema catalog must contain a profiles array")
        return tuple(profile for profile in profiles if isinstance(profile, dict))

    def profile(self, profile_name: str) -> Mapping[str, Any]:
        for profile in self.profiles:
            if str(profile.get("profile", "")).casefold() == profile_name.casefold():
                return profile
        available = ", ".join(str(item.get("profile")) for item in self.profiles)
        raise DataValidationError(
            f"Unknown schema profile '{profile_name}'. Available profiles: {available}"
        )

    def schema_path(self, profile_name: str, statement_type: str) -> Path:
        if statement_type not in STATEMENT_TYPES:
            raise DataValidationError(f"Unsupported statement type: {statement_type}")
        schemas = self.profile(profile_name).get("schemas")
        if not isinstance(schemas, dict) or statement_type not in schemas:
            raise DataValidationError(
                f"Profile {profile_name} has no schema for {statement_type}"
            )
        path = (self.schema_root / str(schemas[statement_type])).resolve()
        if self.schema_root not in path.parents or not path.is_file():
            raise DataValidationError(f"Schema file is unavailable: {path}")
        return path

    def load_schema(self, profile_name: str, statement_type: str) -> dict[str, Any]:
        return JSONReader().read(self.schema_path(profile_name, statement_type))


class StatementNormalizer:
    """Validate a statement contract and add schema-specific canonical fields."""

    _FIELD_ALIASES = {
        "cash": ("cash_and_cash_equivalents",),
        "longterminvestments": ("long_term_equity_investments", "investments_in_associates_and_joint_ventures"),
        "equityinvestments": ("other_equity_instrument_investments", "equity_instruments_at_fvoci"),
        "shorttermdebt": ("short_term_borrowings", "short_term_borrowings_and_current_portion_of_long_term_debt"),
        "longtermdebt": ("long_term_borrowings", "long_term_debt"),
        "payrollpayable": ("employee_benefits_payable", "accrued_compensation"),
        "taxespayable": ("taxes_and_levies_payable", "income_taxes_payable"),
        "deferredrevenue": ("contract_liabilities", "deferred_revenue"),
        "sharecapital": ("share_capital", "common_stock"),
        "fixedassets": ("fixed_assets", "property_plant_and_equipment"),
        "costofsales": ("cost_of_revenue", "cost_of_goods_and_services"),
    }

    def __init__(self, catalog: SchemaCatalog | None = None) -> None:
        self.catalog = catalog or SchemaCatalog()
        self._document_cache: dict[Path, dict[str, Any]] = {}

    def normalize(
        self,
        data: Mapping[str, Any],
        profile_name: str,
        statement_type: str,
    ) -> dict[str, Any]:
        schema_path = self.catalog.schema_path(profile_name, statement_type)
        schema = self._load_document(schema_path)
        normalized = deepcopy(dict(data))

        metadata = normalized.get("schema")
        if not isinstance(metadata, dict):
            raise DataValidationError("'schema' must be an object")
        actual_profile = metadata.get("profile")
        actual_type = metadata.get("statement_type")
        if actual_profile != profile_name:
            raise DataValidationError(
                f"Statement profile is {actual_profile!r}; expected {profile_name!r}"
            )
        if actual_type != statement_type:
            raise DataValidationError(
                f"Statement type is {actual_type!r}; expected {statement_type!r}"
            )

        self._normalize_node(normalized, schema, schema, schema_path, "statement")
        self._validate_node(normalized, schema, schema, schema_path, "statement")
        return normalized

    def _load_document(self, path: Path) -> dict[str, Any]:
        resolved = path.resolve()
        if resolved not in self._document_cache:
            self._document_cache[resolved] = JSONReader().read(resolved)
        return self._document_cache[resolved]

    def _resolve_ref(
        self,
        reference: str,
        document: dict[str, Any],
        document_path: Path,
    ) -> tuple[dict[str, Any], dict[str, Any], Path]:
        file_part, _, fragment = reference.partition("#")
        target_path = (document_path.parent / file_part).resolve() if file_part else document_path
        target_document = self._load_document(target_path) if file_part else document
        node: Any = target_document
        if fragment:
            for part in fragment.lstrip("/").split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(node, dict) or part not in node:
                    raise DataValidationError(f"Invalid schema reference: {reference}")
                node = node[part]
        if not isinstance(node, dict):
            raise DataValidationError(f"Schema reference is not an object: {reference}")
        return node, target_document, target_path

    def _canonical_fields(
        self,
        schema: Mapping[str, Any],
        document: dict[str, Any],
        document_path: Path,
    ) -> set[str]:
        found: set[str] = set()
        reference = schema.get("$ref")
        if isinstance(reference, str):
            node, ref_document, ref_path = self._resolve_ref(
                reference, document, document_path
            )
            found.update(self._canonical_fields(node, ref_document, ref_path))
        for component in schema.get("allOf", []):
            if isinstance(component, dict):
                found.update(
                    self._canonical_fields(component, document, document_path)
                )
        properties = schema.get("properties")
        if isinstance(properties, dict):
            canonical = properties.get("canonical_field")
            if isinstance(canonical, dict) and isinstance(canonical.get("enum"), list):
                found.update(str(value) for value in canonical["enum"])
        return found

    @staticmethod
    def _token(value: object) -> str:
        return "".join(character for character in str(value).casefold() if character.isalnum())

    def _infer_canonical(self, item: Mapping[str, Any], allowed: set[str]) -> str:
        existing = item.get("canonical_field")
        candidates = (
            existing if existing != "other" else None,
            item.get("name"),
            item.get("source_field"),
            existing,
        )
        by_token = {self._token(field): field for field in allowed}
        for candidate in candidates:
            token = self._token(candidate)
            if token in by_token:
                return by_token[token]
            for alias in self._FIELD_ALIASES.get(token, ()):
                if alias in allowed:
                    return alias
        return "other" if "other" in allowed else str(item.get("canonical_field") or "other")

    def _normalize_node(
        self,
        data: Any,
        schema: Mapping[str, Any],
        document: dict[str, Any],
        document_path: Path,
        location: str,
    ) -> None:
        reference = schema.get("$ref")
        if isinstance(reference, str):
            node, ref_document, ref_path = self._resolve_ref(
                reference, document, document_path
            )
            self._normalize_node(data, node, ref_document, ref_path, location)
        for component in schema.get("allOf", []):
            if isinstance(component, dict):
                self._normalize_node(data, component, document, document_path, location)

        if isinstance(data, dict):
            if all(key in data for key in ("name", "amount", "source_field", "description")):
                allowed = self._canonical_fields(schema, document, document_path)
                if allowed:
                    data["canonical_field"] = self._infer_canonical(data, allowed)
                elif not data.get("canonical_field"):
                    data["canonical_field"] = "other"

            properties = schema.get("properties")
            if isinstance(properties, dict):
                for name, child_schema in properties.items():
                    if name in data and isinstance(child_schema, dict):
                        self._normalize_node(
                            data[name],
                            child_schema,
                            document,
                            document_path,
                            f"{location}.{name}",
                        )
        elif isinstance(data, list):
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(data):
                    self._normalize_node(
                        item,
                        item_schema,
                        document,
                        document_path,
                        f"{location}[{index}]",
                    )

    def _validate_node(
        self,
        data: Any,
        schema: Mapping[str, Any],
        document: dict[str, Any],
        document_path: Path,
        location: str,
    ) -> None:
        reference = schema.get("$ref")
        if isinstance(reference, str):
            node, ref_document, ref_path = self._resolve_ref(
                reference, document, document_path
            )
            self._validate_node(data, node, ref_document, ref_path, location)
        for component in schema.get("allOf", []):
            if isinstance(component, dict):
                self._validate_node(data, component, document, document_path, location)

        if "const" in schema and data != schema["const"]:
            raise DataValidationError(
                f"'{location}' must equal {schema['const']!r}; received {data!r}"
            )
        enum = schema.get("enum")
        if isinstance(enum, list) and data not in enum:
            raise DataValidationError(
                f"'{location}' must be one of {', '.join(map(str, enum))}"
            )

        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(data, dict):
            raise DataValidationError(f"'{location}' must be an object")
        if expected_type == "array" and not isinstance(data, list):
            raise DataValidationError(f"'{location}' must be an array")
        if expected_type == "string" and (not isinstance(data, str) or not data.strip()):
            raise DataValidationError(f"'{location}' must be a non-empty string")
        if expected_type == "number" and (
            isinstance(data, bool) or not isinstance(data, (int, float))
        ):
            raise DataValidationError(f"'{location}' must be a number")

        if isinstance(data, dict):
            required = schema.get("required")
            if isinstance(required, list):
                missing = [str(name) for name in required if name not in data]
                if missing:
                    raise DataValidationError(
                        f"'{location}' is missing required field(s): {', '.join(missing)}"
                    )
            properties = schema.get("properties")
            if isinstance(properties, dict):
                for name, child_schema in properties.items():
                    if name in data and isinstance(child_schema, dict):
                        self._validate_node(
                            data[name],
                            child_schema,
                            document,
                            document_path,
                            f"{location}.{name}",
                        )
            if "amount" in data:
                self._validate_amount(data["amount"], f"{location}.amount")
        elif isinstance(data, list):
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(data):
                    self._validate_node(
                        item,
                        item_schema,
                        document,
                        document_path,
                        f"{location}[{index}]",
                    )

    @staticmethod
    def _validate_amount(value: Any, location: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise DataValidationError(f"'{location}' must be a number or decimal string")
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise DataValidationError(f"'{location}' is not a valid decimal amount") from exc
        if not amount.is_finite():
            raise DataValidationError(f"'{location}' must be finite")


class JSONStatementDirectoryRepository:
    """Retrieve statement files from a directory using a company/time-frame query."""

    def __init__(
        self,
        source_directory: str | Path,
        catalog: SchemaCatalog | None = None,
        normalizer: StatementNormalizer | None = None,
    ) -> None:
        self.source_directory = Path(source_directory).expanduser().resolve()
        self.catalog = catalog or SchemaCatalog()
        self.normalizer = normalizer or StatementNormalizer(self.catalog)
        self.reader = JSONReader()

    def retrieve(self, query: StatementQuery) -> ThreeStatementBundle:
        if not self.source_directory.is_dir():
            raise DataValidationError(
                f"Statement source directory not found: {self.source_directory}"
            )

        matched: list[NormalizedStatement] = []
        read_errors: list[str] = []
        for path in sorted(self.source_directory.rglob("*.json")):
            try:
                payload = self.reader.read(path)
            except DataValidationError as exc:
                read_errors.append(f"{path.name}: {exc}")
                continue
            if not self._matches(payload, query):
                continue
            metadata = payload.get("schema")
            if not isinstance(metadata, dict):
                continue
            statement_type = metadata.get("statement_type")
            if statement_type not in STATEMENT_TYPES:
                continue
            normalized = self.normalizer.normalize(
                payload, query.schema_profile, str(statement_type)
            )
            matched.append(
                NormalizedStatement(
                    statement_type=str(statement_type),
                    reporting_period=str(payload["reporting_period"]).strip(),
                    schema_profile=query.schema_profile,
                    data=normalized,
                    source_path=path,
                )
            )

        if not matched:
            suffix = f" Ignored unreadable files: {'; '.join(read_errors)}" if read_errors else ""
            raise DataValidationError(
                "No statements matched company, time frame, and schema profile."
                + suffix
            )

        periods = {statement.reporting_period for statement in matched}
        expected_periods = self._periods_in_range(query)
        missing_periods = [period for period in expected_periods if period not in periods]
        if missing_periods:
            raise DataValidationError(
                "The requested time frame is incomplete; no statement files for: "
                + ", ".join(missing_periods)
            )
        try:
            return ThreeStatementBundle(query=query, statements=tuple(matched))
        except ValueError as exc:
            raise DataValidationError(str(exc)) from exc

    def find_balance_sheet_paths(self, query: StatementQuery) -> tuple[Path, ...]:
        """Return validated source balance sheets without requiring the other statements."""

        if not self.source_directory.is_dir():
            raise DataValidationError(
                f"Statement source directory not found: {self.source_directory}"
            )
        matches: dict[str, Path] = {}
        for path in sorted(self.source_directory.rglob("*.json")):
            try:
                payload = self.reader.read(path)
            except DataValidationError:
                continue
            if not self._matches(payload, query):
                continue
            metadata = payload.get("schema")
            if not isinstance(metadata, dict) or metadata.get("statement_type") != "balance_sheet":
                continue
            self.normalizer.normalize(payload, query.schema_profile, "balance_sheet")
            period = str(payload["reporting_period"]).strip()
            if period in matches:
                raise DataValidationError(f"Duplicate balance sheet for {period}")
            matches[period] = path

        expected = self._periods_in_range(query)
        missing = [period for period in expected if period not in matches]
        if missing:
            raise DataValidationError(
                "No matching balance sheet for: " + ", ".join(missing)
            )
        return tuple(matches[period] for period in expected)

    @staticmethod
    def _matches(payload: Mapping[str, Any], query: StatementQuery) -> bool:
        company = payload.get("company")
        period = payload.get("reporting_period")
        metadata = payload.get("schema")
        return (
            isinstance(company, str)
            and company.strip().casefold() == query.company.casefold()
            and isinstance(period, str)
            and query.includes(period.strip())
            and isinstance(metadata, dict)
            and str(metadata.get("profile", "")).casefold()
            == query.schema_profile.casefold()
        )

    @staticmethod
    def _periods_in_range(query: StatementQuery) -> tuple[str, ...]:
        start = period_key(query.start_period)
        end = period_key(query.end_period)
        if start is None or end is None:
            return ()
        start_is_quarter = "Q" in query.start_period.upper()
        end_is_quarter = "Q" in query.end_period.upper()
        if not start_is_quarter and not end_is_quarter:
            return tuple(str(year) for year in range(start[0], end[0] + 1))
        if not start_is_quarter and end_is_quarter:
            annual_periods = tuple(str(year) for year in range(start[0], end[0]))
            return annual_periods + (query.end_period,)
        if start_is_quarter and not end_is_quarter:
            annual_periods = tuple(str(year) for year in range(start[0] + 1, end[0] + 1))
            return (query.start_period,) + annual_periods

        periods: list[str] = []
        year, quarter = start
        while (year, quarter) <= end:
            periods.append(f"{year}Q{quarter}")
            quarter += 1
            if quarter == 5:
                year += 1
                quarter = 1
        return tuple(periods)
