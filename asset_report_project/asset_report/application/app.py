"""Public application facade and dependency configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..business.analysis import AssetAnalysisService
from ..data_access.json_repository import JSONFinancialStatementRepository
from ..output.charts import AssetCharts
from ..output.reporting import ReportBuilder, ReportFileExporter
from .use_cases import GenerateAssetReport


@dataclass(frozen=True)
class ApplicationConfig:
    default_output: Path = Path("build/asset-report.html")


class DependencyContainer:
    def generate_asset_report(self) -> GenerateAssetReport:
        return GenerateAssetReport(
            analysis_service=AssetAnalysisService(),
            chart_generator=AssetCharts(),
            report_builder=ReportBuilder(),
            exporter=ReportFileExporter(),
        )


class FinancialAnalysisApp:
    def __init__(
        self,
        config: ApplicationConfig | None = None,
        container: DependencyContainer | None = None,
    ) -> None:
        self.config = config or ApplicationConfig()
        self.container = container or DependencyContainer()

    def generate_asset_report(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        title: str | None = None,
    ) -> Path:
        repository = JSONFinancialStatementRepository(input_path)
        destination = output_path or self.config.default_output
        return self.container.generate_asset_report().execute(
            repository, destination, report_title=title
        )
