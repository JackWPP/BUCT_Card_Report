// static/js/main.js
// Client-side controller for the BUCT Campus Card Report web app.

(function () {
    "use strict";

    // =====================================================================
    // DOM
    // =====================================================================
    const $ = (id) => document.getElementById(id);

    const urlInput = $("url-input");
    const urlError = $("url-error");
    const startDate = $("start-date");
    const endDate = $("end-date");
    const btnFetch = $("btn-fetch");

    const stepInput = $("step-input");
    const stepProgress = $("step-progress");
    const stepOptions = $("step-options");
    const stepReport = $("step-report");

    const progressBar = $("progress-bar");
    const progressMsg = $("progress-msg");
    const progressCount = $("progress-count");
    const progressElapsed = $("progress-elapsed");

    const fetchSummary = $("fetch-summary");
    const optLlm = $("opt-llm");
    const optForceRefresh = $("opt-force-refresh");
    const llmStatusBadge = $("llm-status-badge");
    const btnReport = $("btn-report");

    const reportIframe = $("report-iframe");
    const btnNewTab = $("btn-new-tab");
    const btnRestart = $("btn-restart");
    const btnDownload = $("btn-download");
    const btnScreenshot = $("btn-screenshot");
    const btnExportCsv = $("btn-export-csv");
    const btnExportXlsx = $("btn-export-xlsx");

    // Advanced options (enroll date / CSV import / find first)
    const enrollDate = $("enroll-date");
    const btnFetchAll = $("btn-fetch-all");
    const csvFileInput = $("csv-file");
    const btnImportCsv = $("btn-import-csv");
    const btnFindFirst = $("btn-find-first");

    // Settings modal
    const settingsModal = $("settings-modal");
    const aboutModal = $("about-modal");
    const btnSettings = $("btn-settings");
    const btnTheme = $("btn-theme");
    const llmBaseUrlInput = $("llm-base-url");
    const llmModelInput = $("llm-model");
    const llmApiKeyInput = $("llm-api-key");
    const llmEnabledInput = $("llm-enabled");
    const currentKeyDisplay = $("current-key-display");
    const providerList = $("provider-list");
    const configPath = $("config-path");
    const llmTestResult = $("llm-test-result");

    // =====================================================================
    // State
    // =====================================================================
    let sseSource = null;
    let pollTimer = null;
    let activeProvider = null;

    // =====================================================================
    // Utilities
    // =====================================================================
    function formatDate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${day}`;
    }

    function initDates() {
        const today = new Date();
        endDate.value = formatDate(today);
        const start = new Date(today);
        start.setMonth(start.getMonth() - 12);
        startDate.value = formatDate(start);

        // Sensible default for "拉取在校全部": 4 years ago (typical undergrad
        // length). User can adjust.
        if (enrollDate && !enrollDate.value) {
            const e = new Date(today);
            e.setFullYear(e.getFullYear() - 4);
            enrollDate.value = formatDate(e);
        }
    }

    function debounce(fn, ms) {
        let t = null;
        return function (...args) {
            if (t) clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    function escapeHtml(s) {
        // For text insertions only — values are server-trusted.
        const div = document.createElement("div");
        div.textContent = String(s ?? "");
        return div.innerHTML;
    }

    // =====================================================================
    // Toast notifications (replaces alert())
    // =====================================================================
    function toast(msg, type = "info", duration = 3500) {
        const container = $("toast-container");
        const el = document.createElement("div");
        el.className = `toast toast-${type}`;
        el.textContent = msg;
        container.appendChild(el);
        // Trigger CSS animation
        requestAnimationFrame(() => el.classList.add("toast-show"));
        setTimeout(() => {
            el.classList.remove("toast-show");
            el.classList.add("toast-hide");
            setTimeout(() => el.remove(), 300);
        }, duration);
    }

    // =====================================================================
    // Theme toggle
    // =====================================================================
    const THEME_KEY = "buct-theme";
    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        btnTheme.textContent = theme === "dark" ? "☀️" : "🌗";
        try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
    }
    function initTheme() {
        let saved = "light";
        try { saved = localStorage.getItem(THEME_KEY) || "light"; } catch (e) {}
        // Respect OS preference on first visit.
        if (!localStorage.getItem(THEME_KEY) &&
            window.matchMedia("(prefers-color-scheme: dark)").matches) {
            saved = "dark";
        }
        applyTheme(saved);
    }
    btnTheme.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        applyTheme(cur === "dark" ? "light" : "dark");
    });

    // =====================================================================
    // Section switching
    // =====================================================================
    function showSection(name) {
        [stepInput, stepProgress, stepOptions, stepReport].forEach((el) =>
            el.classList.add("hidden")
        );
        ({
            input: stepInput,
            progress: stepProgress,
            options: stepOptions,
            report: stepReport,
        }[name]).classList.remove("hidden");
    }

    // =====================================================================
    // Fetch pipeline (Step 1 -> Step 2)
    // =====================================================================
    async function startFetch() {
        const url = urlInput.value.trim();
        if (!url) {
            showUrlError("请输入校园卡链接");
            return;
        }
        hideUrlError();

        setBtnLoading(btnFetch, true, "处理中...");
        try {
            const res = await fetch("/api/fetch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    url,
                    start_date: startDate.value || null,
                    end_date: endDate.value || null,
                    force_refresh: optForceRefresh.checked,
                }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "请求失败");
            showSection("progress");
            resetProgress();
            startSSE();
        } catch (err) {
            showUrlError(err.message);
            setBtnLoading(btnFetch, false, "开始分析");
        }
    }

    function resetProgress() {
        progressBar.classList.remove("indeterminate");
        progressBar.style.width = "0%";
        progressBar.style.background = "";
        progressMsg.textContent = "正在启动浏览器...";
        progressCount.textContent = "";
        progressElapsed.textContent = "";
    }

    // =====================================================================
    // Real-time progress via Server-Sent Events
    // =====================================================================
    function startSSE() {
        stopSSE();
        if (typeof EventSource === "undefined") {
            startPolling(); // graceful fallback for old browsers
            return;
        }
        sseSource = new EventSource("/api/status/stream");
        sseSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                handleStatus(data);
            } catch (err) {
                console.warn("Bad SSE payload", err);
            }
        };
        sseSource.onerror = () => {
            stopSSE();
            // SSE disconnected unexpectedly → fall back to polling once.
            startPolling();
        };
    }
    function stopSSE() {
        if (sseSource) {
            sseSource.close();
            sseSource = null;
        }
    }

    // Polling fallback (when SSE unsupported or stream interrupted)
    function startPolling() {
        stopPolling();
        pollTimer = setInterval(async () => {
            try {
                const res = await fetch("/api/status");
                const data = await res.json();
                handleStatus(data);
                if (data.status === "done" || data.status === "error") {
                    stopPolling();
                }
            } catch (e) {
                // network glitch, keep trying
            }
        }, 1000);
    }
    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function handleStatus(data) {
        progressMsg.textContent = data.message || "";
        if (data.total > 0) {
            progressBar.classList.remove("indeterminate");
            progressBar.style.width = (data.progress || 0) + "%";
            progressCount.textContent =
                `已处理 ${data.count}/${data.total} 批次`;
        } else {
            progressBar.classList.add("indeterminate");
        }
        if (data.elapsed) {
            progressElapsed.textContent = `已用时 ${data.elapsed}s`;
        }

        if (data.status === "done") {
            stopSSE();
            stopPolling();
            progressBar.style.width = "100%";
            setTimeout(() => {
                fetchSummary.textContent = data.message || "数据获取完成";
                toast(`✅ ${data.message}`, "success");
                showSection("options");
                refreshLlmBadge();
            }, 400);
        } else if (data.status === "error") {
            stopSSE();
            stopPolling();
            progressBar.style.background = "var(--error)";
            progressMsg.textContent = data.message || "获取失败";
            toast(`❌ ${data.message || "获取失败"}`, "error");
            setTimeout(() => {
                showSection("input");
                showUrlError(data.message || "获取失败");
                setBtnLoading(btnFetch, false, "开始分析");
            }, 1500);
        }
    }

    // =====================================================================
    // Generate Report (Step 3 -> Step 4)
    // =====================================================================
    async function generateReport() {
        setBtnLoading(btnReport, true, "生成中...");
        const useLlm = optLlm ? optLlm.checked : false;

        try {
            const res = await fetch("/api/report", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ use_llm: useLlm }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "报告生成失败");

            displayReport(data.html);
            if (data.llm_used) {
                toast("✨ AI 洞察已生成", "success");
            }
            showSection("report");
            // Update download href to bust cache
            btnDownload.href = `/api/report/download?t=${Date.now()}`;
            stepReport.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (err) {
            toast(`❌ ${err.message}`, "error");
        } finally {
            setBtnLoading(btnReport, false, "生成报告");
        }
    }

    function displayReport(html) {
        const iframe = reportIframe;
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.open();
        doc.write(html);
        doc.close();
        iframe.onload = function () {
            try {
                const h = iframe.contentDocument.body.scrollHeight;
                if (h > 200) {
                    iframe.style.height = Math.min(h + 60, 1600) + "px";
                }
            } catch (e) {
                // cross-origin, ignore
            }
        };
    }

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

    // Export the full report as a single long PNG (rendered server-side by
    // headless Chromium, so charts render perfectly).
    async function exportScreenshot() {
        setBtnLoading(btnScreenshot, true, "截图中...");
        try {
            const res = await fetch("/api/report/screenshot");
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.error || "截图失败");
            }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "BUCT_校园卡消费报告.png";
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            toast("✅ 长截图已导出", "success");
        } catch (err) {
            toast(`❌ ${err.message}`, "error");
        } finally {
            setBtnLoading(btnScreenshot, false, "📷 导出长截图");
        }
    }

    // Export the raw transactions as CSV or XLSX. The server returns the file
    // directly with Content-Disposition, so we just trigger a download.
    async function exportTransactions(format, btn) {
        const label = format === "xlsx" ? "导出 XLSX" : "导出 CSV";
        setBtnLoading(btn, true, "导出中...");
        try {
            const res = await fetch(`/api/transactions/export?format=${format}`);
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.error || "导出失败");
            }
            // Pull filename from Content-Disposition if present
            const dispo = res.headers.get("Content-Disposition") || "";
            const m = dispo.match(/filename="?([^";]+)"?/);
            const filename = m ? m[1] : `BUCT_校园卡明细.${format}`;

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            toast(`✅ ${label}已导出（${filename}）`, "success");
        } catch (err) {
            toast(`❌ ${err.message}`, "error");
        } finally {
            setBtnLoading(btn, false, format === "xlsx" ? "📊 导出 XLSX" : "📄 导出 CSV");
        }
    }

    function restartAnalysis() {
        showSection("input");
        setBtnLoading(btnFetch, false, "开始分析");
    }

    // --- "拉取在校全部" — fetch from enrollment date to today ---
    function startFetchAll() {
        if (!enrollDate.value) {
            toast("请先选择入学日期", "error");
            enrollDate.focus();
            return;
        }
        // Mirror the URL field into the standard fetch path with the new range.
        startDate.value = enrollDate.value;
        endDate.value = formatDate(new Date());
        startFetch();
    }

    // --- "🎯 一键找到最初记录" — recursive backward search ---
    async function startFindFirst() {
        const url = urlInput.value.trim();
        if (!url) {
            showUrlError("请输入校园卡链接");
            return;
        }
        hideUrlError();
        setBtnLoading(btnFindFirst, true, "递归查找中...");

        try {
            const res = await fetch("/api/fetch/first", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "请求失败");
            showSection("progress");
            resetProgress();
            // Hint that this may take a while
            progressMsg.textContent = "正在递归查找最早记录（首次约 2-3 分钟）...";
            startSSE();
        } catch (err) {
            showUrlError(err.message);
            setBtnLoading(btnFindFirst, false, "🎯 一键找到最初记录");
        }
    }

    // --- CSV import — bypass fetch, go straight to the options step ---
        const file = csvFileInput.files && csvFileInput.files[0];
        if (!file) {
            toast("请先选择 CSV 文件", "error");
            return;
        }
        setBtnLoading(btnImportCsv, true, "解析中...");
        try {
            const form = new FormData();
            form.append("file", file);
            const res = await fetch("/api/transactions/import", {
                method: "POST",
                body: form,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "导入失败");
            // Mirror the import into the same in-memory state the fetch path
            // would have populated, so the rest of the UI works unchanged.
            stopSSE();
            stopPolling();
            fetchSummary.textContent =
                `${data.message}（${data.date_start} ~ ${data.date_end}）`;
            toast(`✅ ${data.message}`, "success");
            if (data.skipped_rows) {
                toast(`⚠ ${data.skipped_rows} 行解析失败，已跳过`, "warning", 5000);
            }
            btnReport.disabled = false;
            btnReport.textContent = "生成报告";
            showSection("options");
            refreshLlmBadge();
        } catch (err) {
            toast(`❌ ${err.message}`, "error");
        } finally {
            setBtnLoading(btnImportCsv, false, "📤 解析并使用");
        }
    }

    // =====================================================================
    // LLM Settings Modal
    // =====================================================================
    function openSettings() {
        settingsModal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
        loadConfigIntoModal();
    }
    function closeSettings() {
        settingsModal.classList.add("hidden");
        document.body.style.overflow = "";
    }

    async function loadConfigIntoModal() {
        try {
            const res = await fetch("/api/llm/config");
            const data = await res.json();
            renderProviders(data.providers, data.llm);
            llmBaseUrlInput.value = data.llm.base_url || "";
            llmModelInput.value = data.llm.model || "";
            llmEnabledInput.checked = data.llm.enabled;
            currentKeyDisplay.textContent = data.llm.masked_key || "未设置";
            llmApiKeyInput.value = "";
            llmApiKeyInput.placeholder = data.llm.has_key
                ? "留空保持原 Key 不变"
                : "sk-...";
            configPath.textContent = data.config_file || "";
            llmTestResult.classList.add("hidden");
            llmTestResult.textContent = "";
        } catch (err) {
            toast("加载配置失败", "error");
        }
    }

    function renderProviders(providers, current) {
        providerList.innerHTML = "";
        // Find best-matching preset by base_url
        activeProvider = providers.find(
            (p) => p.base_url && p.base_url === current.base_url
        ) || providers.find((p) => p.name === "自定义");

        providers.forEach((p, idx) => {
            const div = document.createElement("div");
            div.className = "provider-chip";
            div.dataset.name = p.name;
            if (activeProvider && activeProvider.name === p.name) {
                div.classList.add("active");
            }
            div.innerHTML = `
                <div class="provider-name">${escapeHtml(p.name)}</div>
                <div class="provider-hint">${escapeHtml(p.hint || "")}</div>
            `;
            div.addEventListener("click", () => selectProvider(p));
            providerList.appendChild(div);
        });
    }

    function selectProvider(p) {
        activeProvider = p;
        providerList.querySelectorAll(".provider-chip").forEach((el) => {
            el.classList.toggle("active", el.dataset.name === p.name);
        });
        if (p.base_url) llmBaseUrlInput.value = p.base_url;
        if (p.model) llmModelInput.value = p.model;
    }

    async function saveLlmConfig() {
        const payload = {
            base_url: llmBaseUrlInput.value.trim(),
            model: llmModelInput.value.trim(),
            enabled: llmEnabledInput.checked,
        };
        const newKey = llmApiKeyInput.value.trim();
        if (newKey) payload.api_key = newKey;
        // Don't send empty api_key field (means "leave unchanged")

        try {
            const res = await fetch("/api/llm/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "保存失败");
            toast("✅ 配置已保存", "success");
            refreshLlmBadge();
            closeSettings();
        } catch (err) {
            toast(`❌ ${err.message}`, "error");
        }
    }

    async function clearApiKey() {
        if (!confirm("确定要清除已保存的 API Key 吗？")) return;
        try {
            const res = await fetch("/api/llm/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ api_key: "__CLEAR__" }),
            });
            await res.json();
            toast("API Key 已清除", "info");
            loadConfigIntoModal();
            refreshLlmBadge();
        } catch (err) {
            toast("清除失败", "error");
        }
    }

    async function testLlm() {
        const btn = $("btn-test-llm");
        setBtnLoading(btn, true, "测试中...");
        llmTestResult.classList.remove("hidden");
        llmTestResult.className = "test-result test-pending";
        llmTestResult.textContent = "正在连接...";

        const payload = {
            base_url: llmBaseUrlInput.value.trim(),
            model: llmModelInput.value.trim(),
        };
        const key = llmApiKeyInput.value.trim();
        if (key) payload.api_key = key;

        try {
            const res = await fetch("/api/llm/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            llmTestResult.className = data.ok
                ? "test-result test-success"
                : "test-result test-error";
            llmTestResult.textContent = data.message;
        } catch (err) {
            llmTestResult.className = "test-result test-error";
            llmTestResult.textContent = `请求失败: ${err.message}`;
        } finally {
            setBtnLoading(btn, false, "🔌 测试连接");
        }
    }

    function toggleKeyVisibility() {
        const inp = llmApiKeyInput;
        inp.type = inp.type === "password" ? "text" : "password";
    }

    function refreshLlmBadge() {
        const ready = window.APP_CONFIG &&
            window.APP_CONFIG.llm &&
            window.APP_CONFIG.llm.ready;
        if (ready) {
            llmStatusBadge.textContent = "已启用";
            llmStatusBadge.className = "badge badge-success";
            optLlm.disabled = false;
        } else if (window.APP_CONFIG?.llm?.has_key) {
            llmStatusBadge.textContent = "已配置但未启用";
            llmStatusBadge.className = "badge badge-warning";
            optLlm.disabled = true;
        } else {
            llmStatusBadge.textContent = "未配置";
            llmStatusBadge.className = "badge badge-muted";
            optLlm.disabled = true;
        }
    }

    // =====================================================================
    // Misc UI helpers
    // =====================================================================
    function setBtnLoading(btn, loading, label) {
        btn.disabled = loading;
        const span = btn.querySelector(".btn-text");
        if (span) span.textContent = label;
        else btn.textContent = label;
    }

    function showUrlError(msg) {
        urlError.textContent = msg;
        urlError.classList.remove("hidden");
    }
    function hideUrlError() {
        urlError.classList.add("hidden");
    }

    // =====================================================================
    // Event wiring
    // =====================================================================
    btnFetch.addEventListener("click", startFetch);
    btnReport.addEventListener("click", generateReport);
    btnNewTab.addEventListener("click", openInNewTab);
    btnRestart.addEventListener("click", restartAnalysis);
    btnScreenshot.addEventListener("click", exportScreenshot);
    btnExportCsv.addEventListener("click", () => exportTransactions("csv", btnExportCsv));
    btnExportXlsx.addEventListener("click", () => exportTransactions("xlsx", btnExportXlsx));

    // Advanced options
    btnFetchAll.addEventListener("click", startFetchAll);
    btnImportCsv.addEventListener("click", importCsv);
    btnFindFirst.addEventListener("click", startFindFirst);
    csvFileInput.addEventListener("change", () => {
        btnImportCsv.disabled = !csvFileInput.files || !csvFileInput.files[0];
    });
    btnSettings.addEventListener("click", openSettings);
    btnTheme.addEventListener("click", () => {}); // handled above via addEventListener

    $("btn-save-llm").addEventListener("click", saveLlmConfig);
    $("btn-test-llm").addEventListener("click", testLlm);
    $("btn-toggle-key").addEventListener("click", toggleKeyVisibility);
    $("btn-clear-key").addEventListener("click", clearApiKey);

    document.querySelectorAll("[data-close-modal]").forEach((el) => {
        el.addEventListener("click", () => {
            closeSettings();
            aboutModal.classList.add("hidden");
            document.body.style.overflow = "";
        });
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeSettings();
            aboutModal.classList.add("hidden");
            document.body.style.overflow = "";
        }
    });

    $("url-help-toggle").addEventListener("click", () => {
        $("url-help").classList.toggle("hidden");
    });

    $("link-about").addEventListener("click", (e) => {
        e.preventDefault();
        aboutModal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
        loadCacheInfo();
    });

    $("btn-clear-cache").addEventListener("click", clearCache);

    async function loadCacheInfo() {
        try {
            const res = await fetch("/api/cache");
            const data = await res.json();
            $("cache-info").textContent =
                `${data.count} 个文件，${data.size_mb} MB`;
        } catch (err) {
            $("cache-info").textContent = "读取失败";
        }
    }

    async function clearCache() {
        if (!confirm("确定要清空所有缓存的交易数据吗？")) return;
        try {
            const res = await fetch("/api/cache", { method: "DELETE" });
            const data = await res.json();
            toast(`已清空 ${data.removed} 个缓存文件`, "info");
            loadCacheInfo();
        } catch (err) {
            toast("清空缓存失败", "error");
        }
    }

    // Ctrl/Cmd+Enter in textarea submits
    urlInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            startFetch();
        }
    });

    // Quick range shortcuts
    document.querySelectorAll("[data-range]").forEach((el) => {
        el.addEventListener("click", () => {
            const months = parseInt(el.dataset.range, 10);
            const today = new Date();
            const start = new Date(today);
            start.setMonth(start.getMonth() - months);
            endDate.value = formatDate(today);
            startDate.value = formatDate(start);
        });
    });

    // Cleanup SSE on page unload
    window.addEventListener("beforeunload", () => {
        stopSSE();
        stopPolling();
    });

    // =====================================================================
    // Init
    // =====================================================================
    initDates();
    initTheme();
    refreshLlmBadge();
})();