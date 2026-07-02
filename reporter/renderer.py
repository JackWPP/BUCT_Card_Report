# reporter/renderer.py
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from analyzer.stats import AnalysisResult
from fetcher.models import Transaction

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def render_report(
    analysis: AnalysisResult,
    transactions: list[Transaction],
    llm_insight: str | None = None,
) -> str:
    """Render an HTML report from analysis results.

    Args:
        analysis: Computed AnalysisResult.
        transactions: Raw transaction list (for future use).
        llm_insight: Optional LLM-generated text to include.

    Returns:
        Complete self-contained HTML string.
    """
    template = _env.get_template("report.html")

    date_start = analysis.date_range[0].strftime("%Y-%m-%d") if analysis.date_range else "N/A"
    date_end = analysis.date_range[1].strftime("%Y-%m-%d") if analysis.date_range else "N/A"

    return template.render(
        analysis=analysis,
        transactions=transactions,
        llm_insight=llm_insight,
        date_start=date_start,
        date_end=date_end,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
