/**
 * spyre-api-client.js
 *
 * Frontend API client for the Spyre Dashboard.
 * Communicates with the secure backend API (Flask) which handles all database operations.
 *
 * SECURITY ARCHITECTURE:
 * ----------------------
 * Frontend (this file) → Backend API (Flask) → ClickHouse Database
 *        ↓                      ↓                      ↓
 *   No secrets          Handles auth & SQL      Credentials
 *   Parameters only     Hardcoded queries       Secure storage
 *
 * This file:
 * - Makes HTTP requests to backend API endpoints
 * - Sends only parameters (filters, limits, IDs)
 * - Never sends SQL queries or credentials
 * - Formats data for dashboard display
 *
 * Backend API handles:
 * - ClickHouse authentication
 * - SQL query execution
 * - Data validation and sanitization
 *
 * Usage:
 *   <script src="spyre-api-client.js"></script>
 *
 */

(function () {
  "use strict";

  // ─── Configuration ─────────────────────────────────────────
  function getConfig() {
    
    return {
      // apiUrl: apiUrl,
      apiUrl : 'http://localhost:5000/api',
      limit : 10
      
    };
  }

  function configFromMeta(name) {
    const el = document.querySelector(`meta[name="spyre-${name}"]`);
    return el ? el.getAttribute("content") : null;
  }

  // ─── Backend API query helper ──────────────────────────────
  /**
   * Execute a query via the secure backend API.
   * Backend handles all authentication AND SQL queries - no SQL exposed to client.
   * Frontend only passes parameters (filters, limits, etc.)
   */
  async function apiQuery(endpoint, options = {}) {
    const cfg = getConfig();
    const url = `${cfg.apiUrl}${endpoint}`;
    
    const res = await fetch(url, {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(error.error || `API error ${res.status}`);
    }

    return res.json();
  }

  // ─── Fetch commits list (grouped by commit SHA) ────────────
  async function fetchCommits(offset = 0, limit = 30, branchFilters = ['push', 'merge-queue', 'commit']) {
    const cfg = getConfig();
    
    if (branchFilters.length === 0) {
      return { data: [], count: 0, total: 0 };
    }
    
    // Build query parameters - NO SQL in frontend!
    const params = new URLSearchParams({
      offset: offset.toString(),
      limit: limit.toString(),
    });
    
    // Add branch filters as multiple parameters
    branchFilters.forEach(filter => {
      params.append('branch_filter', filter);
    });
    
    const result = await apiQuery(`/commits?${params}`);
    // Return full result object with data, count, and total
    return {
      data: result.data || [],
      count: result.count || 0,
      total: result.total || 0
    };
  }

  // ─── Fetch all runs for a specific commit ─────────────────
  // async function fetchRunsForCommit(commitSha, branch, workflow) {
  //   const cfg = getConfig();
  //   const branchFilter = branch ? `AND branch = '${branch.replace(/'/g, "\\'")}'` : "";
  //   const workflowFilter = workflow ? `AND workflow = '${workflow.replace(/'/g, "\\'")}'` : "";

  //   const sql = `
  //     SELECT
  //       run_id,
  //       workflow,
  //       suite_name,
  //       filename,
  //       branch,
  //       commit_sha,
  //       gha_run_id,
  //       triggered_at,
  //       total_tests,
  //       passed,
  //       failed,
  //       skipped,
  //       errors,
  //       xpass,
  //       xfail,
  //       duration_s
  //     FROM ${cfg.db}.test_runs
  //     WHERE commit_sha = '${commitSha.replace(/'/g, "\\'")}'
  //       ${branchFilter}
  //       ${workflowFilter}
  //     ORDER BY triggered_at DESC
  //   `;
  //   return chQuery(sql.trim());
  // }

  // ─── Fetch run list ────────────────────────────────────────
  async function fetchRecentRuns() {
    const cfg = getConfig();
    
    const params = new URLSearchParams({
      limit: cfg.limit.toString(),
    });
    
    const result = await apiQuery(`/runs?${params}`);
    return result.data || [];
  }

  // ─── Fetch all test cases for a run ───────────────────────
  async function fetchTestCases(runId) {
    // Call backend API - SQL is in backend, not exposed to frontend
    const result = await apiQuery(`/test-cases/${runId}`);
    const caseRows = result.data || [];

    // Convert DB rows to the shape dashboard.html's parseXML() produces
    const tests = caseRows.map((row) => {
      // Properties are already attached by backend
      const properties = [];
      if (row.properties && Array.isArray(row.properties)) {
        row.properties.forEach(p => {
          const propString = p.prop_name === "tag" ? p.prop_value : p.prop_name;
          properties.push(propString);
        });
      }
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
    const configured = !!cfg.apiUrl;

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
              ${configured ? `Connected via secure backend API` : "Not configured — backend API unavailable"}
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
                  onclick="window.__chLoadRun('${r.run_id}','${safeName}',${r.triggered_at ? `new Date('${r.triggered_at}').getTime()` : Date.now()},{workflow:'${(r.workflow || "").replace(/'/g, "\\'")}',gha_run_id:'${(r.gha_run_id || "").replace(/'/g, "\\'")}',branch:'${(r.branch || "").replace(/'/g, "\\'")}',commit_sha:'${(r.commit_sha || "").replace(/'/g, "\\'")}'})">
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
  window.__chLoadRun = async function (runId, filename, timestamp, metadata) {
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
        // Add metadata if provided
        ...(metadata && {
          aggregatedData: {
            workflow: metadata.workflow,
            gha_run_id: metadata.gha_run_id,
            branch: metadata.branch,
            commit_sha: metadata.commit_sha,
          }
        })
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

  // ─── Fetch commits (exposed globally) ──────────────────────
  window.__chFetchCommits = async function (offset = 0, limit = 30, branchFilters = ['push', 'merge-queue', 'commit']) {
    try {
      return await fetchCommits(offset, limit, branchFilters);
    } catch (err) {
      console.error("[spyre-clickhouse] fetch commits error:", err);
      throw err;
    }
  };

  // ─── Fetch test cases with properties for a commit ────────
  async function fetchTestCasesForCommit(commitSha, branchFilters) {
    // Call backend API with commit SHA and branch filters as parameters
    const params = new URLSearchParams({
      commit_sha: commitSha,
    });
    
    // Add branch filters
    if (branchFilters && Array.isArray(branchFilters)) {
      branchFilters.forEach(filter => {
        params.append('branch_filter', filter);
      });
    }
    
    const result = await apiQuery(`/commit-tests/${commitSha}?${params}`);
    return result.data || [];
  }

  // ─── Load aggregated commit data (all workflows combined) ──
  window.__chLoadAllRunsForCommit = async function (commitSha, branch, workflow, branchFilters) {
    try {
      // Store the active branch filters (what user selected in the UI)
      const activeBranchFilters = branchFilters || ['push', 'merge-queue', 'commit'];
      
      if (activeBranchFilters.length === 0) {
        console.log('[spyre-clickhouse] No branch filters selected');
        return 0;
      }
      
      // Call backend API with parameters - NO SQL in frontend!
      const params = new URLSearchParams();
      activeBranchFilters.forEach(filter => {
        params.append('branch_filter', filter);
      });
      
      const result = await apiQuery(`/commits/${commitSha}?${params}`);
      const commitData = result.data || [];
      
      if (!commitData || commitData.length === 0) {
        throw new Error(`No data found for commit ${commitSha}`);
      }

      const commit = commitData[0];
      const shortSha = commitSha.substring(0, 8);
      
      // Check for duplicate (same commit already loaded)
      if (runs.some((r) => r._commitSha === commitSha)) {
        console.log(`[spyre-clickhouse] Commit ${shortSha} already loaded`);
        return 0;
      }

      // Fetch detailed test cases with properties for filtering
      console.log(`[spyre-clickhouse] Fetching test cases for commit ${shortSha} with branch filter...`);
      const testCaseRows = await fetchTestCasesForCommit(commitSha, activeBranchFilters);
      
      // Convert to dashboard format
      const tests = testCaseRows.map(row => {
        const properties = [];
        if (row.properties && Array.isArray(row.properties)) {
          row.properties.forEach(prop => {
            // Backend returns prop_name and prop_value (from ClickHouse)
            const propName = prop.prop_name || prop.name;
            const propValue = prop.prop_value || prop.value;
            
            // Convert property to string format: "dtype__float32", "op__add", etc.
            if (propName === 'tag') {
              properties.push(propValue);
            } else if (propValue === 'True' || propValue === true) {
              properties.push(propName);
            } else {
              properties.push(`${propName}__${propValue}`);
            }
          });
        }
        
        return {
          name: row.name,
          cls: row.classname,
          clsShort: row.classname ? row.classname.split('.').pop() : '',
          timeVal: parseFloat(row.duration_s) || 0,
          file: row.classname ? row.classname.replace(/\./g, '/') + '.py' : '',
          status: row.status,
          failMsg: row.fail_message || '',
          tags: [],
          testMethod: '',
          opName: row.op_name || '(no op)',
          dtype: row.dtype || '',
          module: row.module || '',
          properties: properties
        };
      });

      console.log(`[spyre-clickhouse] Loaded ${tests.length} test cases for commit ${shortSha}`);

      // Categorize branches by type
      const branches = commit.branches || [];
      const branchTypes = {
        push: [],
        'merge-queue': [],
        commit: []
      };
      
      branches.forEach(b => {
        if (b === 'main') {
          branchTypes.push.push(b);
        } else if (b && b.startsWith('gh-readonly-queue')) {
          branchTypes['merge-queue'].push(b);
        } else {
          branchTypes.commit.push(b);
        }
      });

      // Create aggregated run object
      const run = {
        _commitSha: commitSha,
        _isAggregated: true,
        filename: `Commit ${shortSha} (${commit.workflows.length} workflows)`,
        timestamp: new Date(commit.triggered_at).getTime() || Date.now(),
        tests: tests, // Now populated with actual test data for filtering
        modelMap: typeof buildGroupMap === "function" ? buildGroupMap(tests, groupBy) : {},
        aggregatedData: {
          commit_sha: commitSha,
          branches: branches,
          branch_types: branchTypes,
          branch_filters_applied: activeBranchFilters,
          pr_number: commit.pr_number,
          workflows: commit.workflows,
          gha_run_ids: commit.gha_run_ids,
          passed: commit.passed,
          failed: commit.failed,
          xfail: commit.xfail,
          xpass: commit.xpass,
          skipped: commit.skipped,
          total_tests: commit.total_tests,
        }
      };
      console.log("--aggregated results--\n",run);

      runs.push(run);
      runs.sort((a, b) => a.timestamp - b.timestamp);

      // Find the index of the newly added run after sorting
      const newRunIndex = runs.findIndex(r => r._commitSha === commitSha);

      // Update UI
      if (typeof selectRun === "function" && newRunIndex >= 0) {
        selectRun(newRunIndex);
      }
      if (typeof updateRunList === "function") {
        updateRunList();
      }

      console.log(`[spyre-clickhouse] Loaded aggregated data for commit ${shortSha}`);
      return 1;
    } catch (err) {
      console.error("[spyre-clickhouse] load commit error:", err);
      throw err;
    }
  };

  // ─── Auto-load latest run on page open ────────────────────
  // Set window.SPYRE_CH_AUTOLOAD = true to load the most recent run
  // automatically when the dashboard opens (useful for a Helm deployment
  // where the dashboard is the primary UI, not a one-off HTML file).
  async function maybeAutoLoad() {
    if (!window.SPYRE_CH_AUTOLOAD) return;
    const cfg = getConfig();
    if (!cfg.apiUrl) return;
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