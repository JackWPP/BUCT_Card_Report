"""Tests for the screenshot endpoint (no-Playwright paths only).

The happy path requires a real Chromium instance, so it's verified manually
via the running app. Here we cover the failure paths and the rendered HTML
contract that the screenshot relies on.
"""
import json
from pathlib import Path

import pytest

from app import app
from reporter.renderer import render_report
from analyzer.stats import AnalysisResult, analyze
from fetcher.models import Transaction
from datetime import datetime


@pytest.fixture
def client():
    return app.test_client()


def test_screenshot_returns_400_when_no_report(client, tmp_path, monkeypatch):
    """If output_report.html doesn't exist, the endpoint must return JSON 400,
    not a 404 HTML page (so the frontend fetch+blob flow can parse the error)."""
    monkeypatch.chdir(tmp_path)
    r = client.get("/api/report/screenshot")
    assert r.status_code == 400
    data = r.get_json()
    assert "error" in data


def test_screenshot_returns_500_json_on_playwright_error(client, monkeypatch):
    """If Playwright fails (e.g. chromium not installed), the endpoint must
    return a JSON error rather than an HTML stack trace page."""
    from pathlib import Path
    Path("output_report.html").write_text("<html></html>", encoding="utf-8")
    try:
        # Force a failure inside the screenshot handler
        import app as app_mod
        real_import = app_mod.__builtins__["__import__"]
        def bad_import(name, *a, **kw):
            if name == "playwright.sync_api":
                raise RuntimeError("simulated chromium missing")
            return real_import(name, *a, **kw)
        monkeypatch.setitem(app_mod.__builtins__, "__import__", bad_import)

        r = client.get("/api/report/screenshot")
        assert r.status_code == 500
        data = r.get_json()
        assert "error" in data
    finally:
        Path("output_report.html").unlink(missing_ok=True)


def test_report_html_sets_rendered_flag():
    """The screenshot endpoint waits on window.__reportRendered — make sure
    the flag is actually set at the end of the report's <script> block."""
    a = AnalysisResult()
    a.monthly = [{"month": "2025-09", "expense": -10.0, "recharge": 0, "count": 1}]
    html = render_report(a, [], None)
    assert "window.__reportRendered = true" in html
