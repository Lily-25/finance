"""Public application facade and dependency configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..business.analysis import FinancialAnalysisService
from ..data_access.json_repository import JSONFinancialStatementRepository
from ..output.charts import FinancialCharts
from ..output.reporting import ReportBuilder, ReportFileExporter
from .use_cases import GenerateFinancialReport


@dataclass(frozen=True)
class ApplicationConfig:
    default_output: Path = Path("build/financial-report.html")


class DependencyContainer:
    def generate_financial_report(self) -> GenerateFinancialReport:
        return GenerateFinancialReport(
            analysis_service=FinancialAnalysisService(),
            chart_generator=FinancialCharts(),
            report_builder=ReportBuilder(),
            exporter=ReportFileExporter(),
        )

    def generate_asset_report(self) -> GenerateFinancialReport:
        """Backward-compatible dependency factory."""

        return self.generate_financial_report()


class FinancialAnalysisApp:
    def __init__(
        self,
        config: ApplicationConfig | None = None,
        container: DependencyContainer | None = None,
    ) -> None:
        self.config = config or ApplicationConfig()
        self.container = container or DependencyContainer()

    def generate_financial_report(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        title: str | None = None,
    ) -> Path:
        repository = JSONFinancialStatementRepository(input_path)
        destination = output_path or self.config.default_output
        return self.container.generate_financial_report().execute(
            repository, destination, report_title=title
        )

    def generate_asset_report(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        title: str | None = None,
    ) -> Path:
        """Backward-compatible facade method."""

        return self.generate_financial_report(input_path, output_path, title)
