"""Application use cases coordinating domain, analysis, and output layers."""

from __future__ import annotations

from pathlib import Path

from ..business.analysis import AssetAnalysisService
from ..domain.repositories import FinancialStatementRepository
from ..output.charts import ChartGenerator
from ..output.reporting import ReportBuilder, ReportFileExporter


class GenerateAssetReport:
    def __init__(
        self,
        analysis_service: AssetAnalysisService,
        chart_generator: ChartGenerator,
        report_builder: ReportBuilder,
        exporter: ReportFileExporter,
    ) -> None:
        self.analysis_service = analysis_service
        self.chart_generator = chart_generator
        self.report_builder = report_builder
        self.exporter = exporter

    def execute(
        self,
        repository: FinancialStatementRepository,
        destination: str | Path,
        report_title: str | None = None,
    ) -> Path:
        data = repository.load()
        result = self.analysis_service.analyze(data)
        charts = self.chart_generator.generate(result)
        if len(charts) != 4:
            raise RuntimeError("Asset reports require exactly four charts")
        html = self.report_builder.build(result, charts, report_title)
        return self.exporter.export(html, destination)
