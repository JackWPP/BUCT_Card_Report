// static/js/main.js

(function () {
    "use strict";

    // --- DOM Elements ---
    const urlInput = document.getElementById("url-input");
    const urlError = document.getElementById("url-error");
    const startDate = document.getElementById("start-date");
    const endDate = document.getElementById("end-date");
    const btnFetch = document.getElementById("btn-fetch");

    const stepInput = document.getElementById("step-input");
    const stepProgress = document.getElementById("step-progress");
    const stepOptions = document.getElementById("step-options");
    const stepReport = document.getElementById("step-report");

    const progressBar = document.getElementById("progress-bar");
    const progressMsg = document.getElementById("progress-msg");
    const progressCount = document.getElementById("progress-count");

    const fetchSummary = document.getElementById("fetch-summary");
    const optLlm = document.getElementById("opt-llm");
    const btnReport = document.getElementById("btn-report");

    const reportIframe = document.getElementById("report-iframe");
    const btnNewTab = document.getElementById("btn-new-tab");

    let pollTimer = null;

    // --- Initialize default dates ---
    function initDates() {
        const today = new Date();
        const endStr = formatDate(today);

        const start = new Date(today);
        start.setMonth(start.getMonth() - 10);
        const startStr = formatDate(start);

        startDate.value = startStr;
        endDate.value = endStr;
    }

    function formatDate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${day}`;
    }

    // --- Fetch (Step 1 -> Step 2) ---
    function startFetch() {
        const url = urlInput.value.trim();
        if (!url) {
            showError("请输入校园卡链接");
            return;
        }

        hideError();
        btnFetch.disabled = true;
        btnFetch.textContent = "处理中...";

        const payload = {
            url: url,
            start_date: startDate.value || null,
            end_date: endDate.value || null,
        };

        fetch("/api/fetch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((res) => {
                if (!res.ok) {
                    return res.json().then((data) => {
                        throw new Error(data.error || "请求失败");
                    });
                }
                return res.json();
            })
            .then(() => {
                showProgress();
                startPolling();
            })
            .catch((err) => {
                showError(err.message);
                btnFetch.disabled = false;
                btnFetch.textContent = "开始分析";
            });
    }

    // --- Polling ---
    function startPolling() {
        progressBar.classList.add("indeterminate");
        pollTimer = setInterval(pollStatus, 1000);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function pollStatus() {
        fetch("/api/status")
            .then((res) => res.json())
            .then((data) => {
                progressMsg.textContent = data.message || "";

                if (data.count > 0) {
                    progressCount.textContent = `已获取 ${data.count} 条记录`;
                }

                if (data.status === "done") {
                    stopPolling();
                    progressBar.classList.remove("indeterminate");
                    progressBar.style.width = "100%";
                    setTimeout(() => showOptions(data), 500);
                } else if (data.status === "error") {
                    stopPolling();
                    progressBar.classList.remove("indeterminate");
                    progressBar.style.width = "0%";
                    progressBar.style.background = "var(--error)";
                    progressMsg.textContent = data.message || "获取失败";
                    setTimeout(() => {
                        showInput();
                        showError(data.message || "获取失败");
                        btnFetch.disabled = false;
                        btnFetch.textContent = "开始分析";
                    }, 2000);
                }
            })
            .catch(() => {
                // Network error, keep polling
            });
    }

    // --- Show/Hide sections ---
    function showInput() {
        stepInput.classList.remove("hidden");
        stepProgress.classList.add("hidden");
        stepOptions.classList.add("hidden");
        stepReport.classList.add("hidden");
    }

    function showProgress() {
        stepInput.classList.add("hidden");
        stepProgress.classList.remove("hidden");
        stepOptions.classList.add("hidden");
        stepReport.classList.add("hidden");
        progressBar.style.width = "0%";
        progressBar.style.background = "var(--primary)";
        progressCount.textContent = "";
    }

    function showOptions(data) {
        stepProgress.classList.add("hidden");
        stepOptions.classList.remove("hidden");
        stepReport.classList.add("hidden");

        fetchSummary.textContent = data.message || "数据获取完成";
        btnReport.disabled = false;
        btnReport.textContent = "生成报告";
    }

    function showReport() {
        stepReport.classList.remove("hidden");
    }

    // --- Generate Report ---
    function generateReport() {
        btnReport.disabled = true;
        btnReport.textContent = "生成中...";

        const useLlm = optLlm ? optLlm.checked : false;

        fetch("/api/report", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ use_llm: useLlm }),
        })
            .then((res) => {
                if (!res.ok) {
                    return res.json().then((data) => {
                        throw new Error(data.error || "报告生成失败");
                    });
                }
                return res.json();
            })
            .then((data) => {
                displayReport(data.html);
                showReport();
                btnReport.textContent = "生成报告";
                btnReport.disabled = false;

                // Scroll to report
                document.getElementById("step-report").scrollIntoView({
                    behavior: "smooth",
                });
            })
            .catch((err) => {
                btnReport.disabled = false;
                btnReport.textContent = "生成报告";
                alert("报告生成失败: " + err.message);
            });
    }

    function displayReport(html) {
        const iframe = reportIframe;
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.open();
        doc.write(html);
        doc.close();

        // Auto-resize iframe based on content
        iframe.onload = function () {
            try {
                const h = iframe.contentDocument.body.scrollHeight;
                if (h > 200) {
                    iframe.style.height = Math.min(h + 40, 1200) + "px";
                }
            } catch (e) {
                // cross-origin, ignore
            }
        };
    }

    // --- Open report in new tab ---
    function openInNewTab() {
        const iframe = reportIframe;
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        const html = doc.documentElement.outerHTML;
        const w = window.open("", "_blank");
        if (w) {
            w.document.open();
            w.document.write(html);
            w.document.close();
        }
    }

    // --- Error display ---
    function showError(msg) {
        urlError.textContent = msg;
        urlError.classList.remove("hidden");
    }

    function hideError() {
        urlError.classList.add("hidden");
    }

    // --- Event listeners ---
    btnFetch.addEventListener("click", startFetch);
    btnReport.addEventListener("click", generateReport);
    btnNewTab.addEventListener("click", openInNewTab);

    // Allow Ctrl+Enter in textarea to submit
    urlInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            startFetch();
        }
    });

    // --- Init ---
    initDates();
})();
