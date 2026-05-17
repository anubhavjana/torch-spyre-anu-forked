/**
 * spyre-clickhouse.js
 *
 * Drop-in replacement for the manual XML upload in dashboard.html.
 * Add this <script> tag to dashboard.html AFTER the main <script> block:
 *
 *   <script src="spyre-clickhouse.js"></script>
 *
 * Or paste the contents directly into dashboard.html.
 *
 * Configuration — set these as global JS variables before this script loads,
 * or via a <meta> tag pattern (see configFromMeta() below):
 *
 *   window.SPYRE_CH_URL      = "https://clickhouse.internal.example.com:8443"
 *   window.SPYRE_CH_USER     = "spyre_reader"
 *   window.SPYRE_CH_PASS     = "..."   // only for dev; use token auth in prod
 *   window.SPYRE_CH_DB       = "spyre"
 *   window.SPYRE_CH_TOKEN    = "..."   // preferred: ClickHouse JWT / API token
 *   window.SPYRE_CH_WORKFLOW = ""      // optional filter: "module-tests"
 *   window.SPYRE_CH_LIMIT    = 30      // how many recent runs to auto-load
 */

(function () {
  "use strict";

  // ─── Configuration ─────────────────────────────────────────
  function getConfig() {
    return {
      url:      window.SPYRE_CH_URL      || configFromMeta("ch-url")      || "",
      user:     window.SPYRE_CH_USER     || configFromMeta("ch-user")     || "default",
      pass:     window.SPYRE_CH_PASS     || configFromMeta("ch-pass")     || "",
      token:    window.SPYRE_CH_TOKEN    || configFromMeta("ch-token")    || "",
      db:       window.SPYRE_CH_DB       || configFromMeta("ch-db")       || "spyre",
      workflow: window.SPYRE_CH_WORKFLOW || configFromMeta("ch-workflow") || "",
      limit:    parseInt(window.SPYRE_CH_LIMIT || configFromMeta("ch-limit") || "30", 10),
    };
  }

  function configFromMeta(name) {
    const el = document.querySelector(`meta[name="spyre-${name}"]`);
    return el ? el.getAttribute("content") : null;
  }

  // ─── ClickHouse HTTP query helper ──────────────────────────
  /**
   * Execute a ClickHouse SQL query via the HTTP interface.
   * Returns parsed JSON rows (FORMAT JSONEachRow).
   */
  async function chQuery(sql) {
    const cfg = getConfig();
    if (!cfg.url) throw new Error("SPYRE_CH_URL is not configured");

    const params = new URLSearchParams({
      database:                   cfg.db,
      default_format:             "JSONEachRow",
      max_result_rows:            "100000",
      result_overflow_mode:       "break",
    });

    const headers = { "Content-Type": "text/plain" };
    // ClickHouse Cloud uses X-ClickHouse-User/Key headers, not Bearer tokens.
    // cfg.token holds the password (stored in K8s secret as "token" key).
    headers["X-ClickHouse-User"] = cfg.user;
    headers["X-ClickHouse-Key"]  = cfg.token || cfg.pass;

    const res = await fetch(`${cfg.url}?${params}`, {
      method: "POST",
      headers,
      body: sql,
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`ClickHouse error ${res.status}: ${text.slice(0, 300)}`);
    }

    const text = await res.text();
    if (!text.trim()) return [];

    // JSONEachRow → one JSON object per line
    return text
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  }

  // ─── Fetch run list ────────────────────────────────────────
  async function fetchRecentRuns() {
    const cfg = getConfig();
    const workflowFilter = cfg.workflow
      ? `AND workflow = '${cfg.workflow.replace(/'/g, "\\'")}'`
      : "";

    const sql = `
      SELECT
        run_id,
        workflow,
        suite_name,
        filename,
        branch,
        commit_sha,
        gha_run_id,
        triggered_at,
        total_tests,
        passed,
        failed,
        skipped,
        errors,
        xpass,
        duration_s
      FROM ${cfg.db}.test_runs
      WHERE 1=1 ${workflowFilter}
      ORDER BY triggered_at DESC
      LIMIT ${cfg.limit}
    `;
    return chQuery(sql.trim());
  }

  // ─── Fetch all test cases for a run ───────────────────────
  async function fetchTestCases(runId) {
    const cfg = getConfig();
    const caseSql = `
      SELECT
        tc.case_id,
        tc.classname,
        tc.name,
        tc.op_name,
        tc.dtype,
        tc.status,
        tc.duration_s,
        tc.fail_message
      FROM ${cfg.db}.test_cases tc
      WHERE tc.run_id = '${runId}'
      ORDER BY tc.classname, tc.name
    `;
    const propSql = `
      SELECT case_id, prop_name, prop_value
      FROM ${cfg.db}.run_properties
      WHERE run_id = '${runId}'
    `;

    const [caseRows, propRows] = await Promise.all([
      chQuery(caseSql.trim()),
      chQuery(propSql.trim()),
    ]);

    // Group properties by case_id
    const propsByCase = {};
    for (const p of propRows) {
      if (!propsByCase[p.case_id]) propsByCase[p.case_id] = [];
      // Reconstruct the property strings the dashboard expects:
      // e.g. prop_name="tag" prop_value="model__granite3b" → "model__granite3b"
      //      prop_name="granite" prop_value="True" → "granite"
      const propString =
        p.prop_name === "tag" ? p.prop_value : p.prop_name;
      propsByCase[p.case_id].push(propString);
    }

    // Convert DB rows to the shape dashboard.html's parseXML() produces
    const tests = caseRows.map((row) => {
      const properties = propsByCase[row.case_id] || [];
      const tags = [];
      const re = /\[([^\[\]]+)\]/g;
      let m;
      while ((m = re.exec(row.name)) !== null) {
        m[1].split("][").forEach((t) => { if (t && !tags.includes(t)) tags.push(t); });
      }
      const clsParts = (row.classname || "").split(".");
      const clsShort = clsParts[clsParts.length - 1] || row.classname;
      return {
        name:       row.name,
        cls:        row.classname,
        clsShort,
        timeVal:    parseFloat(row.duration_s) || 0,
        file:       row.classname.replace(/\./g, "/") + ".py",
        status:     row.status,
        failMsg:    row.fail_message || "",
        tags,
        testMethod: "",
        opName:     row.op_name || "(no op)",
        dtype:      row.dtype || "",
        properties,
      };
    });

    // Mark whether op and module tags are present (used by sidebar submenu logic)
    const hasOpTags     = tests.some((t) => t.properties.some((p) => p.startsWith("op__")));
    const hasModuleTags = tests.some((t) => t.properties.some((p) => p.startsWith("module__")));
    Object.defineProperty(tests, "hasOpTags",     { value: hasOpTags,     enumerable: false });
    Object.defineProperty(tests, "hasModuleTags", { value: hasModuleTags, enumerable: false });

    return tests;
  }

  // ─── Build the UI panel ────────────────────────────────────
  function buildFetchPanel() {
    const cfg = getConfig();
    const configured = !!cfg.url;

    // Inject a "Fetch from ClickHouse" section into the upload panel
    const uploadPanel = document.getElementById("panel-upload");
    if (!uploadPanel) return;

    const section = document.createElement("div");
    section.id = "ch-fetch-section";
    section.style.cssText = "margin-top:24px";
    section.innerHTML = `
      <div class="surface">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
          <div>
            <div style="font-family:var(--mono);font-size:13px;font-weight:500;color:var(--text)">
              Auto-fetch from ClickHouse
            </div>
            <div style="font-size:12px;color:var(--text3);margin-top:3px">
              ${configured ? `Connected: <code style="font-size:11px">${cfg.url}</code>` : "Not configured — set SPYRE_CH_URL"}
            </div>
          </div>
          <button class="btn btn-primary" id="ch-fetch-btn"
            onclick="window.__chFetchRuns()"
            ${configured ? "" : "disabled"}>
            ↓ Load latest ${cfg.limit} runs
          </button>
        </div>

        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px">
          <div style="display:flex;gap:6px;align-items:center">
            <label style="font-size:11px;font-family:var(--mono);color:var(--text3)">WORKFLOW</label>
            <select id="ch-workflow-filter" class="btn btn-sm" style="min-width:160px">
              <option value="">All workflows</option>
              <option value="module-tests" ${cfg.workflow === "module-tests" ? "selected" : ""}>module-tests</option>
              <option value="upstream-tests" ${cfg.workflow === "upstream-tests" ? "selected" : ""}>upstream-tests</option>
            </select>
          </div>
          <div style="display:flex;gap:6px;align-items:center">
            <label style="font-size:11px;font-family:var(--mono);color:var(--text3)">BRANCH</label>
            <input id="ch-branch-filter" class="search-input" placeholder="e.g. main"
              style="width:140px;padding:6px 10px" value="">
          </div>
          <div style="display:flex;gap:6px;align-items:center">
            <label style="font-size:11px;font-family:var(--mono);color:var(--text3)">LIMIT</label>
            <input id="ch-limit-input" class="search-input" type="number"
              min="1" max="200" style="width:70px;padding:6px 10px" value="${cfg.limit}">
          </div>
        </div>

        <div id="ch-run-list" style="display:none">
          <div style="font-size:11px;font-family:var(--mono);color:var(--text3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">
            available runs
          </div>
          <div class="table-wrap" style="max-height:340px">
            <table class="test-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Filename</th>
                  <th>Workflow</th>
                  <th>Branch</th>
                  <th>Date</th>
                  <th style="text-align:center">Tests</th>
                  <th style="text-align:center">Pass%</th>
                  <th style="text-align:center">Load</th>
                </tr>
              </thead>
              <tbody id="ch-run-rows"></tbody>
            </table>
          </div>
        </div>

        <div id="ch-status" style="font-size:12px;color:var(--text3);margin-top:8px"></div>
      </div>
    `;
    uploadPanel.appendChild(section);
  }

  // ─── Fetch and display run list ────────────────────────────
  window.__chFetchRuns = async function () {
    const btn    = document.getElementById("ch-fetch-btn");
    const status = document.getElementById("ch-status");
    const list   = document.getElementById("ch-run-list");
    const tbody  = document.getElementById("ch-run-rows");

    // Read current filter values from the UI
    const workflow = document.getElementById("ch-workflow-filter")?.value || "";
    const branch   = document.getElementById("ch-branch-filter")?.value || "";
    const limit    = parseInt(document.getElementById("ch-limit-input")?.value || "30", 10);

    // Temporarily override config
    window.SPYRE_CH_WORKFLOW = workflow;
    window.SPYRE_CH_LIMIT    = limit;

    if (btn) btn.disabled = true;
    status.textContent = "Fetching run list…";
    list.style.display = "none";

    try {
      let runRows = await fetchRecentRuns();

      // Client-side branch filter (keeps SQL simple)
      if (branch) {
        runRows = runRows.filter((r) => r.branch === branch || r.branch.includes(branch));
      }

      if (!runRows.length) {
        status.textContent = "No runs found for the selected filters.";
        return;
      }

      tbody.innerHTML = runRows
        .map((r, i) => {
          const total    = parseInt(r.total_tests) || 0;
          const pass     = parseInt(r.passed) + parseInt(r.xpass || 0);
          const pct      = total ? Math.round((pass / total) * 100) : 0;
          const color    = pct >= 90 ? "var(--pass)" : pct >= 60 ? "var(--xfail)" : "var(--fail)";
          const date     = new Date(r.triggered_at).toLocaleString();
          const safeName = (r.filename || "").replace(/"/g, "&quot;");
          return `
            <tr>
              <td style="color:var(--text3)">${i + 1}</td>
              <td style="font-family:var(--mono);font-size:11px" title="${safeName}">${safeName}</td>
              <td style="font-size:11px">${r.workflow}</td>
              <td style="font-size:11px">${r.branch}</td>
              <td style="font-size:11px;color:var(--text3)">${date}</td>
              <td style="text-align:center">${total}</td>
              <td style="text-align:center;font-weight:600;color:${color}">${pct}%</td>
              <td style="text-align:center">
                <button class="btn btn-sm btn-primary"
                  onclick="window.__chLoadRun('${r.run_id}','${safeName}',${r.triggered_at ? `new Date('${r.triggered_at}').getTime()` : Date.now()})">
                  Load
                </button>
              </td>
            </tr>`;
        })
        .join("");

      list.style.display = "block";
      status.textContent = `${runRows.length} run(s) found. Click "Load" to import into the dashboard.`;
    } catch (err) {
      status.textContent = `Error: ${err.message}`;
      console.error("[spyre-clickhouse] fetch error:", err);
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  // ─── Load a single run's test cases ───────────────────────
  window.__chLoadRun = async function (runId, filename, timestamp) {
    const status = document.getElementById("ch-status");
    status.textContent = `Loading test cases for ${filename}…`;

    try {
      const tests = await fetchTestCases(runId);

      // Check for duplicate (same runId already loaded)
      if (runs.some((r) => r._runId === runId)) {
        toast(`Already loaded: ${filename}`);
        status.textContent = "";
        return;
      }

      const run = {
        _runId:    runId,
        filename,
        timestamp: timestamp || Date.now(),
        tests,
        modelMap:  typeof buildGroupMap === "function"
          ? buildGroupMap(tests, groupBy)
          : {},
      };

      runs.push(run);
      runs.sort((a, b) => a.timestamp - b.timestamp);

      // Delegate to the existing dashboard functions
      if (typeof selectRun === "function") selectRun(runs.length - 1);
      if (typeof updateRunList === "function") updateRunList();
      if (typeof switchTab === "function") switchTab("overview");

      toast(`✓ Loaded ${tests.length} tests from ${filename}`);
      status.textContent = `✓ ${filename} loaded successfully.`;
    } catch (err) {
      status.textContent = `Error loading run: ${err.message}`;
      console.error("[spyre-clickhouse] load error:", err);
    }
  };

  // ─── Auto-load latest run on page open ────────────────────
  // Set window.SPYRE_CH_AUTOLOAD = true to load the most recent run
  // automatically when the dashboard opens (useful for a Helm deployment
  // where the dashboard is the primary UI, not a one-off HTML file).
  async function maybeAutoLoad() {
    if (!window.SPYRE_CH_AUTOLOAD) return;
    const cfg = getConfig();
    if (!cfg.url) return;
    try {
      const runRows = await fetchRecentRuns();
      if (!runRows.length) return;
      const newest = runRows[0];
      await window.__chLoadRun(
        newest.run_id,
        newest.filename,
        new Date(newest.triggered_at).getTime()
      );
      console.log("[spyre-clickhouse] Auto-loaded:", newest.filename);
    } catch (err) {
      console.warn("[spyre-clickhouse] Auto-load failed:", err.message);
    }
  }

  // ─── Init ──────────────────────────────────────────────────
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      buildFetchPanel();
      maybeAutoLoad();
    });
  } else {
    buildFetchPanel();
    maybeAutoLoad();
  }
})();