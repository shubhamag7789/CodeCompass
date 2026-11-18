let analysis = null;
let currentRepoId = null;
let repositoriesList = [];
let conversationId = null;

// Graph state with pan, zoom, and progressive expansion
let graphState = {
  filter: "all",
  query: "",
  nodes: [],
  edges: [],
  positions: new Map(),
  selected: null,
  expanded: new Set(["repo:root"]),
  childrenByParent: new Map(),
  parentByChild: new Map(),
  nodesById: new Map(),
  incomingRels: new Map(),
  outgoingRels: new Map(),
  scale: 1,
  panX: 0,
  panY: 0,
  isDragging: false,
  dragStartX: 0,
  dragStartY: 0,
  toggles: {
    hierarchy: true,
    incoming: true,
    outgoing: true,
  },
};

const typeColors = {
  Repository: "#6366f1",
  Directory: "#94a3b8",
  File: "#0ea5e9",
  Class: "#a855f7",
  Function: "#10b981",
  Method: "#14b8a6",
  API: "#f59e0b",
  ExternalDependency: "#f43f5e",
};

// INITIALIZATION
async function init() {
  setupEventListeners();
  loadAiStatus();
  await loadRepositories();
  await loadAnalysis();
}

async function loadAiStatus() {
  const badge = document.getElementById("aiModelBadge");
  if (!badge) return;
  try {
    const res = await fetch("/api/ai/status");
    if (!res.ok) return;
    const data = await res.json();
    if (data.configured && data.provider === "gemini") {
      const modelDisplay = data.model && data.model.includes("3.5") ? "Gemini 3.5 Flash Lite" : (data.model || "Gemini Flash Lite");
      badge.textContent = `● ${modelDisplay}`;
      badge.className = "ai-status-badge ai-status-gemini";
      badge.title = `Google Gemini Active (${data.model || "gemini-3.5-flash-lite"})`;
    } else if (data.configured && data.provider === "openrouter") {
      badge.textContent = "● OpenRouter AI";
      badge.className = "ai-status-badge ai-status-openrouter";
      badge.title = `OpenRouter Active (${data.model || "custom"})`;
    } else {
      badge.textContent = "● Local Extractive";
      badge.className = "ai-status-badge ai-status-local";
      badge.title = "Offline mode: local AST & BM25 retrieval";
    }
  } catch (err) {
    console.warn("Could not load AI status:", err);
  }
}

async function loadRepositories() {
  try {
    const res = await fetch("/api/repositories");
    if (!res.ok) return;
    const data = await res.json();
    repositoriesList = data.repositories || [];
    currentRepoId = data.active_repo_id || (repositoriesList[0] ? repositoriesList[0].id : "default");
    renderRepoHistoryModal();
  } catch (err) {
    console.warn("Could not load repositories list:", err);
  }
}

async function loadAnalysis(repoId = "") {
  try {
    const url = repoId ? `/api/analysis?repo=${encodeURIComponent(repoId)}` : "/api/analysis";
    const response = await fetch(url);
    const payload = await response.json();
    if (!response.ok) {
      renderMissing(payload.error || "No analysis available.");
      return;
    }
    analysis = payload;
    currentRepoId = payload.active_repo_id || currentRepoId;
    renderAll();
    loadFilesTree();
  } catch (err) {
    renderMissing(err.message);
  }
}

function renderMissing(message) {
  document.getElementById("repoName").textContent = "No repository";
  document.getElementById("headline").textContent = message;
  document.getElementById("metrics").innerHTML = "";
  document.getElementById("chatLog").innerHTML = `<div class="chat-entry chat-codecompass"><span class="chat-role">CodeCompass AI</span><div class="chat-text">Import a local folder or public GitHub URL to begin.</div></div>`;
}

function renderAll() {
  const repoMeta = analysis.repository || {};
  const repoName = repoMeta.name || "Repository";
  document.getElementById("repoName").textContent = repoName;
  const repoBreadcrumb = document.getElementById("topbarRepoBreadcrumb");
  if (repoBreadcrumb) repoBreadcrumb.textContent = repoName;
  document.getElementById("headline").textContent = analysis.summary?.headline || "CodeCompass Architecture Overview";

  // Update sidebar badge
  const sourceTag = document.getElementById("repoSourceType");
  if (sourceTag) {
    sourceTag.textContent = repoMeta.path?.startsWith("http") ? "github" : "local";
  }

  renderMetrics();
  renderLayers();
  renderComponents();
  renderApis();
  renderRoleOnboarding("backend");
  loadDiscoveredFlows();
  renderImpactSelector();
  prepareGraph();
  resetConversation();
}

// METRICS
function renderMetrics() {
  const stats = analysis.summary?.stats || {};
  const metrics = [
    ["Files", stats.files || 0],
    ["APIs", stats.apis || 0],
    ["Classes", stats.classes || 0],
    ["Functions", stats.functions || 0],
    ["Imports", stats.imports || 0],
    ["Total Lines", stats.lines || 0],
  ];
  document.getElementById("metrics").innerHTML = metrics
    .map(([label, value]) => `
      <article class="metric">
        <span>${escapeHtml(label)}</span>
        <strong>${Number(value).toLocaleString()}</strong>
      </article>
    `)
    .join("");
}

// LAYERS
function renderLayers() {
  const layers = analysis.summary?.architecture_layers || [];
  document.getElementById("layerFlow").innerHTML =
    layers
      .map(
        (layer) => `
          <div class="layer">
            <strong>${escapeHtml(layer.name)}</strong>
            <span>${layer.files} files</span>
          </div>
        `
      )
      .join("") || `<p class="empty-hint">No architecture layers detected yet.</p>`;
}

// COMPONENTS
function renderComponents() {
  document.getElementById("components").innerHTML =
    (analysis.components || [])
      .map(
        (component) => `
          <article class="component">
            <strong>${escapeHtml(component.name)}</strong>
            <p>${escapeHtml(component.responsibility)}</p>
            <div class="component-meta">
              <span>${component.files} files / ${component.lines} lines</span>
              <span>•</span>
              <span>${escapeHtml((component.languages || []).join(", "))}</span>
            </div>
          </article>
        `
      )
      .join("") || `<p class="empty-hint">No components detected yet.</p>`;
}

// APIS
function renderApis() {
  const query = document.getElementById("apiSearch").value.toLowerCase();
  const apis = (analysis.apis || []).filter((api) => `${api.method} ${api.path} ${api.file}`.toLowerCase().includes(query));
  document.getElementById("apiTable").innerHTML =
    apis
      .map(
        (api) => `
          <div class="api-row">
            <span class="method ${escapeHtml(api.method)}">${escapeHtml(api.method)}</span>
            <strong>${escapeHtml(api.path)}</strong>
            <span class="api-source-link" onclick="previewFile('${escapeHtml(api.file)}')">${escapeHtml(api.file)}:${api.line}</span>
          </div>
        `
      )
      .join("") || `<p class="empty-hint" style="padding: 20px;">No matching API routes detected.</p>`;
}

// ROLE-BASED ONBOARDING
let currentRole = "backend";

async function renderRoleOnboarding(role = "backend") {
  currentRole = role;
  try {
    const res = await fetch(`/api/onboarding?role=${encodeURIComponent(role)}&repo=${encodeURIComponent(currentRepoId || "")}`);
    const guide = await res.json();
    if (!res.ok) throw new Error(guide.error);

    const badge = document.getElementById("roleMissionBadge");
    const heading = document.getElementById("roleGuideHeading");
    const mission = document.getElementById("roleGuideMission");

    if (badge) badge.textContent = `${role.toUpperCase().replace("_", " & ")} ROADMAP`;
    if (heading) heading.textContent = guide.title;
    if (mission) mission.textContent = guide.mission;

    // Timeline steps
    const timelineEl = document.getElementById("readingPathTimeline");
    if (timelineEl) {
      if (!guide.reading_path || !guide.reading_path.length) {
        timelineEl.innerHTML = `<div class="empty-hint">No reading steps generated.</div>`;
      } else {
        timelineEl.innerHTML = guide.reading_path
          .map(
            (step) => `
            <div class="reading-step-card">
              <div class="step-header">
                <span class="step-day-badge">Day ${step.day} • ${step.category}</span>
                <span class="step-title">${escapeHtml(step.title)}</span>
              </div>
              <p class="step-desc">${escapeHtml(step.description)}</p>
              <span class="step-file-tag" onclick="previewFile('${escapeHtml(step.file_path)}')">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                <span>${escapeHtml(step.file_path)}</span>
              </span>
            </div>
          `
          )
          .join("");
      }
    }

    // Key entry points & APIs
    const entryList = document.getElementById("roleEntryList");
    if (entryList) {
      const items = (guide.key_entrypoints || []).concat(
        (guide.important_apis || []).map((a) => ({
          path: a.file || a.path,
          label: `${a.method || "API"} ${a.path || a.label}`,
        }))
      );
      if (!items.length) {
        entryList.innerHTML = `<div class="empty-hint" style="padding: 4px;">None</div>`;
      } else {
        entryList.innerHTML = items
          .slice(0, 8)
          .map(
            (it) => `
            <div class="role-side-item" onclick="previewFile('${escapeHtml(it.path)}')">
              <span class="item-title">${escapeHtml(it.label)}</span>
              <span style="font-size: 10px; color: var(--accent-blue);">View</span>
            </div>
          `
          )
          .join("");
      }
    }

    // Key test suites
    const testList = document.getElementById("roleTestList");
    if (testList) {
      if (!guide.key_test_suites || !guide.key_test_suites.length) {
        testList.innerHTML = `<div class="empty-hint" style="padding: 4px;">No test files detected</div>`;
      } else {
        testList.innerHTML = guide.key_test_suites
          .slice(0, 6)
          .map(
            (tf) => `
            <div class="role-side-item" onclick="previewFile('${escapeHtml(tf)}')">
              <span class="item-title">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
                ${escapeHtml(tf.split("/").pop())}
              </span>
              <span style="font-size: 10px; color: var(--text-faint);">${escapeHtml(tf)}</span>
            </div>
          `
          )
          .join("");
      }
    }

    // High risk gotchas
    const riskList = document.getElementById("roleRiskList");
    if (riskList) {
      if (!guide.high_risk_components || !guide.high_risk_components.length) {
        riskList.innerHTML = `<div class="empty-hint" style="padding: 4px;">No high-risk bottlenecks identified</div>`;
      } else {
        riskList.innerHTML = guide.high_risk_components
          .slice(0, 5)
          .map(
            (hr) => `
            <div class="role-side-item" onclick="focusImpact('${escapeHtml(hr.id)}')">
              <span class="item-title">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                ${escapeHtml(hr.label)}
              </span>
              <span style="font-size: 10.5px; color: var(--danger); font-weight: 700;">${hr.affected_files_count} affected</span>
            </div>
          `
          )
          .join("");
      }
    }
  } catch (err) {
    console.error("Could not load role onboarding:", err);
  }
}

