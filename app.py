# app.py
import json
import logging
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from config import Config
from fetcher.url_parser import parse_card_url
from fetcher.browser import fetch_transactions
from analyzer.stats import analyze
from reporter.renderer import render_report
from llm.insights import generate_insight

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
config = Config()

# In-memory state (single-user local app)
_state = {
    "status": "idle",       # idle | fetching | done | error
    "message": "",
    "count": 0,
    "transactions": None,
    "analysis": None,
}


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html", llm_available=config.llm_enabled)


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    """Start fetching transactions in a background thread."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    url = data.get("url", "").strip()
    start_date = data.get("start_date") or "2025-09-01"
    end_date = data.get("end_date") or None

    if not url:
        return jsonify({"error": "请输入校园卡链接"}), 400

    try:
        openid = parse_card_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if _state["status"] == "fetching":
        return jsonify({"error": "正在获取数据中，请等待完成"}), 409

    _state["status"] = "fetching"
    _state["message"] = "正在启动浏览器..."
    _state["count"] = 0
    _state["transactions"] = None
    _state["analysis"] = None

    def _run():
        try:
            def on_progress(msg, count):
                _state["message"] = msg
                _state["count"] = count

            txs = fetch_transactions(openid, start_date, end_date, on_progress)
            _state["transactions"] = txs
            _state["analysis"] = analyze(txs)
            _state["status"] = "done"
            _state["message"] = f"成功获取 {len(txs)} 条记录"
        except Exception as e:
            logger.exception("Fetch failed")
            _state["status"] = "error"
            _state["message"] = f"获取失败: {e}"

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/status")
def api_status():
    """Return current fetch progress."""
    return jsonify({
        "status": _state["status"],
        "message": _state["message"],
        "count": _state["count"],
    })


@app.route("/api/report", methods=["POST"])
def api_report():
    """Generate and return the HTML report."""
    if _state["status"] != "done" or not _state["analysis"]:
        return jsonify({"error": "没有可用的数据，请先获取数据"}), 400

    data = request.get_json() or {}
    use_llm = data.get("use_llm", False)

    llm_insight = None
    if use_llm and config.llm_enabled:
        _state["message"] = "正在生成 AI 分析..."
        llm_insight = generate_insight(_state["analysis"], config)

    html = render_report(_state["analysis"], _state["transactions"], llm_insight)

    output_path = Path("output_report.html")
    output_path.write_text(html, encoding="utf-8")

    return jsonify({"html": html})


@app.route("/api/report/download")
def api_download():
    """Download the generated report as an HTML file."""
    path = Path("output_report.html")
    if not path.exists():
        return "暂无可下载的报告", 404
    return send_file(
        path,
        mimetype="text/html",
        as_attachment=True,
        download_name="BUCT_校园卡消费报告.html",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
