"""Application services for retrieving and exporting three statements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from ..data_access.statement_repository import JSONStatementDirectoryRepository
from ..domain.statement_bundle import StatementQuery, ThreeStatementBundle


@dataclass(frozen=True)
class StatementExportResult:
    bundle: ThreeStatementBundle
    output_directory: Path
    manifest_path: Path
    statement_paths: tuple[Path, ...]


class RetrieveAndNormalizeThreeStatements:
    """Retrieve a complete time frame and export schema-normalized JSON files."""

    def execute(
        self,
        source_directory: str | Path,
        output_directory: str | Path,
        query: StatementQuery,
    ) -> StatementExportResult:
        repository = JSONStatementDirectoryRepository(source_directory)
        bundle = repository.retrieve(query)
        destination = Path(output_directory).expanduser().resolve()
        normalized_directory = destination / "normalized"
        normalized_directory.mkdir(parents=True, exist_ok=True)

        company_slug = self._slug(query.company)
        exported: list[Path] = []
        statement_records: list[dict[str, Any]] = []
        for period in bundle.periods:
            for statement_type, statement in bundle.for_period(period).items():
                path = normalized_directory / (
                    f"{company_slug}_{self._slug(period)}_{statement_type}.json"
                )
                self._write_json(path, dict(statement.data))
                exported.append(path)
                statement_records.append(
                    {
                        "period": period,
                        "statement_type": statement_type,
                        "source_path": str(statement.source_path),
                        "normalized_path": str(path),
                    }
                )

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "company": query.company,
            "schema_profile": query.schema_profile,
            "time_frame": {
                "start": query.start_period,
                "end": query.end_period,
                "periods": list(bundle.periods),
            },
            "statement_count": len(exported),
            "statements": statement_records,
        }
        manifest_path = destination / "manifest.json"
        self._write_json(manifest_path, manifest)
        return StatementExportResult(
            bundle=bundle,
            output_directory=destination,
            manifest_path=manifest_path,
            statement_paths=tuple(exported),
        )

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
        return slug or "statement"

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