// FEATURE FLOW TRACER
let activeFlowData = null;

async function loadDiscoveredFlows() {
  const select = document.getElementById("flowPresetSelect");
  if (!select) return;
  try {
    const res = await fetch(`/api/flow/discover?repo=${encodeURIComponent(currentRepoId || "")}`);
    const data = await res.json();
    const flows = data.flows || [];
    select.innerHTML =
      `<option value="">Select an API route or Controller...</option>` +
      flows
        .map(
          (f) => `
        <option value="${escapeHtml(f.id)}">${escapeHtml(f.name)} (${escapeHtml(f.category)})</option>
      `
        )
        .join("");

    if (flows.length > 0) {
      select.value = flows[0].id;
      traceFeatureFlow(flows[0].id, null);
    }
  } catch (err) {
    console.warn("Could not load discoverable flows:", err);
  }
}

async function traceFeatureFlow(entryPointId, query) {
  const heading = document.getElementById("flowNameHeading");
  const timeline = document.getElementById("flowStepsTimeline");
  const chips = document.getElementById("flowStatsChips");
  const mermaidBox = document.getElementById("flowMermaidCode");

  if (heading) heading.textContent = "Tracing execution path...";
  if (timeline) timeline.innerHTML = `<div class="empty-hint" style="padding: 24px; text-align: center;">Walking call graph...</div>`;

  try {
    const params = new URLSearchParams();
    if (currentRepoId) params.set("repo", currentRepoId);
    if (entryPointId) params.set("id", entryPointId);
    if (query) params.set("query", query);

    const res = await fetch(`/api/flow/trace?${params.toString()}`);
    const flow = await res.json();
    if (!res.ok) throw new Error(flow.error || "Flow trace failed");

    activeFlowData = flow;

    if (heading) heading.textContent = flow.name;
    const catTag = document.getElementById("flowCategoryTag");
    if (catTag) catTag.textContent = (flow.category || "EXECUTION FLOW").toUpperCase();

    if (chips) {
      chips.innerHTML = `
        <span class="flow-stat-pill"><strong>${flow.steps.length}</strong> Steps</span>
        <span class="flow-stat-pill"><strong>${flow.involved_files.length}</strong> Files Touched</span>
      `;
    }

    // Render Steps Timeline
    if (timeline) {
      timeline.innerHTML = flow.steps
        .map(
          (s) => `
          <div class="flow-step-node">
            <div class="flow-step-badge">${s.step_number}</div>
            <div class="flow-step-main">
              <div class="flow-step-top">
                <span class="flow-step-name">${escapeHtml(s.label)}</span>
                <span class="flow-step-rel">${escapeHtml(s.relationship_type)}</span>
              </div>
              <p class="flow-step-desc">${escapeHtml(s.description)}</p>
              <div class="flow-step-meta">
                <span class="method ${escapeHtml(s.type)}" style="font-size: 10px; padding: 2px 6px;">${escapeHtml(s.type)}</span>
                ${
                  s.path
                    ? `<span class="flow-step-code-link" onclick="previewFile('${escapeHtml(s.path)}')">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                        <span>${escapeHtml(s.path)}${s.line ? `:${s.line}` : ""}</span>
                       </span>`
                    : ""
                }
              </div>
            </div>
          </div>
        `
        )
        .join("");
    }

    if (mermaidBox) {
      mermaidBox.textContent = flow.mermaid_sequence || flow.mermaid_flowchart || "(No diagram generated)";
    }
  } catch (err) {
    if (heading) heading.textContent = `Trace Failed: ${err.message}`;
    if (timeline) timeline.innerHTML = `<div class="empty-hint" style="padding: 24px; text-align: center; color: var(--accent-rose);">Could not trace execution flow: ${escapeHtml(err.message)}</div>`;
  }
}

// IMPACT SELECTOR & BLAST RADIUS VIEW
let impactFilter = "all";
let impactSearchQuery = "";

function renderImpactSelector(filterType = null, searchQuery = null) {
  if (filterType !== null) impactFilter = filterType;
  if (searchQuery !== null) impactSearchQuery = searchQuery.trim().toLowerCase();

  const select = document.getElementById("impactSelect");
  if (!select || !analysis?.impact_index) return;

  const currentVal = select.value;

  let items = Object.entries(analysis.impact_index || {})
    .filter(([, item]) => ["File", "Class", "Function", "Method", "API"].includes(item.type || item.kind));

  if (impactFilter === "High") {
    items = items.filter(([, item]) => item.risk === "High");
  } else if (impactFilter === "Medium") {
    items = items.filter(([, item]) => item.risk === "Medium");
  } else if (impactFilter === "API") {
    items = items.filter(([, item]) => (item.type || item.kind) === "API");
  } else if (impactFilter === "Function") {
    items = items.filter(([, item]) => ["Function", "Method"].includes(item.type || item.kind));
  } else if (impactFilter === "File") {
    items = items.filter(([, item]) => (item.type || item.kind) === "File");
  }

  if (impactSearchQuery) {
    items = items.filter(([id, item]) => {
      const lbl = (item.label || "").toLowerCase();
      const path = (item.path || item.file || "").toLowerCase();
      const idStr = id.toLowerCase();
      return lbl.includes(impactSearchQuery) || path.includes(impactSearchQuery) || idStr.includes(impactSearchQuery);
    });
  }

  // Sort: High risk first, then Medium, then Low, then alphabetical
  const riskOrder = { High: 0, Medium: 1, Low: 2 };
  items.sort((a, b) => {
    const diff = (riskOrder[a[1].risk] ?? 2) - (riskOrder[b[1].risk] ?? 2);
    if (diff !== 0) return diff;
    return (a[1].label || "").localeCompare(b[1].label || "");
  });

  if (!items.length) {
    select.innerHTML = `<option value="">No matching targets found</option>`;
    document.getElementById("impactLayout").innerHTML = `
      <div class="empty-hint" style="padding: 40px; text-align: center;">
        No targets match the filter "${escapeHtml(impactFilter)}" and query "${escapeHtml(impactSearchQuery)}".
      </div>
    `;
    return;
  }

  select.innerHTML = items
    .map(([id, item]) => {
      const riskPrefix = item.risk === "High" ? "● High" : (item.risk === "Medium" ? "● Med" : "● Low");
      const kind = item.type || item.kind || "Entity";
      return `<option value="${escapeHtml(id)}">${riskPrefix} · ${escapeHtml(item.label)} (${kind})</option>`;
    })
    .join("");

  // Restore selection if still in filtered list, else pick first
  const exists = items.some(([id]) => id === currentVal);
  if (exists) {
    select.value = currentVal;
  } else {
    select.value = items[0][0];
  }

  renderImpact();
}

async function renderImpact(targetId = null) {
  const select = document.getElementById("impactSelect");
  const layout = document.getElementById("impactLayout");
  if (!layout) return;

  const id = targetId || (select ? select.value : "");
  if (!id) {
    layout.innerHTML = `<div class="empty-hint" style="padding: 30px;">Select an impact target above to view its blast radius.</div>`;
    return;
  }

  if (select && targetId && select.value !== targetId) {
    // If targetId not in select, add it
    let opt = select.querySelector(`option[value="${CSS.escape(targetId)}"]`);
    if (!opt) {
      opt = document.createElement("option");
      opt.value = targetId;
      opt.textContent = `[Target] ${targetId}`;
      select.prepend(opt);
    }
    select.value = targetId;
  }

  // Fetch dynamic detailed impact from backend
  let item = analysis?.impact_index?.[id];
  try {
    const res = await fetch(`/api/impact?id=${encodeURIComponent(id)}&repo=${encodeURIComponent(currentRepoId || "")}`);
    if (res.ok) {
      const liveData = await res.json();
      if (liveData && !liveData.error) {
        item = { ...item, ...liveData };
      }
    }
  } catch (err) {
    console.warn("Could not fetch live impact:", err);
  }

  if (!item) {
    layout.innerHTML = `<div class="empty-hint" style="padding: 30px;">No impact data found for "${escapeHtml(id)}".</div>`;
    return;
  }

  const risk = item.risk || "Low";
  const affectedFiles = item.affected_files || [];
  const affectedApis = item.affected_apis || [];
  const affectedTests = item.affected_tests || [];
  const directDependents = item.direct_dependents || [];
  const transitiveDependents = item.transitive_dependents || [];

  const blastScore = item.blast_score !== undefined
    ? item.blast_score
    : Math.min(100, Math.max(10, (risk === "High" ? 85 : (risk === "Medium" ? 45 : 15)) + affectedFiles.length * 3));

  const blastGaugeColor = risk === "High" ? "#f43f5e" : (risk === "Medium" ? "#f59e0b" : "#10b981");

  const kind = item.kind || item.type || "Component";
  const targetLabel = item.label || id;
  const filePath = item.file || item.path || "";
  const lineInfo = item.line_range ? `:${item.line_range[0]}` : (item.line ? `:${item.line}` : "");

  // Direct callers HTML
  let directHtml = "";
  if (directDependents.length) {
    directHtml = directDependents
      .map(
        (c) => `
        <div class="impact-caller-card" onclick="focusImpact('${escapeHtml(c.id)}')">
          <div class="caller-card-top">
            <span class="caller-name">${escapeHtml(c.name || c.id)}</span>
            <span class="caller-rel-tag">${escapeHtml(c.relation || "CALLS")}</span>
          </div>
          <div class="caller-file">${escapeHtml(c.file || "")}${c.start_line ? `:${c.start_line}` : ""}</div>
        </div>
      `
      )
      .join("");
  } else if (affectedFiles.length > 0) {
    directHtml = affectedFiles.slice(0, 8).map(f => `
      <div class="impact-caller-card" onclick="previewFile('${escapeHtml(f)}')">
        <div class="caller-card-top">
          <span class="caller-name">${escapeHtml(f.split('/').pop())}</span>
          <span class="caller-rel-tag">DEPENDENT</span>
        </div>
        <div class="caller-file">${escapeHtml(f)}</div>
      </div>
    `).join("");
  } else {
    directHtml = `<div class="empty-hint" style="padding: 14px 0; font-size: 12px;">No callers or imports detected (isolated or root entrypoint).</div>`;
  }

  // Transitive & APIs HTML
  let apisAndTransitiveHtml = "";
  if (affectedApis.length) {
    apisAndTransitiveHtml += `
      <div style="margin-bottom: 10px;">
        <span style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase;">Public Endpoints at Risk:</span>
      </div>
      ${affectedApis.map(a => `
        <div class="impact-api-card" style="margin-bottom: 6px;">
          <span class="method API" style="font-size: 10px; padding: 2px 6px;">API</span>
          <strong style="font-size: 12.5px; color: #f1f5f9;">${escapeHtml(a)}</strong>
        </div>
      `).join("")}
    `;
  }
  if (transitiveDependents.length) {
    apisAndTransitiveHtml += `
      <div style="margin: 12px 0 8px 0;">
        <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Transitive Dependents (2-Hop):</span>
      </div>
      ${transitiveDependents.slice(0, 6).map(t => `
        <div class="impact-caller-card" onclick="focusImpact('${escapeHtml(t.id)}')">
          <div class="caller-card-top">
            <span class="caller-name">${escapeHtml(t.name || t.id)}</span>
            <span class="caller-rel-tag" style="background: rgba(139,92,246,0.18); color: #c084fc;">2-HOP</span>
          </div>
          <div class="caller-file">${escapeHtml(t.file || "")}</div>
        </div>
      `).join("")}
    `;
  }
  if (!affectedApis.length && !transitiveDependents.length) {
    apisAndTransitiveHtml = `<div class="empty-hint" style="padding: 14px 0; font-size: 12px;">No downstream API routes or 2-hop consumers impacted.</div>`;
  }

  // Recommendations guidance HTML
  const recs = item.recommendations || [];
  let guidanceHtml = "";
  if (risk === "High") {
    guidanceHtml += `
      <div class="impact-guidance-card alert-high">
        <div class="guidance-icon danger">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
        </div>
        <div><strong>High Blast Radius:</strong> Changes here cascade across multiple architectural boundaries. Plan a phased migration or review breaking API contracts.</div>
      </div>
    `;
  }
  if (affectedTests.length) {
    guidanceHtml += `
      <div class="impact-guidance-card">
        <div class="guidance-icon success">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 2v7.31L4.89 20a2 2 0 0 0 1.66 3h14.9a2 2 0 0 0 1.66-3L18 9.31V2"></path><line x1="8.5" y1="2" x2="15.5" y2="2"></line><line x1="7" y1="15" x2="17" y2="15"></line></svg>
        </div>
        <div><strong>Recommended Tests:</strong> Run test suites in <code>${affectedTests.slice(0, 3).map(escapeHtml).join(", ")}</code> before deploying.</div>
      </div>
    `;
  } else {
    guidanceHtml += `
      <div class="impact-guidance-card alert-warning">
        <div class="guidance-icon warning">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
        </div>
        <div><strong>Test Coverage Gap:</strong> No automated test files directly cover this dependency chain. Add regression tests prior to modification.</div>
      </div>
    `;
  }
  for (const r of recs) {
    guidanceHtml += `
      <div class="impact-guidance-card">
        <div class="guidance-icon info">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        </div>
        <div>${escapeHtml(r)}</div>
      </div>
    `;
  }

  layout.innerHTML = `
    <!-- Hero Card -->
    <div class="impact-hero-card">
      <div class="impact-hero-left">
        <div class="impact-target-title-row">
          <h2 class="impact-target-title">${escapeHtml(targetLabel)}</h2>
          <span class="impact-kind-badge">${escapeHtml(kind)}</span>
        </div>
        ${
          filePath
            ? `<span class="impact-file-link" onclick="previewFile('${escapeHtml(filePath)}')">
                 <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                 <span>${escapeHtml(filePath)}${lineInfo}</span>
               </span>`
            : ""
        }
      </div>

      <div class="impact-hero-right">
        <div class="impact-risk-gauge-row">
          <span class="risk-badge risk-${risk}"><span class="risk-indicator-dot"></span>${risk} Risk</span>
          <div class="blast-gauge-box">
            <div class="blast-gauge-bar">
              <div class="blast-gauge-fill" style="width: ${blastScore}%; background: ${blastGaugeColor};"></div>
            </div>
            <span class="blast-gauge-label">Blast Radius: ${blastScore}%</span>
          </div>
        </div>

        <div class="impact-hero-actions">
          <button type="button" class="btn-impact-action btn-graph" onclick="jumpToGraphNode('${escapeHtml(id)}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <span>View in Graph</span>
          </button>
          <button type="button" class="btn-impact-action btn-ask" onclick="askAiImpact('${escapeHtml(targetLabel)}', '${escapeHtml(filePath)}', ${affectedFiles.length}, ${affectedApis.length})">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
            <span>Ask AI Blast Radius</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 4 Stats Cards -->
    <div class="impact-stats-grid">
      <div class="impact-stat-card">
        <div class="impact-stat-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
        </div>
        <div class="impact-stat-info">
          <span class="impact-stat-val">${affectedFiles.length}</span>
          <span class="impact-stat-lbl">Downstream Files</span>
        </div>
      </div>
      <div class="impact-stat-card">
        <div class="impact-stat-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>
        </div>
        <div class="impact-stat-info">
          <span class="impact-stat-val">${directDependents.length || (affectedFiles.length > 0 ? 1 : 0)}</span>
          <span class="impact-stat-lbl">1-Hop Direct Callers</span>
        </div>
      </div>
      <div class="impact-stat-card">
        <div class="impact-stat-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
        </div>
        <div class="impact-stat-info">
          <span class="impact-stat-val">${affectedApis.length}</span>
          <span class="impact-stat-lbl">Exposed APIs Impacted</span>
        </div>
      </div>
      <div class="impact-stat-card">
        <div class="impact-stat-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
        </div>
        <div class="impact-stat-info">
          <span class="impact-stat-val">${affectedTests.length}</span>
          <span class="impact-stat-lbl">Affected Test Suites</span>
        </div>
      </div>
    </div>

    <!-- 3-Column Drilldown -->
    <div class="impact-drilldown-grid">
      <div class="impact-column-panel">
        <div class="impact-column-header">
          <span class="impact-col-title">Direct Callers (1-Hop)</span>
          <span class="impact-col-count">${directDependents.length || affectedFiles.length}</span>
        </div>
        <div class="impact-items-list">${directHtml}</div>
      </div>

      <div class="impact-column-panel">
        <div class="impact-column-header">
          <span class="impact-col-title">APIs &amp; Transitive (2-Hop)</span>
          <span class="impact-col-count">${affectedApis.length + transitiveDependents.length}</span>
        </div>
        <div class="impact-items-list">${apisAndTransitiveHtml}</div>
      </div>

      <div class="impact-column-panel">
        <div class="impact-column-header">
          <span class="impact-col-title">Pre-Merge Risk Guidance</span>
          <span class="impact-col-count">Checklist</span>
        </div>
        <div class="impact-items-list">${guidanceHtml}</div>
      </div>
    </div>
  `;
}

// PROGRESSIVE GRAPH ENGINE
function prepareGraph() {
  if (!analysis) return;

  // Index all nodes by ID
  graphState.nodesById = new Map();
  (analysis.nodes || []).forEach((node) => {
    graphState.nodesById.set(node.id, node);
  });

  // Index hierarchy and dependencies
  graphState.childrenByParent = new Map();
  graphState.parentByChild = new Map();
  graphState.incomingRels = new Map();
  graphState.outgoingRels = new Map();

  (analysis.relationships || []).forEach((rel) => {
    if (rel.type === "CONTAINS") {
      if (!graphState.childrenByParent.has(rel.source)) {
        graphState.childrenByParent.set(rel.source, []);
      }
      graphState.childrenByParent.get(rel.source).push(rel.target);
      graphState.parentByChild.set(rel.target, rel.source);
    } else {
      // Outgoing
      if (!graphState.outgoingRels.has(rel.source)) {
        graphState.outgoingRels.set(rel.source, []);
      }
      graphState.outgoingRels.get(rel.source).push(rel);

      // Incoming
      if (!graphState.incomingRels.has(rel.target)) {
        graphState.incomingRels.set(rel.target, []);
      }
      graphState.incomingRels.get(rel.target).push(rel);
    }
  });

  // Initial state: Level 1 - Repository Root expanded only
  const rootId = "repo:root";
  graphState.expanded = new Set(graphState.nodesById.has(rootId) ? [rootId] : []);
  if (!graphState.expanded.size && analysis.nodes?.[0]) {
    graphState.expanded.add(analysis.nodes[0].id);
  }

  graphState.selected = null;
  graphState.filter = "all";
  graphState.query = "";
  graphState.toggles = {
    hierarchy: true,
    incoming: true,
    outgoing: true,
  };

  updateVisibleGraph();
  fitGraphToScreen();
}

function updateVisibleGraph() {
  const visibleIdSet = new Set();
  const rootId = "repo:root";

  // Root node is always visible
  if (graphState.nodesById.has(rootId)) {
    visibleIdSet.add(rootId);
  } else if (analysis?.nodes?.[0]) {
    visibleIdSet.add(analysis.nodes[0].id);
  }

  // Add immediate children of all expanded nodes
  graphState.expanded.forEach((parentId) => {
    const children = graphState.childrenByParent.get(parentId) || [];
    children.forEach((childId) => {
      if (graphState.nodesById.has(childId)) {
        visibleIdSet.add(childId);
      }
    });
  });

  // If a node is selected, include its immediate incoming & outgoing connections
  if (graphState.selected && graphState.nodesById.has(graphState.selected)) {
    const selId = graphState.selected;
    visibleIdSet.add(selId);

    if (graphState.toggles.incoming) {
      const inc = (graphState.incomingRels.get(selId) || []).slice(0, 15);
      inc.forEach((r) => {
        if (graphState.nodesById.has(r.source)) visibleIdSet.add(r.source);
      });
    }

    if (graphState.toggles.outgoing) {
      const out = (graphState.outgoingRels.get(selId) || []).slice(0, 15);
      out.forEach((r) => {
        if (graphState.nodesById.has(r.target)) visibleIdSet.add(r.target);
      });
    }
  }

  // Filter nodes by type if selected
  let visibleNodes = Array.from(visibleIdSet)
    .map((id) => graphState.nodesById.get(id))
    .filter(Boolean);

  if (graphState.filter !== "all") {
    visibleNodes = visibleNodes.filter(
      (n) =>
        n.type === "Repository" ||
        n.type === graphState.filter ||
        graphState.expanded.has(n.id) ||
        n.id === graphState.selected
    );
  }

  const finalVisibleIdSet = new Set(visibleNodes.map((n) => n.id));
  graphState.nodes = visibleNodes;

  // Determine active visible edges
  const activeEdges = [];
  (analysis.relationships || []).forEach((rel) => {
    if (!finalVisibleIdSet.has(rel.source) || !finalVisibleIdSet.has(rel.target)) return;

    if (rel.type === "CONTAINS") {
      if (graphState.toggles.hierarchy && graphState.expanded.has(rel.source)) {
        activeEdges.push(rel);
      }
    } else {
      const isInc = rel.target === graphState.selected;
      const isOut = rel.source === graphState.selected;

      if (graphState.selected) {
        if (isInc && graphState.toggles.incoming) activeEdges.push(rel);
        if (isOut && graphState.toggles.outgoing) activeEdges.push(rel);
      } else {
        if (graphState.toggles.incoming || graphState.toggles.outgoing) activeEdges.push(rel);
      }
    }
  });

  graphState.edges = activeEdges;

  updateLevelIndicator();
  layoutGraph();
  drawGraph();
}

function updateLevelIndicator() {
  const badge = document.getElementById("graphLevelIndicator");
  if (!badge) return;

  const types = new Set(graphState.nodes.map((n) => n.type));
  let levelText = "Level 1: Repository Overview";
  if (types.has("Function") || types.has("Method") || types.has("API")) {
    levelText = "Level 4: Entity & Dependency Trace";
  } else if (types.has("Class")) {
    levelText = "Level 3: Classes & Symbols";
  } else if (types.has("File")) {
    levelText = "Level 3: Files & Structure";
  } else if (graphState.expanded.size > 1) {
    levelText = "Level 2: Directory Architecture";
  }
  badge.textContent = `${levelText} (${graphState.nodes.length} nodes)`;
}

function layoutGraph() {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const height = rect.height || 680;

  // Assign column (level) based on hierarchy depth from repo:root
  const depthMap = new Map();
  depthMap.set("repo:root", 0);

  // BFS down from root along childrenByParent
  const queue = ["repo:root"];
  while (queue.length > 0) {
    const parentId = queue.shift();
    const pDepth = depthMap.get(parentId) || 0;
    const children = graphState.childrenByParent.get(parentId) || [];
    children.forEach((childId) => {
      if (!depthMap.has(childId)) {
        depthMap.set(childId, pDepth + 1);
        queue.push(childId);
      }
    });
  }

  // For any nodes not reachable through CONTAINS (e.g. caller/callee neighbors or external deps)
  graphState.nodes.forEach((node) => {
    if (!depthMap.has(node.id)) {
      if (node.type === "Repository") depthMap.set(node.id, 0);
      else if (node.type === "Directory") depthMap.set(node.id, 1);
      else if (node.type === "File") depthMap.set(node.id, 2);
      else if (node.type === "Class") depthMap.set(node.id, 3);
      else if (node.type === "Function" || node.type === "Method") depthMap.set(node.id, 4);
      else depthMap.set(node.id, 4);
    }
  });

  // Group nodes by column
  const columns = new Map();
  graphState.nodes.forEach((node) => {
    let col = depthMap.get(node.id) ?? 2;
    if (!columns.has(col)) columns.set(col, []);
    columns.get(col).push(node);
  });

  const sortedColKeys = Array.from(columns.keys()).sort((a, b) => a - b);
  graphState.positions = new Map();

  const colSpacing = 280;
  const nodeSpacing = 72;
  const startX = 140;

  sortedColKeys.forEach((colKey, colIdx) => {
    const nodesInCol = columns.get(colKey);
    // Sort nodes in column alphabetically for visual stability
    nodesInCol.sort((a, b) => (a.label || "").localeCompare(b.label || ""));

    const colHeight = (nodesInCol.length - 1) * nodeSpacing;
    const startY = Math.max(80, (height - colHeight) / 2);
    const x = startX + colIdx * colSpacing;

    nodesInCol.forEach((node, rowIdx) => {
      const y = startY + rowIdx * nodeSpacing;
      graphState.positions.set(node.id, { x, y, col: colIdx });
    });
  });
}

function fitGraphToScreen() {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const width = rect.width || 1200;
  const height = rect.height || 680;

  if (graphState.nodes.length === 0) {
    graphState.scale = 1;
    graphState.panX = 0;
    graphState.panY = 0;
    drawGraph();
    return;
  }

  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  graphState.nodes.forEach((n) => {
    const pos = graphState.positions.get(n.id);
    if (!pos) return;
    minX = Math.min(minX, pos.x);
    maxX = Math.max(maxX, pos.x);
    minY = Math.min(minY, pos.y);
    maxY = Math.max(maxY, pos.y);
  });

  const graphW = Math.max(100, maxX - minX + 280);
  const graphH = Math.max(100, maxY - minY + 160);

  const scaleX = (width - 140) / graphW;
  const scaleY = (height - 120) / graphH;
  const fitScale = Math.min(1.2, Math.max(0.45, Math.min(scaleX, scaleY)));

  const midX = (minX + maxX) / 2;
  const midY = (minY + maxY) / 2;

  graphState.scale = fitScale;
  graphState.panX = width / 2 - midX * fitScale;
  graphState.panY = height / 2 - midY * fitScale;

  drawGraph();
}

function drawGraph() {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;

  if (canvas.width !== Math.floor(rect.width * ratio) || canvas.height !== Math.floor(rect.height * ratio)) {
    canvas.width = Math.floor(rect.width * ratio);
    canvas.height = Math.floor(rect.height * ratio);
    layoutGraph();
  }

  ctx.save();
  ctx.scale(ratio, ratio);
  const width = rect.width;
  const height = rect.height;

  ctx.clearRect(0, 0, width, height);

  // Subtle background dot grid
  ctx.save();
  ctx.fillStyle = "rgba(148, 163, 184, 0.08)";
  const gridSize = 32 * graphState.scale;
  const offsetX = (graphState.panX % gridSize + gridSize) % gridSize;
  const offsetY = (graphState.panY % gridSize + gridSize) % gridSize;
  for (let gx = offsetX; gx < width; gx += gridSize) {
    for (let gy = offsetY; gy < height; gy += gridSize) {
      ctx.beginPath();
      ctx.arc(gx, gy, 1, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.restore();

  // Apply pan and zoom
  ctx.translate(graphState.panX, graphState.panY);
  ctx.scale(graphState.scale, graphState.scale);

  const selectedId = graphState.selected;
  const incomingSet = new Set(
    selectedId ? (graphState.incomingRels.get(selectedId) || []).map((r) => r.source) : []
  );
  const outgoingSet = new Set(
    selectedId ? (graphState.outgoingRels.get(selectedId) || []).map((r) => r.target) : []
  );

  // Draw Edges
  graphState.edges.forEach((edge) => {
    const a = graphState.positions.get(edge.source);
    const b = graphState.positions.get(edge.target);
    if (!a || !b) return;

    const isConnectedToSelected = selectedId && (edge.source === selectedId || edge.target === selectedId);
    const isHierarchy = edge.type === "CONTAINS";

    ctx.save();

    if (selectedId) {
      ctx.globalAlpha = isConnectedToSelected ? 1.0 : 0.08;
    } else {
      ctx.globalAlpha = isHierarchy ? 0.4 : 0.6;
    }

    if (edge.target === selectedId) {
      // Inward connection to selected (Emerald)
      ctx.strokeStyle = "#34d399";
      ctx.lineWidth = 2.4;
      ctx.setLineDash([]);
    } else if (edge.source === selectedId) {
      // Outward connection from selected (Cyan)
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2.4;
      ctx.setLineDash([]);
    } else if (isHierarchy) {
      ctx.strokeStyle = "rgba(148, 163, 184, 0.35)";
      ctx.lineWidth = 1.4;
      ctx.setLineDash([4, 4]);
    } else {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.35)";
      ctx.lineWidth = 1.4;
      ctx.setLineDash([]);
    }

    // Smooth Bezier Curve
    const dx = Math.abs(b.x - a.x) * 0.55;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.bezierCurveTo(a.x + dx, a.y, b.x - dx, b.y, b.x, b.y);
    ctx.stroke();

    // Directional Arrowhead for non-hierarchy dependencies
    if (!isHierarchy) {
      const t = 0.85; // position near target
      const arrowX = (1 - t) * (1 - t) * a.x + 2 * (1 - t) * t * (a.x + dx) + t * t * b.x;
      const arrowY = (1 - t) * (1 - t) * a.y + 2 * (1 - t) * t * a.y + t * t * b.y;
      const angle = Math.atan2(b.y - a.y, b.x - a.x);

      ctx.save();
      ctx.translate(arrowX, arrowY);
      ctx.rotate(angle);
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(-8, -4);
      ctx.lineTo(-8, 4);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    ctx.restore();
  });

  // Draw Nodes
  graphState.nodes.forEach((node) => {
    const pos = graphState.positions.get(node.id);
    if (!pos) return;

    const isSelected = selectedId === node.id;
    const isIncoming = incomingSet.has(node.id);
    const isOutgoing = outgoingSet.has(node.id);
    const isExpanded = graphState.expanded.has(node.id);
    const hasChildren = (graphState.childrenByParent.get(node.id) || []).length > 0;

    ctx.save();

    // Contextual Dimming
    if (selectedId) {
      const isRelevant = isSelected || isIncoming || isOutgoing;
      ctx.globalAlpha = isRelevant ? 1.0 : 0.18;
    } else {
      ctx.globalAlpha = 1.0;
    }

    // Node Radius
    const radius = node.type === "Repository" ? 18 : node.type === "Directory" ? 14 : node.type === "File" ? 11 : 8;
    const baseColor = typeColors[node.type] || "#94a3b8";

    // Glow Effect for Selected or Connected Nodes
    if (isSelected) {
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 18;
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius + 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    } else if (isIncoming) {
      ctx.shadowColor = "#34d399";
      ctx.shadowBlur = 12;
      ctx.strokeStyle = "#34d399";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius + 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    } else if (isOutgoing) {
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 12;
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius + 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Core Node Circle
    ctx.fillStyle = baseColor;
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
    ctx.fill();

    // Inner icon / dot
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, Math.max(2.5, radius * 0.35), 0, Math.PI * 2);
    ctx.fill();

    // Expandable indicator badge [+] / [-]
    if (hasChildren) {
      const badgeX = pos.x + radius * 0.7;
      const badgeY = pos.y - radius * 0.7;
      ctx.fillStyle = isExpanded ? "#f43f5e" : "#10b981";
      ctx.beginPath();
      ctx.arc(badgeX, badgeY, 6, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 9px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(isExpanded ? "−" : "+", badgeX, badgeY);
    }

    // Text Label with dark halo pill
    const labelText = truncate(node.label, 24);
    ctx.font = isSelected ? "bold 12px Plus Jakarta Sans, sans-serif" : "11px Plus Jakarta Sans, sans-serif";
    const textWidth = ctx.measureText(labelText).width;
    const textX = pos.x + radius + 8;
    const textY = pos.y + 4;

    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
    ctx.beginPath();
    ctx.roundRect(textX - 4, textY - 12, textWidth + 8, 16, 4);
    ctx.fill();

    ctx.fillStyle = isSelected ? "#ffffff" : isIncoming ? "#6ee7b7" : isOutgoing ? "#7dd3fc" : "#e2e8f0";
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(labelText, textX, textY);

    ctx.restore();
  });

  ctx.restore();
}

function selectNodeFromCanvas(event) {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const rawX = event.clientX - rect.left;
  const rawY = event.clientY - rect.top;

  // Convert to zoomed and panned coordinates
  const x = (rawX - graphState.panX) / graphState.scale;
  const y = (rawY - graphState.panY) / graphState.scale;

  let clickedNode = null;
  let bestDist = Infinity;

  graphState.nodes.forEach((node) => {
    const pos = graphState.positions.get(node.id);
    if (!pos) return;
    const radius = node.type === "Repository" ? 22 : node.type === "Directory" ? 18 : 14;
    const dist = Math.hypot(pos.x - x, pos.y - y);
    if (dist < radius + 8 && dist < bestDist) {
      clickedNode = node;
      bestDist = dist;
    }
  });

  if (clickedNode) {
    // If clicking Directory or File, toggle expansion on single click for fluid browsing
    const hasChildren = (graphState.childrenByParent.get(clickedNode.id) || []).length > 0;
    if (hasChildren && (clickedNode.type === "Directory" || clickedNode.type === "File")) {
      toggleNodeExpansion(clickedNode.id);
    } else {
      selectNode(clickedNode.id);
    }
  } else {
    // Clicked empty background: clear selection
    graphState.selected = null;
    updateVisibleGraph();
    renderInspectorEmpty();
  }
}

function selectNode(nodeId) {
  graphState.selected = nodeId;
  const node = graphState.nodesById.get(nodeId);
  if (!node) return;

  updateVisibleGraph();
  renderNodeInspector(node);
}

function toggleNodeExpansion(nodeId) {
  if (graphState.expanded.has(nodeId)) {
    // Collapse: remove this node and all of its descendants
    collapseDescendants(nodeId);
    graphState.expanded.delete(nodeId);
  } else {
    // Expand
    graphState.expanded.add(nodeId);
  }

  graphState.selected = nodeId;
  const node = graphState.nodesById.get(nodeId);
  updateVisibleGraph();
  if (node) renderNodeInspector(node);
}

function collapseDescendants(parentId) {
  const children = graphState.childrenByParent.get(parentId) || [];
  children.forEach((childId) => {
    graphState.expanded.delete(childId);
    collapseDescendants(childId);
  });
}

function jumpToNode(nodeId) {
  if (!graphState.nodesById.has(nodeId)) return;

  // Trace ancestors up to root and expand all of them
  let curr = nodeId;
  while (curr) {
    const parent = graphState.parentByChild.get(curr);
    if (parent) {
      graphState.expanded.add(parent);
      curr = parent;
    } else {
      break;
    }
  }

  graphState.selected = nodeId;
  updateVisibleGraph();

  // Smoothly center canvas on target node
  const canvas = document.getElementById("graphCanvas");
  if (canvas) {
    const pos = graphState.positions.get(nodeId);
    if (pos) {
      const rect = canvas.getBoundingClientRect();
      const targetScale = Math.max(graphState.scale, 0.9);
      graphState.scale = targetScale;
      graphState.panX = rect.width / 2 - pos.x * targetScale;
      graphState.panY = rect.height / 2 - pos.y * targetScale;
      drawGraph();
    }
  }

  const node = graphState.nodesById.get(nodeId);
  if (node) renderNodeInspector(node);
}

function renderInspectorEmpty() {
  const inspector = document.getElementById("nodeInspector");
  if (!inspector) return;
  inspector.innerHTML = `
    <div class="inspector-placeholder">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
      <p>Click any node in the graph to inspect details, incoming calls, and dependencies.</p>
    </div>
  `;
}

async function renderNodeInspector(node) {
  const inspector = document.getElementById("nodeInspector");
  if (!inspector) return;

  const incoming = graphState.incomingRels.get(node.id) || [];
  const outgoing = graphState.outgoingRels.get(node.id) || [];
  const children = graphState.childrenByParent.get(node.id) || [];
  const isExpanded = graphState.expanded.has(node.id);
  const hasChildren = children.length > 0;

  const incomingHtml = incoming.length
    ? incoming
        .slice(0, 15)
        .map((r) => {
          const srcNode = graphState.nodesById.get(r.source);
          const lbl = srcNode ? srcNode.label : r.source;
          return `
            <div class="inspector-dep-item" onclick="jumpToNode('${escapeHtml(r.source)}')">
              <span class="inspector-dep-target">← ${escapeHtml(lbl)}</span>
              <span class="inspector-dep-rel">${escapeHtml(r.type)}</span>
            </div>
          `;
        })
        .join("")
    : `<div class="empty-hint" style="padding: 4px 0; font-size: 11px;">No incoming callers detected</div>`;

  const outgoingHtml = outgoing.length
    ? outgoing
        .slice(0, 15)
        .map((r) => {
          const tgtNode = graphState.nodesById.get(r.target);
          const lbl = tgtNode ? tgtNode.label : r.target;
          return `
            <div class="inspector-dep-item" onclick="jumpToNode('${escapeHtml(r.target)}')">
              <span class="inspector-dep-target">→ ${escapeHtml(lbl)}</span>
              <span class="inspector-dep-rel">${escapeHtml(r.type)}</span>
            </div>
          `;
        })
        .join("")
    : `<div class="empty-hint" style="padding: 4px 0; font-size: 11px;">No outgoing dependencies</div>`;

  inspector.innerHTML = `
    <div class="inspector-header">
      <div class="inspector-title-row">
        <span class="inspector-node-name">${escapeHtml(node.label)}</span>
      </div>
      <div class="inspector-badges">
        <span class="method ${escapeHtml(node.type)}" style="background: rgba(56,189,248,0.18); color: #38bdf8; font-size: 10.5px;">${escapeHtml(node.type)}</span>
        ${node.line ? `<span style="font-size: 11px; color: var(--text-faint);">Line ${node.line}</span>` : ""}
      </div>
      ${node.path ? `<div class="inspector-path">${escapeHtml(node.path)}</div>` : ""}
    </div>

    <div class="inspector-stats-row">
      <div class="inspector-stat-item">
        <span class="stat-num">${incoming.length}</span>
        <span class="stat-lbl">Inward</span>
      </div>
      <div class="inspector-stat-item">
        <span class="stat-num">${outgoing.length}</span>
        <span class="stat-lbl">Outward</span>
      </div>
      <div class="inspector-stat-item">
        <span class="stat-num">${children.length}</span>
        <span class="stat-lbl">Children</span>
      </div>
    </div>

    <div class="inspector-actions-row">
      ${
        hasChildren
          ? `<button type="button" class="btn-inspector-primary" onclick="toggleNodeExpansion('${escapeHtml(node.id)}')">
              ${isExpanded ? "Collapse Children" : "Expand Children"}
             </button>`
          : ""
      }
      <button type="button" class="btn-inspector-secondary" onclick="focusImpact('${escapeHtml(node.id)}')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
        <span>Impact</span>
      </button>
      <button type="button" class="btn-inspector-secondary" onclick="askAboutNode('${escapeHtml(node.label)}')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        <span>Ask AI</span>
      </button>
    </div>

    <div class="inspector-section">
      <div class="inspector-section-title">
        <span>Incoming Callers (${incoming.length})</span>
      </div>
      <div class="inspector-dep-list">${incomingHtml}</div>
    </div>

    <div class="inspector-section">
      <div class="inspector-section-title">
        <span>Outgoing Calls & Imports (${outgoing.length})</span>
      </div>
      <div class="inspector-dep-list">${outgoingHtml}</div>
    </div>

    <div class="inspector-section" id="inspectorCodeSection">
      <div class="inspector-section-title">
        <span>Source Preview</span>
      </div>
      <div class="inspector-code-box" id="inspectorCodeBox">Loading source preview...</div>
    </div>
  `;

  // Fetch code preview if node has a path
  if (node.path) {
    loadNodeCodePreview(node);
  } else {
    const box = document.getElementById("inspectorCodeBox");
    if (box) box.textContent = "(No source file associated)";
  }
}

async function loadNodeCodePreview(node) {
  const box = document.getElementById("inspectorCodeBox");
  if (!box) return;
  try {
    const res = await fetch(`/api/file?path=${encodeURIComponent(node.path)}`);
    const data = await res.json();
    if (!res.ok || !data.content) {
      box.textContent = "(Could not load file source)";
      return;
    }

    const lines = data.content.split("\n");
    const targetLine = node.line || 1;
    const start = Math.max(1, targetLine - 4);
    const end = Math.min(lines.length, targetLine + 20);

    const snippet = lines
      .slice(start - 1, end)
      .map((line, idx) => {
        const lineNum = start + idx;
        const isTarget = lineNum === targetLine;
        const prefix = isTarget ? "▶ " : "  ";
        return `${prefix}${String(lineNum).padStart(3, " ")} | ${line}`;
      })
      .join("\n");

    box.textContent = snippet;
  } catch (err) {
    box.textContent = `(Error: ${err.message})`;
  }
}

function focusImpact(nodeId) {
  const impactTab = document.querySelector('.tab[data-view="impact"]');
  if (impactTab) impactTab.click();
  renderImpact(nodeId);
}

function askAiImpact(label, file, filesCount, apisCount) {
  const overviewTab = document.querySelector('.tab[data-view="overview"]');
  if (overviewTab) overviewTab.click();
  const input = document.getElementById("questionInput");
  if (input) {
    input.value = `Analyze the change impact of modifying "${label}" in "${file}". What are the potential breaking changes for the ${filesCount} downstream files and ${apisCount} API routes?`;
    document.getElementById("btnAsk").click();
  }
}

function jumpToGraphNode(nodeId) {
  const graphTab = document.querySelector('.tab[data-view="explorer"]');
  if (graphTab) graphTab.click();
  jumpToNode(nodeId);
}

function askAboutNode(label) {
  const overviewTab = document.querySelector('.tab[data-view="overview"]');
  if (overviewTab) overviewTab.click();
  const input = document.getElementById("questionInput");
  if (input) {
    input.value = `Explain what ${label} does and how it is used in this codebase.`;
    document.getElementById("btnAsk").click();
  }
}

// FILE EXPLORER & VIEWER
let repoFilesList = [];
let currentPreviewedPath = "";

async function loadFilesTree() {
  try {
    const res = await fetch("/api/filetree");
    const data = await res.json();
    repoFilesList = data.files || [];
    renderFilteredFiles();
  } catch (err) {
    console.error("Could not load file tree:", err);
  }
}

function renderFilteredFiles(filterQuery = "") {
  const listEl = document.getElementById("fileTreeList");
  const badgeEl = document.getElementById("fileCountBadge");
  if (!listEl) return;

  const query = (filterQuery || "").trim().toLowerCase();
  const matched = query
    ? repoFilesList.filter((f) => f.toLowerCase().includes(query))
    : repoFilesList;

  if (badgeEl) {
    badgeEl.textContent = query
      ? `${matched.length} of ${repoFilesList.length}`
      : `${repoFilesList.length} files`;
  }

  if (!matched.length) {
    listEl.innerHTML = `<div class="empty-hint" style="padding: 20px; text-align: center;">No files match "${escapeHtml(query)}"</div>`;
    return;
  }

  listEl.innerHTML = matched
    .map((filePath) => {
      const parts = filePath.split("/");
      const fileName = parts.pop();
      const dirPath = parts.join("/");
      const ext = fileName.includes(".") ? fileName.split(".").pop().toLowerCase() : "file";
      const isActive = currentPreviewedPath === filePath;
      return `
        <div class="tree-item ${isActive ? "active" : ""}" data-path="${escapeHtml(filePath)}" onclick="previewFile('${escapeHtml(filePath)}')">
          <span class="file-ext-tag ext-${escapeHtml(ext)}">${escapeHtml(ext.slice(0, 4))}</span>
          <div class="tree-item-info">
            <span class="tree-item-name">${escapeHtml(fileName)}</span>
            ${dirPath ? `<span class="tree-item-dir">${escapeHtml(dirPath)}</span>` : ""}
          </div>
        </div>
      `;
    })
    .join("");
}

async function previewFile(filePath) {
  try {
    currentPreviewedPath = filePath;
    // Switch to files view if not already there
    const filesTab = document.querySelector('.tab[data-view="files"]');
    if (filesTab && !filesTab.classList.contains("active")) {
      filesTab.click();
    }

    document.querySelectorAll(".tree-item").forEach((el) => {
      if (el.dataset.path === filePath) {
        el.classList.add("active");
        el.scrollIntoView({ block: "nearest", behavior: "smooth" });
      } else {
        el.classList.remove("active");
      }
    });

    const res = await fetch(`/api/file?path=${encodeURIComponent(filePath)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    document.getElementById("codeViewerPath").textContent = data.path;
    document.getElementById("codeViewerLines").textContent = `${data.lines} lines`;
    document.getElementById("codeContent").textContent = data.content;
  } catch (err) {
    document.getElementById("codeViewerPath").textContent = filePath;
    document.getElementById("codeContent").textContent = `Error loading file: ${err.message}`;
  }
}

// ASSISTANT CHAT
async function askServer(question) {
  const input = document.getElementById("questionInput");
  question = (question || "").trim();
  if (!question) return;

  appendChatEntry("you", question, null);
  input.value = "";

  const thinkingId = appendChatEntry("codecompass", "Analyzing repository context...", { isThinking: true });

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, conversation_id: conversationId, repo_id: currentRepoId }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Ask failed");

    conversationId = payload.conversation_id || conversationId;
    updateChatEntry(thinkingId, payload.answer || "No answer.", payload);
  } catch (error) {
    updateChatEntry(thinkingId, `(Request failed: ${error.message})`, { mode: "error" });
  }
}

let chatMsgCounter = 0;

function copyCodeSnippet(btn) {
  const pre = btn.closest(".ai-code-card")?.querySelector("pre code");
  if (!pre) return;
  const text = pre.innerText || pre.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.innerHTML;
    btn.innerHTML = `<span>✓ Copied</span>`;
    setTimeout(() => { btn.innerHTML = orig; }, 1800);
  });
}

function copyFullAnswer(btn) {
  const entry = btn.closest(".chat-entry");
  if (!entry) return;
  const textEl = entry.querySelector(".chat-text");
  if (!textEl) return;
  const text = textEl.innerText || textEl.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.innerHTML;
    btn.innerHTML = `<span>✓ Copied Answer</span>`;
    setTimeout(() => { btn.innerHTML = orig; }, 1800);
  });
}

function appendChatEntry(role, text, payload) {
  const log = document.getElementById("chatLog");
  if (!log) return "";
  chatMsgCounter++;
  const entryId = `chat-msg-${chatMsgCounter}`;

  const entry = document.createElement("div");
  entry.id = entryId;
  entry.className = `chat-entry chat-${role}`;

  if (role === "you") {
    entry.innerHTML = `
      <div class="chat-entry-header">
        <div class="chat-sender-info">
          <div class="chat-avatar-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
          </div>
          <span class="chat-role">You</span>
        </div>
      </div>
      <div class="chat-text">${escapeHtml(text)}</div>
    `;
  } else {
    const isThinking = payload?.isThinking;
    const badgeEl = document.getElementById("aiModelBadge");
    const activeModel = badgeEl ? badgeEl.textContent.trim() : "● Gemini 3.5 Flash Lite";

    entry.innerHTML = `
      <div class="chat-entry-header">
        <div class="chat-sender-info">
          <div class="chat-avatar-icon" style="background: rgba(16,185,129,0.18); color: #34d399;">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polygon points="12 8 8 12 12 16 16 12 12 8"></polygon></svg>
          </div>
          <span class="chat-role" style="color: #38bdf8;">CodeCompass AI</span>
          <span class="ai-status-badge ai-status-gemini" style="font-size: 10px; padding: 2px 7px;">${escapeHtml(activeModel)}</span>
        </div>
        ${!isThinking ? `<button type="button" class="btn-copy-answer" onclick="copyFullAnswer(this)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> <span>Copy</span></button>` : ""}
      </div>
      <div class="chat-text">
        ${
          isThinking
            ? `<div class="ai-thinking-shimmer">
                 <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                 <span>${escapeHtml(text)}</span>
               </div>`
            : formatMarkdown(text)
        }
      </div>
      ${renderSourcesChips(payload)}
    `;
  }

  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
  return entryId;
}

function updateChatEntry(entryId, text, payload) {
  const entry = document.getElementById(entryId);
  if (!entry) return;

  const header = entry.querySelector(".chat-entry-header");
  if (header && !header.querySelector(".btn-copy-answer")) {
    header.insertAdjacentHTML("beforeend", `<button type="button" class="btn-copy-answer" onclick="copyFullAnswer(this)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> <span>Copy</span></button>`);
  }

  const textEl = entry.querySelector(".chat-text");
  if (textEl) {
    textEl.innerHTML = formatMarkdown(text);
  }

  const chipsHtml = renderSourcesChips(payload);
  if (chipsHtml) {
    const existing = entry.querySelector(".answer-sources");
    if (existing) existing.remove();
    entry.insertAdjacentHTML("beforeend", chipsHtml);
  }

  const log = document.getElementById("chatLog");
  if (log) log.scrollTop = log.scrollHeight;
}

function renderSourcesChips(payload) {
  if (!payload) return "";
  const chips = (payload.sources || [])
    .slice(0, 6)
    .map(
      (s) => `
        <span class="source-chip" onclick="previewFile('${escapeHtml(s.file)}')">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
          <span>${escapeHtml(s.file)}:${s.start_line}</span>
        </span>
      `
    )
    .join("");
  const mode = payload.mode
    ? `<span class="answer-mode">${payload.mode === "llm" ? `AI (${escapeHtml(payload.model || "gemini")})` : escapeHtml(payload.mode)}</span>`
    : "";
  return chips || mode ? `<div class="answer-sources">${mode}${chips}</div>` : "";
}

function resetConversation() {
  const previous = conversationId;
  conversationId = null;
  const log = document.getElementById("chatLog");
  if (log) {
    log.innerHTML = `
      <div class="chat-entry chat-codecompass">
        <div class="chat-entry-header">
          <div class="chat-sender-info">
            <div class="chat-avatar-icon" style="background: rgba(16,185,129,0.18); color: #34d399;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polygon points="12 8 8 12 12 16 16 12 12 8"></polygon></svg>
            </div>
            <span class="chat-role" style="color: #38bdf8;">CodeCompass AI</span>
          </div>
        </div>
        <div class="chat-text">Ready to answer questions about <strong>${escapeHtml(analysis?.repository?.name || "this codebase")}</strong>. Ask anything or pick a suggested topic above.</div>
      </div>
    `;
  }
  if (previous) {
    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: previous, reset: true }),
    }).catch(() => {});
  }
}

// REPO IMPORT / SWITCH MODAL
function renderRepoHistoryModal() {
  const list = document.getElementById("repoHistoryList");
  if (!repositoriesList.length) {
    list.innerHTML = `<div class="empty-hint">No other repositories analyzed yet.</div>`;
    return;
  }
  list.innerHTML = repositoriesList
    .map(
      (r) => `
        <div class="repo-history-item ${r.id === currentRepoId ? "active" : ""}" onclick="selectRepository('${escapeHtml(r.id)}')">
          <div>
            <strong>${escapeHtml(r.name)}</strong>
            <span style="display:block; font-size:11px; color:var(--text-faint);">${escapeHtml(r.root_path)}</span>
          </div>
          <span class="repo-source-tag">${escapeHtml(r.source || "local")}</span>
        </div>
      `
    )
    .join("");
}

async function selectRepository(repoId) {
  closeImportModal();
  await fetch("/api/switch-repo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_id: repoId }),
  });
  await loadRepositories();
  await loadAnalysis(repoId);
}

function openImportModal() {
  document.getElementById("importModal").classList.add("open");
  renderRepoHistoryModal();
}

function closeImportModal() {
  document.getElementById("importModal").classList.remove("open");
  document.getElementById("importStatusText").textContent = "";
}

// EVENT LISTENERS
function setupEventListeners() {
  // Tabs Navigation
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.view).classList.add("active");
      const breadcrumbEl = document.getElementById("topbarViewBreadcrumb");
      if (breadcrumbEl) {
        const viewNames = {
          overview: "Overview",
          graph: "Dependency Graph",
          files: "File Explorer",
          apis: "API Map",
          flows: "Feature Flows",
          impact: "Impact Analysis",
          guide: "Onboarding Guide"
        };
        breadcrumbEl.textContent = viewNames[btn.dataset.view] || btn.dataset.view;
      }
      if (btn.dataset.view === "graph") requestAnimationFrame(drawGraph);
    });
  });

  // Graph filters
  document.querySelectorAll(".segment").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".segment").forEach((s) => s.classList.remove("active"));
      btn.classList.add("active");
      graphState.filter = btn.dataset.filter;
      updateVisibleGraph();
    });
  });

  // Search input & dropdown
  const searchInput = document.getElementById("graphSearch");
  const searchDropdown = document.getElementById("searchResultsDropdown");

  if (searchInput && searchDropdown) {
    searchInput.addEventListener("input", (e) => {
      const query = (e.target.value || "").trim().toLowerCase();
      if (!query || !analysis?.nodes) {
        searchDropdown.classList.remove("visible");
        searchDropdown.innerHTML = "";
        return;
      }

      const matches = analysis.nodes
        .filter((n) => {
          const matchLabel = (n.label || "").toLowerCase().includes(query);
          const matchPath = (n.path || "").toLowerCase().includes(query);
          return matchLabel || matchPath;
        })
        .slice(0, 10);

      if (!matches.length) {
        searchDropdown.innerHTML = `<div style="padding: 10px 14px; font-size: 12px; color: var(--text-faint);">No matching entities</div>`;
        searchDropdown.classList.add("visible");
        return;
      }

      searchDropdown.innerHTML = matches
        .map(
          (m) => `
          <div class="search-result-item" data-node-id="${escapeHtml(m.id)}">
            <div class="search-result-main">
              <span class="search-result-label">${escapeHtml(m.label)}</span>
              ${m.path ? `<span class="search-result-path">${escapeHtml(m.path)}${m.line ? `:${m.line}` : ""}</span>` : ""}
            </div>
            <span class="method ${escapeHtml(m.type)}" style="font-size: 10px; padding: 2px 6px;">${escapeHtml(m.type)}</span>
          </div>
        `
        )
        .join("");
      searchDropdown.classList.add("visible");
    });

    searchDropdown.addEventListener("click", (e) => {
      const item = e.target.closest(".search-result-item");
      if (item && item.dataset.nodeId) {
        const targetId = item.dataset.nodeId;
        jumpToNode(targetId);
        searchDropdown.classList.remove("visible");
        searchInput.value = "";
      }
    });

    document.addEventListener("click", (e) => {
      if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
        searchDropdown.classList.remove("visible");
      }
    });
  }

  // Edge Toggles
  const tHierarchy = document.getElementById("toggleHierarchy");
  const tIncoming = document.getElementById("toggleIncoming");
  const tOutgoing = document.getElementById("toggleOutgoing");

  if (tHierarchy) {
    tHierarchy.addEventListener("change", (e) => {
      graphState.toggles.hierarchy = e.target.checked;
      updateVisibleGraph();
    });
  }
  if (tIncoming) {
    tIncoming.addEventListener("change", (e) => {
      graphState.toggles.incoming = e.target.checked;
      updateVisibleGraph();
    });
  }
  if (tOutgoing) {
    tOutgoing.addEventListener("change", (e) => {
      graphState.toggles.outgoing = e.target.checked;
      updateVisibleGraph();
    });
  }

  // Overview Reset & Fit to screen
  const btnReset = document.getElementById("btnResetToOverview");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      const rootId = "repo:root";
      graphState.expanded = new Set(graphState.nodesById.has(rootId) ? [rootId] : []);
      if (!graphState.expanded.size && analysis.nodes?.[0]) {
        graphState.expanded.add(analysis.nodes[0].id);
      }
      graphState.selected = null;
      updateVisibleGraph();
      fitGraphToScreen();
      renderInspectorEmpty();
    });
  }

  const btnFit = document.getElementById("btnFitScreen");
  if (btnFit) {
    btnFit.addEventListener("click", fitGraphToScreen);
  }

  // Graph Canvas Pan and Zoom
  const canvas = document.getElementById("graphCanvas");
  canvas.addEventListener("click", selectNodeFromCanvas);
  canvas.addEventListener("dblclick", (e) => {
    // Double click can also toggle expansion
    selectNodeFromCanvas(e);
  });

  canvas.addEventListener("mousedown", (e) => {
    graphState.isDragging = true;
    graphState.dragStartX = e.clientX - graphState.panX;
    graphState.dragStartY = e.clientY - graphState.panY;
  });

  window.addEventListener("mousemove", (e) => {
    if (!graphState.isDragging) return;
    graphState.panX = e.clientX - graphState.dragStartX;
    graphState.panY = e.clientY - graphState.dragStartY;
    drawGraph();
  });

  window.addEventListener("mouseup", () => {
    graphState.isDragging = false;
  });

  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    graphState.scale = Math.max(0.3, Math.min(3.5, graphState.scale * zoomFactor));
    drawGraph();
  });

  document.getElementById("btnZoomIn").addEventListener("click", () => {
    graphState.scale = Math.min(3.5, graphState.scale * 1.2);
    drawGraph();
  });

  document.getElementById("btnZoomOut").addEventListener("click", () => {
    graphState.scale = Math.max(0.3, graphState.scale * 0.8);
    drawGraph();
  });

  document.getElementById("btnResetZoom").addEventListener("click", () => {
    graphState.scale = 1;
    graphState.panX = 0;
    graphState.panY = 0;
    drawGraph();
  });

  // Chat Form
  document.getElementById("questionForm").addEventListener("submit", (e) => {
    e.preventDefault();
    askServer(document.getElementById("questionInput").value);
  });

  document.getElementById("chatReset").addEventListener("click", resetConversation);

  // Suggested prompt chips
  document.querySelectorAll(".prompt-chips .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      askServer(chip.dataset.prompt);
    });
  });

  // Filter APIs
  document.getElementById("apiSearch").addEventListener("input", renderApis);

  // Impact selector & controls
  const impactSel = document.getElementById("impactSelect");
  if (impactSel) {
    impactSel.addEventListener("change", () => renderImpact());
  }

  const impactSearchInput = document.getElementById("impactSearchInput");
  if (impactSearchInput) {
    let timeoutId = null;
    impactSearchInput.addEventListener("input", (e) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        renderImpactSelector(null, e.target.value);
      }, 200);
    });
  }

  document.querySelectorAll("#impactFilterPills .impact-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#impactFilterPills .impact-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      renderImpactSelector(pill.dataset.filter, null);
    });
  });

  // Role Selector in Onboarding Guide
  document.querySelectorAll("#rolePills .role-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#rolePills .role-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      renderRoleOnboarding(pill.dataset.role);
    });
  });

  // Feature Flow Tracer Controls
  const flowSelect = document.getElementById("flowPresetSelect");
  if (flowSelect) {
    flowSelect.addEventListener("change", (e) => {
      if (e.target.value) {
        traceFeatureFlow(e.target.value, null);
      }
    });
  }

  const btnTrace = document.getElementById("btnTraceFlow");
  const flowInput = document.getElementById("flowQueryInput");
  if (btnTrace && flowInput) {
    btnTrace.addEventListener("click", () => {
      const q = (flowInput.value || "").trim();
      if (q) traceFeatureFlow(null, q);
    });
    flowInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const q = (flowInput.value || "").trim();
        if (q) traceFeatureFlow(null, q);
      }
    });
  }

  // Flow Diagram View Toggles
  document.querySelectorAll(".btn-flow-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-flow-toggle").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const mode = btn.dataset.flowMode;
      const timeline = document.getElementById("flowStepsTimeline");
      const diagram = document.getElementById("flowDiagramContainer");
      if (mode === "steps") {
        if (timeline) timeline.style.display = "flex";
        if (diagram) diagram.style.display = "none";
      } else {
        if (timeline) timeline.style.display = "none";
        if (diagram) diagram.style.display = "block";
      }
    });
  });

  // Modal open/close
  document.getElementById("btnOpenImportModal").addEventListener("click", openImportModal);
  document.getElementById("btnHeaderImport").addEventListener("click", openImportModal);
  document.getElementById("btnCloseImportModal").addEventListener("click", closeImportModal);

  // Modal import tabs (Local vs Github)
  document.querySelectorAll(".import-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".import-tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".import-tab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const tabId = btn.dataset.tab === "local" ? "tabLocal" : "tabGithub";
      document.getElementById(tabId).classList.add("active");
    });
  });

  // Import / Analyze Form submission
  document.getElementById("analyzeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const isLocal = document.querySelector('.import-tab-btn[data-tab="local"]').classList.contains("active");
    const targetPath = isLocal
      ? document.getElementById("localRepoPath").value.trim()
      : document.getElementById("githubRepoUrl").value.trim();

    if (!targetPath) {
      alert("Please enter a path or repository URL.");
      return;
    }

    const statusEl = document.getElementById("importStatusText");
    const submitBtn = document.getElementById("btnSubmitImport");
    submitBtn.disabled = true;
    submitBtn.textContent = "Analyzing...";
    statusEl.textContent = isLocal ? "Scanning local directory..." : "Cloning repository from GitHub...";

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: targetPath }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Analysis failed");

      closeImportModal();
      await loadRepositories();
      await loadAnalysis(data.repo_id);
    } catch (err) {
      statusEl.textContent = `Error: ${err.message}`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Analyze & Import</span>`;
    }
  });

  // File Explorer Search & Copy
  const fileFilterInput = document.getElementById("fileFilterInput");
  if (fileFilterInput) {
    fileFilterInput.addEventListener("input", (e) => {
      renderFilteredFiles(e.target.value);
    });
  }

  const btnCopyFileCode = document.getElementById("btnCopyFileCode");
  if (btnCopyFileCode) {
    btnCopyFileCode.addEventListener("click", () => {
      const codeEl = document.getElementById("codeContent");
      if (!codeEl) return;
      navigator.clipboard.writeText(codeEl.textContent).then(() => {
        const orig = btnCopyFileCode.innerHTML;
        btnCopyFileCode.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> <span style="color:#10b981;">Copied!</span>`;
        setTimeout(() => { btnCopyFileCode.innerHTML = orig; }, 1800);
      });
    });
  }

  window.addEventListener("resize", () => requestAnimationFrame(drawGraph));
}

// HELPERS
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function truncate(value, max) {
  value = String(value || "");
  return value.length <= max ? value : `${value.slice(0, max - 1)}...`;
}

function formatMarkdown(text) {
  if (!text) return "";
  let raw = String(text);

  // 1. Extract and protect code blocks
  const codeBlocks = [];
  raw = raw.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const placeholder = `@@@CODEBLOCK_${codeBlocks.length}@@@`;
    const escapedCode = escapeHtml(code.trimEnd());
    const langLabel = lang ? escapeHtml(lang) : "code";
    codeBlocks.push(`
      <div class="ai-code-card">
        <div class="ai-code-header">
          <span class="ai-code-lang">${langLabel}</span>
          <button type="button" class="btn-code-copy" onclick="copyCodeSnippet(this)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            <span>Copy</span>
          </button>
        </div>
        <pre class="ai-code-pre"><code>${escapedCode}</code></pre>
      </div>
    `);
    return placeholder;
  });

  // 2. Escape HTML for the rest of text
  let safe = escapeHtml(raw);

  // 3. Inline code
  safe = safe.replace(/`([^`\n]+)`/g, '<code class="ai-inline-code">$1</code>');

  // 4. Bold and Italics
  safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');

  // 5. Headings (#, ##, ###, ####)
  safe = safe.replace(/^#### (.*$)/gim, '<h6 class="ai-h4">$1</h6>');
  safe = safe.replace(/^### (.*$)/gim, '<h5 class="ai-h3">$1</h5>');
  safe = safe.replace(/^## (.*$)/gim, '<h4 class="ai-h2">$1</h4>');
  safe = safe.replace(/^# (.*$)/gim, '<h3 class="ai-h1">$1</h3>');

  // 6. Blockquotes
  safe = safe.replace(/^> (.*$)/gim, '<blockquote class="ai-quote">$1</blockquote>');

  // 7. Clickable file citations in text: e.g. "server/src/routes/index.js (Lines 16-29)" or "client/src/routes/ProtectedRoute.jsx:11"
  safe = safe.replace(/\b([a-zA-Z0-9_\-\.\/]+\.(?:js|jsx|ts|tsx|py|json|html|css|md))(?::(\d+)(?:-(\d+))?)?\b/g, (match, path) => {
    return `<span class="ai-file-link" onclick="previewFile('${escapeHtml(path)}')" title="Click to view file in editor"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg> <span>${match}</span></span>`;
  });

  // 8. Lists parsing (group consecutive bullet / ordered items into <ul> or <ol>)
  const lines = safe.split("\n");
  const outLines = [];
  let inUl = false;
  let inOl = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const bulletMatch = line.match(/^(\s*)[-*+]\s+(.*)$/);
    const numMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);

    if (bulletMatch) {
      if (inOl) { outLines.push("</ol>"); inOl = false; }
      if (!inUl) { outLines.push('<ul class="ai-list-ul">'); inUl = true; }
      outLines.push(`<li class="ai-list-li">${bulletMatch[2]}</li>`);
    } else if (numMatch) {
      if (inUl) { outLines.push("</ul>"); inUl = false; }
      if (!inOl) { outLines.push('<ol class="ai-list-ol">'); inOl = true; }
      outLines.push(`<li class="ai-list-li">${numMatch[2]}</li>`);
    } else {
      if (inUl) { outLines.push("</ul>"); inUl = false; }
      if (inOl) { outLines.push("</ol>"); inOl = false; }
      outLines.push(line);
    }
  }
  if (inUl) outLines.push("</ul>");
  if (inOl) outLines.push("</ol>");

  safe = outLines.join("\n");

  // 9. Paragraph breaks (replace double newlines with clean paragraph separation)
  safe = safe.replace(/\n{2,}/g, '</p><p class="ai-p">');
  safe = `<p class="ai-p">${safe}</p>`;
  // Clean up empty paragraphs around headers, lists, and code blocks
  safe = safe.replace(/<p class="ai-p">\s*<\/p>/g, "");
  safe = safe.replace(/<p class="ai-p">(<h[3-6]|<ul|<ol|<div|<blockquote)/g, "$1");
  safe = safe.replace(/(<\/h[3-6]>|<\/ul>|<\/ol>|<\/div>|<\/blockquote>)\s*<\/p>/g, "$1");

  // 10. Restore code blocks
  for (let i = 0; i < codeBlocks.length; i++) {
    safe = safe.replace(`@@@CODEBLOCK_${i}@@@`, codeBlocks[i]);
  }

  return safe;
}

// Run!
init();
