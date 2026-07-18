/* ============================================================
   aegispass — front-end app core
   Vanilla JS SPA shell: routing, API client, toasts, modals,
   command palette. Views are mounted into #view.
   ============================================================ */
"use strict";

const App = {
  state: { user: null, is_admin: false, sso: false, company: "AegisPass", app_name: "AD Manager", view: "dashboard" },
  views: {},          // name -> render(container) function
  paletteItems: [],   // built at boot
};

function BOOT(cfg) {
  Object.assign(App.state, cfg);
  document.getElementById("sideWho").textContent = (App.state.user.displayName || App.state.user.sAMAccountName || "—");
  document.getElementById("sideRole").textContent = App.state.is_admin ? "Domain Administrator" : "Authenticated user";
  if (App.state.is_admin) {
    document.getElementById("nav-admin").style.display = "";
    document.getElementById("nav-audit").style.display = "";
    const navWf = document.getElementById("nav-workflows");
    if (navWf) navWf.style.display = "";
  }
  App.views.dashboard = ViewDashboard;
  App.views.users = ViewUsers;
  App.views.groups = ViewGroups;
  App.views.ous = ViewOus;
  App.views.audit = ViewAudit;
  App.views.self = ViewSelf;
  App.views.admin = ViewAdmin;
  App.views.workflows = ViewWorkflows;
  App.views.enroll = ViewEnroll;
  buildPalette();
  bindShell();
  routeTo("dashboard");
  refreshStatusBtn();
  setInterval(refreshStatusBtn, 30000);
}

/* ---------- API client (envelope-aware) ---------- */
async function api(path, opts = {}) {
  const res = await fetch(path, Object.assign({ credentials: "same-origin",
    headers: { "Content-Type": "application/json" } }, opts));
  let body = null;
  try { body = await res.json(); } catch (_) {}
  if (body && typeof body.ok === "boolean") {
    if (!body.ok) { const e = new Error(body.error || "Request failed"); e.code = body.code; throw e; }
    return body.data;
  }
  if (!res.ok) { const e = new Error((body && body.error) || "Request failed"); throw e; }
  return body;
}

/* ---------- toast ---------- */
function toast(title, msg, kind = "ok") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.innerHTML = `<div><div class="t-title">${esc(title)}</div><div class="t-msg">${esc(msg || "")}</div></div>`;
  document.getElementById("toasts").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 250); }, 4200);
}
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

/* ---------- modal ---------- */
function openModal(html, opts = {}) {
  const m = document.getElementById("modal");
  m.className = "modal" + (opts.wide ? " wide" : "");
  m.innerHTML = html;
  document.getElementById("overlay").classList.add("show");
  const close = () => closeModal();
  m.querySelectorAll("[data-close]").forEach(b => b.onclick = close);
  m.querySelectorAll("form[data-api]").forEach(f => wireForm(f));
  return m;
}
function closeModal() { document.getElementById("overlay").classList.remove("show"); document.getElementById("modal").innerHTML = ""; }
document.getElementById("overlay").addEventListener("click", e => { if (e.target.id === "overlay") closeModal(); });

/* ---------- generic form wired to API ---------- */
function wireForm(form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector("button[type=submit]");
    const msg = form.querySelector("[data-form-msg]");
    if (btn) btn.disabled = true;
    try {
      const payload = JSON.parse(form.dataset.payload || "{}");
      const method = form.dataset.method || "POST";
      const data = form.dataset.mode === "form" ? new URLSearchParams(new FormData(form)) : payload;
      const res = await fetch(form.dataset.api, { method, credentials: "same-origin",
        headers: (form.dataset.mode === "json" ? { "Content-Type": "application/json" } : {}),
        body: form.dataset.mode === "json" ? JSON.stringify(payload) : data });
      const out = await res.json().catch(() => ({}));
      if (!res.ok || (out && out.ok === false)) throw new Error((out && out.error) || "Failed");
      toast("Success", (out && out.data && out.data.msg) || "Done", "ok");
      closeModal();
      if (form.dataset.reload) location.hash = "#" + form.dataset.reload;
      else if (App.views[App.state.view]) App.views[App.state.view](document.getElementById("view"));
    } catch (err) {
      if (msg) { msg.textContent = err.message; msg.style.color = "var(--danger)"; }
      else toast("Error", err.message, "err");
    } finally { if (btn) btn.disabled = false; }
  });
}

/* ---------- routing ---------- */
function routeTo(view) {
  if (!App.views[view]) view = "dashboard";
  App.state.view = view;
  document.querySelectorAll(".nav a").forEach(a => a.classList.toggle("active", a.dataset.view === view));
  const labels = { dashboard: "Dashboard", users: "Users", groups: "Groups", ous: "Organizational Units", audit: "Audit log", self: "My password", admin: "Administration" };
  document.getElementById("crumb").innerHTML = `<b>${labels[view] || "Dashboard"}</b>`;
  const v = document.getElementById("view");
  v.innerHTML = `<div class="loading"><span class="spinner"></span> Loading…</div>`;
  try { (App.views[view] || App.views.dashboard)(v); }
  catch (e) { v.innerHTML = `<div class="empty">Failed to load view: ${esc(e.message)}</div>`; }
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", () => {
  const v = location.hash.replace("#", "");
  if (v) routeTo(v);
});
function navGo(view) { location.hash = "#" + view; routeTo(view); }

/* ---------- shell bindings ---------- */
function bindShell() {
  document.getElementById("toggleSide").onclick = () => document.getElementById("app").classList.toggle("collapsed");
  document.querySelectorAll(".nav a").forEach(a => a.onclick = () => navGo(a.dataset.view));
  document.getElementById("openPalette").onclick = openPalette;
  document.addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); }
    if (e.key === "Escape") { closeModal(); document.getElementById("palette").classList.remove("show"); }
  });
}

/* ---------- status button ---------- */
async function refreshStatusBtn() {
  try {
    const s = await (await fetch("/status.json")).json();
    const ok = s.directory === "online" && s.secure_channel === "verified";
    document.getElementById("statusBtn").textContent = ok ? "🟢" : "🟡";
    document.getElementById("statusBtn").title = ok ? "Directory online · channel verified"
      : "Directory degraded";
  } catch (_) { document.getElementById("statusBtn").textContent = "⚪"; }
}

/* ---------- command palette ---------- */
function buildPalette() {
  const items = [
    { icon: "▦", title: "Dashboard", keys: "G D", go: () => navGo("dashboard") },
    { icon: "👤", title: "Users", keys: "G U", go: () => navGo("users") },
    { icon: "👥", title: "Groups", keys: "G G", go: () => navGo("groups") },
    { icon: "🗂", title: "Organizational Units", go: () => navGo("ous") },
    { icon: "🔑", title: "Change my password", go: () => navGo("self") },
  ];
  if (App.state.is_admin) {
    items.push({ icon: "⚙", title: "Administration", go: () => navGo("admin") });
    items.push({ icon: "🛡", title: "Audit log", go: () => navGo("audit") });
  }
  App.paletteItems = items;
}
function openPalette() {
  const p = document.getElementById("palette");
  p.classList.add("show");
  const input = document.getElementById("paletteInput");
  input.value = ""; input.focus();
  renderPalette("");
  input.oninput = () => renderPalette(input.value);
  input.onkeydown = (e) => {
    if (e.key === "Enter") { const sel = p.querySelector(".item.sel") || p.querySelector(".item"); if (sel) sel.click(); }
  };
}
function renderPalette(q) {
  const box = document.getElementById("paletteResults");
  const ql = q.toLowerCase();
  const list = App.paletteItems.filter(i => !ql || i.title.toLowerCase().includes(ql));
  box.innerHTML = list.map((i, idx) => `<div class="item ${idx === 0 ? "sel" : ""}" data-i="${App.paletteItems.indexOf(i)}"><span>${i.icon}</span><span>${esc(i.title)}</span><span class="keys">${i.keys || ""}</span></div>`).join("") || `<div class="empty">No matches</div>`;
  box.querySelectorAll(".item").forEach(el => el.onclick = () => { const i = App.paletteItems[+el.dataset.i]; document.getElementById("palette").classList.remove("show"); i.go(); });
}
document.getElementById("palette").addEventListener("click", e => { if (e.target.id === "palette") e.target.classList.remove("show"); });

/* ============================================================
   VIEWS
   ============================================================ */
function ViewDashboard(v) {
  const user = App.state.user || {};
  const greeting = greetHour();
  const role = App.state.is_admin ? "Domain Administrator" : "Authenticated user";
  v.innerHTML = `
    <!-- Hero greeting -->
    <div class="hero-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap">
        <div>
          <h1>${esc(greeting)}, ${esc(user.givenName || user.displayName || user.sAMAccountName || "Admin")}</h1>
          <p>${esc(role)} · ${esc(user.sAMAccountName || "")} · ${esc(App.state.company)}</p>
        </div>
        <div class="hero-pill"><span class="dot green"></span>Directory online</div>
      </div>
    </div>

    <!-- KPI stat cards -->
    <div class="grid stat-grid" id="stats">
      <div class="card">
        <div class="card-head">
          <div class="subtle">Total users</div>
          <div class="kpi ico blue">👤</div>
        </div>
        <div class="kpi"><div class="num">…</div><div class="delta">+0.2%</div></div>
        <div class="spark" id="spark1">${sparkBars().map(h => `<i style="height:${h}%"></i>`).join("")}</div>
      </div>

      <div class="card">
        <div class="card-head">
          <div class="subtle">Active accounts</div>
          <div class="kpi ico green">✓</div>
        </div>
        <div class="kpi"><div class="num">…</div><div class="delta">healthy</div></div>
      </div>

      <div class="card">
        <div class="card-head">
          <div class="subtle">Locked accounts</div>
          <div class="kpi ico warn">🔒</div>
        </div>
        <div class="kpi"><div class="num">…</div></div>
      </div>

      <div class="card">
        <div class="card-head">
          <div class="subtle">Groups</div>
          <div class="kpi ico purple">👥</div>
        </div>
        <div class="kpi"><div class="num">…</div><div class="delta">+1</div></div>
        <div class="spark" id="spark4">${sparkBars().map(h => `<i style="height:${h}%"></i>`).join("")}</div>
      </div>
    </div>

    <!-- Quick actions + Health + Activity -->
    <div class="grid" style="margin-top:22px;grid-template-columns:1.1fr 1fr 1fr">

      <!-- Quick actions -->
      <div class="card">
        <div class="card-head"><h3>Quick actions</h3></div>
        <div class="qa-grid">
          <div class="qa-tile" onclick="navGo('users')"><div class="ico" style="background:var(--blue-soft);color:#0369a1">👤</div><div class="ttl">Browse users</div></div>
          <div class="qa-tile" onclick="navGo('groups')"><div class="ico" style="background:var(--purple-soft);color:#6d28d9">👥</div><div class="ttl">Manage groups</div></div>
          <div class="qa-tile" onclick="navGo('self')"><div class="ico" style="background:var(--ok-soft);color:#047857">🔑</div><div class="ttl">Change my password</div></div>
          ${App.state.is_admin ? `<div class="qa-tile" onclick="showCreateUser()"><div class="ico" style="background:rgba(32,58,94,.12);color:#203a5e">➕</div><div class="ttl">Create user</div></div>
          <div class="qa-tile" onclick="navGo('audit')"><div class="ico" style="background:var(--warn-soft);color:#b45309">🛡</div><div class="ttl">Audit log</div></div>` : ''}
        </div>
      </div>

      <!-- Directory health -->
      <div class="card">
        <div class="card-head"><h3>Directory health</h3><span class="pill green" id="healthBadge"><span class="dot green"></span>Online</span></div>
        <div id="healthBox"><div class="loading"><span class="spinner"></span></div></div>
        <div class="divider"></div>
        <div class="subtle" style="margin-bottom:8px">Connection latency</div>
        <div style="display:flex;align-items:center;gap:10px">
          <div class="live-bar" style="flex:1;background:var(--surface-3)"><span id="latencyBar" style="width:0%;background:var(--blue)"></span></div>
          <span class="pill blue" id="latencyValue">— ms</span>
        </div>
      </div>

      <!-- Recent activity -->
      <div class="card">
        <div class="card-head"><h3>Recent activity</h3></div>
        <div id="activityBox"><div class="loading"><span class="spinner"></span></div></div>
      </div>
    </div>

    <!-- Services status -->
    <div class="grid" style="margin-top:22px;grid-template-columns:1fr 1fr">
      <div class="card" style="grid-column:1 / -1">
        <div class="card-head"><h3>Services status</h3><span class="pill green" id="svcBadge"><span class="dot green"></span>All systems operational</span></div>
        <div id="servicesBox"><div class="loading"><span class="spinner"></span></div></div>
      </div>
    </div>

    <!-- Device fleet status -->
    <div class="grid" style="margin-top:22px">
      <div class="card" style="grid-column:1 / -1">
        <div class="card-head"><h3>Device fleet status</h3><span class="pill blue" id="devBadge">Domain-joined</span></div>
        <div id="deviceBox"><div class="loading"><span class="spinner"></span></div></div>
      </div>
    </div>`;
  loadDashboardData(v);
}
function greetHour(){
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}
function sparkBars(n=10){
  return Array.from({length:n}, () => 20 + Math.floor(Math.random()*70));
}
async function loadDashboardData(v){
  try {
    const st = await api("/api/user-stats");
    const nums = v.querySelectorAll(".stat-grid .num");
    if (nums[0]) nums[0].textContent = (st.total ?? 0).toLocaleString();
    if (nums[1]) nums[1].textContent = (st.enabled ?? 0).toLocaleString();
    if (nums[2]) nums[2].textContent = (st.locked ?? 0).toLocaleString();
    if (nums[3]) nums[3].textContent = (st.groups ?? 0).toLocaleString();
  } catch (e) { /* leave placeholders */ }
  loadHealth(v);
  loadActivity(v);
  loadDevices(v);
  loadServices(v);
}
async function loadServices(v){
  const box = v.querySelector("#servicesBox");
  if (!box) return;
  try {
    const s = await (await fetch("/status.json")).json();
    const allOk = s.directory === "online" && s.secure_channel === "verified" && s.sso === "available";
    const badge = v.querySelector("#svcBadge");
    if (badge) badge.outerHTML = allOk
      ? `<span class="pill green"><span class="dot green"></span>All systems operational</span>`
      : `<span class="pill amber"><span class="dot amber"></span>Some services degraded</span>`;
    const pill = (ok, label, detail) => `
      <div class="card" style="padding:16px;background:${ok?'var(--surface-2)':'var(--warn-soft)'};border:1px solid ${ok?'var(--border-soft)':'rgba(245,158,11,.35)'}">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
          <div style="width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-size:18px;background:${ok?'var(--ok-soft)':'var(--warn-soft)'};color:${ok?'#047857':'#b45309'}">${ok?'✓':'!'}</div>
          <div>
            <div style="font-weight:650;font-size:14px;color:var(--txt)">${label}</div>
            <div style="font-size:12px;color:var(--txt-3)">${ok?'Operational': 'Degraded'}</div>
          </div>
        </div>
        <div class="subtle">${detail}</div>
      </div>`;
    const latencyPct = Math.max(5, Math.min(100, 100 - ((s.latency_ms || 0) / 2)));
    box.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:18px">
        ${pill(s.directory==='online', 'Directory services', s.directory === 'online' ? 'AD reachable over LDAPS' : 'Connection issue')}
        ${pill(s.secure_channel==='verified', 'Secure channel', s.secure_channel === 'verified' ? 'Certificate pinned & verified' : 'TLS verification issue')}
        ${pill(s.sso==='available', 'Single sign-on', s.sso === 'available' ? 'Negotiate available' : 'SSO not configured')}
        ${pill(true, 'API services', 'Dashboard API responding')}
      </div>
      <div class="subtle" style="margin-bottom:8px">Live response latency</div>
      <div style="display:flex;align-items:center;gap:12px">
        <div class="live-bar" style="flex:1;background:var(--surface-3)"><span id="svcLatencyBar" style="width:0%;background:${latencyPct > 80 ? 'var(--ok)' : latencyPct > 40 ? 'var(--warn)' : 'var(--danger)'}"></span></div>
        <span class="pill ${latencyPct > 80 ? 'green' : latencyPct > 40 ? 'amber' : 'red'}" id="svcLatencyValue">${s.latency_ms || 0} ms</span>
      </div>
      <div class="spark" id="svcSpark" style="margin-top:10px;height:24px">${sparkBars().map(h=>`<i style="height:${h}%"></i>`).join("")}</div>`;
    setTimeout(() => {
      const bar = box.querySelector("#svcLatencyBar");
      if (bar) bar.style.width = latencyPct + '%';
    }, 50);
  } catch (e) {
    box.innerHTML = `<div class="empty">Services status unavailable</div>`;
  }
}
async function loadDevices(v){
  const box = v.querySelector("#deviceBox");
  if (!box) return;
  try {
    const d = await api("/api/device-stats");
    if (d.error) throw new Error(d.error);
    const sites = Object.entries(d.sites || {}).sort((a,b)=>b[1]-a[1]).slice(0,5);
    const os = Object.entries(d.os || {}).sort((a,b)=>b[1]-a[1]);
    box.innerHTML = `
      <div class="grid stat-grid" style="margin-bottom:18px">
        <div class="card" style="padding:16px;background:var(--surface-2);border:1px solid var(--border-soft)">
          <div class="subtle">Total devices</div>
          <div class="kpi"><div class="num" style="font-size:28px">${(d.total||0).toLocaleString()}</div></div>
        </div>
        <div class="card" style="padding:16px;background:var(--surface-2);border:1px solid var(--border-soft)">
          <div class="subtle">Active / Enabled</div>
          <div class="kpi"><div class="num" style="font-size:28px;color:var(--ok)">${(d.active||0).toLocaleString()}</div></div>
        </div>
        <div class="card" style="padding:16px;background:var(--surface-2);border:1px solid var(--border-soft)">
          <div class="subtle">Stale &gt;60d</div>
          <div class="kpi"><div class="num" style="font-size:28px;color:${d.stale?'var(--warn)':'var(--ok)'}">${(d.stale||0).toLocaleString()}</div></div>
        </div>
        <div class="card" style="padding:16px;background:var(--surface-2);border:1px solid var(--border-soft)">
          <div class="subtle">Disabled</div>
          <div class="kpi"><div class="num" style="font-size:28px;color:${d.disabled?'var(--danger)':'var(--ok)'}">${(d.disabled||0).toLocaleString()}</div></div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;align-items:start">
        <div>
          <div class="subtle" style="margin-bottom:10px;text-transform:uppercase">By type</div>
          <div style="display:flex;flex-direction:column;gap:10px">
            <div class="bar-row"><span>Workstations</span><div class="bar-track"><span class="bar" style="width:${pct(d.workstations,d.total)}%;background:var(--blue)"></span></div><span class="subtle">${(d.workstations||0).toLocaleString()}</span></div>
            <div class="bar-row"><span>Servers</span><div class="bar-track"><span class="bar" style="width:${pct(d.servers,d.total)}%;background:var(--purple)"></span></div><span class="subtle">${(d.servers||0).toLocaleString()}</span></div>
            <div class="bar-row"><span>Domain controllers</span><div class="bar-track"><span class="bar" style="width:${pct(d.domain_controllers,d.total)}%;background:var(--brand)"></span></div><span class="subtle">${(d.domain_controllers||0).toLocaleString()}</span></div>
          </div>
        </div>
        <div>
          <div class="subtle" style="margin-bottom:10px;text-transform:uppercase">By operating system</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px">
            ${os.map(([name,c]) => `<span class="pill" title="${esc(name)}">${esc(name)} <b>${c}</b></span>`).join('') || '<span class="subtle">No OS data available</span>'}
          </div>
        </div>
        <div>
          <div class="subtle" style="margin-bottom:10px;text-transform:uppercase">By location / OU</div>
          <div style="display:flex;flex-direction:column;gap:10px">
            ${sites.map(([site,c]) => `
            <div class="bar-row">
              <span>${esc(site)}</span>
              <div class="bar-track"><span class="bar" style="width:${pct(c,d.total)}%;background:var(--brand-2)"></span></div>
              <span class="subtle">${c}</span>
            </div>`).join('') || '<span class="subtle">No site data available</span>'}
          </div>
        </div>
      </div>`;
  } catch (e) {
    box.innerHTML = `<div class="empty">Device status unavailable</div>`;
  }
}
function pct(part,total){ return total ? Math.max(1, Math.round((part/total)*100)) : 0; }
async function loadHealth(v){
  try {
    const s = await (await fetch("/status.json")).json();
    const ok = s.directory === "online" && s.secure_channel === "verified";
    const badge = v.querySelector("#healthBadge");
    if (badge) badge.outerHTML = ok
      ? `<span class="pill green"><span class="dot green"></span>Online</span>`
      : `<span class="pill amber"><span class="dot amber"></span>Degraded</span>`;
    v.querySelector("#healthBox").innerHTML = `
      <div style="display:flex;flex-direction:column;gap:14px">
        <div class="live-row" style="padding:0;border:0">
          <div class="live-ico ${s.directory==='online'?'ok':'off'}" style="width:34px;height:34px;font-size:16px">✓</div>
          <div class="live-info">
            <div class="live-label" style="font-size:13.5px">Directory services</div>
            <div class="live-detail">${s.directory === 'online' ? 'Reachable over LDAPS' : 'Unreachable'}</div>
          </div>
        </div>
        <div class="live-row" style="padding:0;border:0">
          <div class="live-ico ${s.secure_channel==='verified'?'ok':'off'}" style="width:34px;height:34px;font-size:16px">🔒</div>
          <div class="live-info">
            <div class="live-label" style="font-size:13.5px">Secure channel</div>
            <div class="live-detail">${s.secure_channel === 'verified' ? 'Certificate pinned and verified' : 'Unverified'}</div>
          </div>
        </div>
        <div class="live-row" style="padding:0;border:0">
          <div class="live-ico ${s.sso==='available'?'ok':'off'}" style="width:34px;height:34px;font-size:16px">☁</div>
          <div class="live-info">
            <div class="live-label" style="font-size:13.5px">Single sign-on</div>
            <div class="live-detail">${s.sso === 'available' ? 'Negotiate available on network' : 'Not configured'}</div>
          </div>
        </div>
      </div>`;
    const ms = s.latency_ms || 0;
    const pct = Math.max(5, Math.min(100, 100 - (ms / 2)));
    const bar = v.querySelector("#latencyBar");
    const val = v.querySelector("#latencyValue");
    if (bar) setTimeout(() => bar.style.width = pct + '%', 50);
    if (val) val.textContent = ms + ' ms';
  } catch (e) { v.querySelector("#healthBox").innerHTML = `<div class="empty">Status unavailable</div>`; }
}
async function loadActivity(v){
  const box = v.querySelector("#activityBox");
  if (!box) return;
  if (!App.state.is_admin) {
    box.innerHTML = `<div class="feed">
      <div class="feed-item"><div class="feed-dot blue"></div><div class="feed-body"><div class="feed-title">Welcome back</div><div class="feed-meta">Your session is active and the directory is online.</div></div></div>
    </div>`;
    return;
  }
  try {
    const rows = await api("/api/audit?limit=5");
    if (!rows || !rows.length) {
      box.innerHTML = `<div class="empty">No recent privileged actions recorded.</div>`;
      return;
    }
    box.innerHTML = `<div class="feed">${rows.slice().reverse().map(r => {
      const color = r.outcome === 'success' ? 'green' : r.outcome === 'denied' ? 'red' : 'amber';
      const action = r.action.replace(/\./g, ' ');
      return `<div class="feed-item">
        <div class="feed-dot ${color}"></div>
        <div class="feed-body">
          <div class="feed-title">${esc(action)}${r.target ? ' · ' + esc(r.target.split(',')[0]) : ''}</div>
          <div class="feed-meta">${esc(r.actor)} · ${esc(r.ts)} · <span class="pill ${color}">${esc(r.outcome)}</span></div>
        </div>
      </div>`;
    }).join('')}</div>`;
  } catch (e) {
    box.innerHTML = `<div class="empty">Activity feed unavailable</div>`;
  }
}
function ViewSelf(v) {
  v.innerHTML = `
    <div class="card" style="max-width:520px">
      <div class="card-head"><h3>Change your password</h3></div>
      <form id="spForm">
        <div class="field"><label>Current password</label><input class="input" type="password" name="old_password" required></div>
        <div class="field"><label>New password</label><input class="input" type="password" name="new_password" required></div>
        <p class="muted tiny" data-form-msg></p>
        <button class="btn primary" type="submit" style="width:100%">Change password</button>
      </form>
    </div>`;
  const form = v.querySelector("form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector("button"); btn.disabled = true;
    const msg = form.querySelector("[data-form-msg]");
    try {
      await api("/api/self/password", { method: "POST", body: JSON.stringify({
        old_password: form.old_password.value, new_password: form.new_password.value }) });
      toast("Password changed", "You can now use your new password.", "ok");
      form.reset();
    } catch (err) { msg.textContent = err.message; msg.style.color = "var(--danger)"; }
    finally { btn.disabled = false; }
  });
}

/* Placeholders registered so routing never breaks before subagent views load.
   These are replaced when views/users.js etc. are present. */
function ViewUsers(v) {
  v.innerHTML = `
    <div class="toolbar">
      <div class="searchbar" style="flex:1"><span>🔎</span><input id="uSearch" placeholder="Search users (name, username, email)…"><span class="kbd">/</span></div>
      ${App.state.is_admin ? '<button class="btn primary" id="uCreate">➕ New user</button>' : ''}
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Directory users</h3><div class="spacer"></div><span class="pill" id="uCount">…</span></div>
      <div class="table-wrap"><table class="data" id="uTable">
        <thead><tr>
          <th data-sort="sAMAccountName">Username</th><th data-sort="displayName">Name</th>
          <th data-sort="mail">Email</th><th>Status</th><th></th>
        </tr></thead>
        <tbody><tr><td colspan="5"><div class="loading"><span class="spinner"></span></div></td></tr></tbody>
      </table></div>
    </div>`;
  const tbody = v.querySelector("#uTable tbody");
  let data = [];
  async function load(q = "") {
    try {
      const out = await api("/api/users?q=" + encodeURIComponent(q) + "&per_page=500");
      data = out || [];
      v.querySelector("#uCount").textContent = (out && out.meta && out.meta.total) || data.length;
      render();
    } catch (e) { tbody.innerHTML = `<tr><td colspan="5" class="empty">${esc(e.message)}</td></tr>`; }
  }
  function render() {
    if (!data.length) { tbody.innerHTML = `<tr><td colspan="5" class="empty">No users found</td></tr>`; return; }
    tbody.innerHTML = data.map(u => {
      const disabled = (u.userAccountControl || 0) & 2;
      const status = u.locked ? '<span class="pill red"><span class="dot red"></span>Locked</span>'
        : disabled ? '<span class="pill red">Disabled</span>' : '<span class="pill green"><span class="dot green"></span>Active</span>';
      return `<tr>
        <td><b>${esc(u.sAMAccountName)}</b></td>
        <td>${esc(u.displayName || "")}</td>
        <td class="muted">${esc(u.mail || "")}</td>
        <td>${status}</td>
        <td style="text-align:right;white-space:nowrap">
          <button class="btn sm" data-act="unlock" data-dn="${enc(u.dn)}">Unlock</button>
          <button class="btn sm" data-act="pw" data-dn="${enc(u.dn)}">Reset PW</button>
          ${App.state.is_admin ? `<button class="btn sm danger" data-act="del" data-dn="${enc(u.dn)}">Delete</button>` : ''}
        </td></tr>`;
    }).join("");
    tbody.querySelectorAll("button[data-act]").forEach(b => b.onclick = () => userAction(b.dataset.act, b.dataset.dn));
  }
  v.querySelector("#uSearch").oninput = (e) => load(e.target.value);
  if (App.state.is_admin) v.querySelector("#uCreate").onclick = showCreateUser;
  load();
}
function enc(s){ return encodeURIComponent(s); }

function userAction(act, dn) {
  if (act === "unlock") {
    api("/api/users/" + enc(dn) + "/unlock", { method: "POST" }).then(() => toast("Unlocked", "Account unlocked", "ok")).catch(e => toast("Error", e.message, "err"));
  } else if (act === "pw") {
    openModal(`<div class="modal-head"><h3>Reset password</h3><button class="btn ghost sm x" data-close>✕</button></div>
      <form data-api="/api/users/${enc(dn)}/password" data-method="POST" data-mode="json" data-payload='{}'>
      <div class="modal-body">
        <div class="field"><label>New password</label><input class="input" name="new_password" required placeholder="Min 8 chars, complex"></div>
        <label class="check"><input type="checkbox" name="force_change" checked> Require change at next logon</label>
        <p class="muted tiny" data-form-msg></p>
      </div>
      <div class="modal-foot"><button class="btn ghost" data-close type="button">Cancel</button><button class="btn primary" type="submit">Reset</button></div>
      </form>`);
  } else if (act === "del") {
    openModal(`<div class="modal-head"><h3>Delete user?</h3><button class="btn ghost sm x" data-close>✕</button></div>
      <div class="modal-body"><p>This permanently removes the account. This cannot be undone.</p>
      <p class="muted tiny">${esc(dn)}</p></div>
      <div class="modal-foot"><button class="btn ghost" data-close type="button">Cancel</button>
      <button class="btn danger" id="delGo">Delete</button></div>`);
    document.getElementById("delGo").onclick = () => api("/api/users/" + enc(dn), { method: "DELETE" }).then(() => { toast("Deleted", "User removed", "ok"); closeModal(); routeTo("users"); }).catch(e => toast("Error", e.message, "err"));
  }
}

function showCreateUser() {
  openModal(`<div class="modal-head"><h3>Create new user</h3><button class="btn ghost sm x" data-close>✕</button></div>
    <form id="cuForm"><div class="modal-body">
      <div class="row">
        <div class="field"><label>First name</label><input class="input" name="givenName" required></div>
        <div class="field"><label>Last name</label><input class="input" name="sn" required></div>
      </div>
      <div class="row">
        <div class="field"><label>Username (sAMAccountName)</label><input class="input" name="sam" required placeholder="jdoe"></div>
        <div class="field"><label>Email</label><input class="input" name="mail" placeholder="jdoe@example.com"></div>
      </div>
      <div class="field"><label>Target OU</label><input class="input" name="ou" value="OU=STTJ,DC=example,DC=com"></div>
      <label class="check"><input type="checkbox" name="autopw" checked> Auto-generate a secure 12-char password (embeds a AegisPass school code + Jorah + One)</label>
      <div class="field" id="cuPwWrap" style="display:none"><label>Temporary password</label><input class="input" name="pw" placeholder="Min 8 chars, complex"></div>
      <label class="check"><input type="checkbox" name="force" checked> User must change at next logon</label>
      <p class="muted tiny" id="cuMsg"></p>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close type="button">Cancel</button>
    <button class="btn primary" type="submit">Create user</button></div></form>`, { wide: true });
  const cu = document.getElementById("cuForm");
  if (cu.autopw) cu.autopw.addEventListener("change", () => {
    document.getElementById("cuPwWrap").style.display = cu.autopw.checked ? "none" : "block";
    if (cu.pw) cu.pw.required = !cu.autopw.checked;
  });
  cu.addEventListener("submit", async (e) => {
    e.preventDefault(); const f = e.target; const btn = f.querySelector("button[type=submit]"); btn.disabled = true;
    try {
      const given = f.givenName.value.trim(), sn = f.sn.value.trim(), sam = f.sam.value.trim();
      const mail = f.mail.value.trim(), ou = f.ou.value.trim();
      const autopw = f.autopw && f.autopw.checked;
      const pw = autopw ? "" : f.pw.value;
      const dn = "CN=" + given + " " + sn + "," + ou;
      const upn = mail.includes("@") ? mail : sam + "@example.com";
      const r = await api("/api/users", { method: "POST", body: JSON.stringify({ dn, password: pw,
        force_change: f.force.checked, attrs: { givenName: given, sn, displayName: given + " " + sn,
        sAMAccountName: sam, userPrincipalName: upn, mail: mail || upn } }) });
      const gen = (r && r.generated_password);
      if (gen) {
        closeModal();
        openModal(`<div class="modal-head"><h3>User created — temporary password</h3><button class="btn ghost sm x" data-close>✕</button></div>
          <div class="modal-body">
            <p><b>${esc(sam)}</b> was provisioned. Share this temporary password securely:</p>
            <div class="codebox" style="font-family:monospace;font-size:18px;background:var(--surface-2);padding:12px;border-radius:8px;letter-spacing:1px">${esc(gen)}</div>
            <p class="muted tiny">12 characters · includes a AegisPass school code, "Jorah" and "One". User must change it at next logon.</p>
          </div>
          <div class="modal-foot"><button class="btn primary" data-close type="button">Done</button></div>`);
        routeTo("users");
      } else {
        toast("User created", sam + " provisioned", "ok"); closeModal(); routeTo("users");
      }
    } catch (err) { document.getElementById("cuMsg").textContent = err.message; document.getElementById("cuMsg").style.color = "var(--danger)"; }
    finally { btn.disabled = false; }
  });
}
function ViewGroups(v) {
  v.innerHTML = `
    <div class="toolbar">
      <div class="searchbar" style="flex:1"><span>🔎</span><input id="gSearch" placeholder="Search groups…"></div>
      ${App.state.is_admin ? '<button class="btn primary" id="gCreate">➕ New group</button>' : ''}
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Groups</h3><div class="spacer"></div><span class="pill" id="gCount">…</span></div>
      <div class="table-wrap"><table class="data" id="gTable">
        <thead><tr><th>Name</th><th>SamAccountName</th><th>Members</th><th></th></tr></thead>
        <tbody><tr><td colspan="4"><div class="loading"><span class="spinner"></span></div></td></tr></tbody>
      </table></div>
    </div>`;
  const tbody = v.querySelector("#gTable tbody"); let data = [];
  async function load(q = "") {
    try { const out = await api("/api/groups?q=" + encodeURIComponent(q)); data = out || [];
      v.querySelector("#gCount").textContent = (out && out.meta && out.meta.total) || data.length; render();
    } catch (e) { tbody.innerHTML = `<tr><td colspan="4" class="empty">${esc(e.message)}</td></tr>`; }
  }
  function render() {
    if (!data.length) { tbody.innerHTML = `<tr><td colspan="4" class="empty">No groups found</td></tr>`; return; }
    tbody.innerHTML = data.map(g => `<tr>
      <td><b>${esc(g.cn)}</b></td><td class="muted">${esc(g.sAMAccountName || "")}</td>
      <td><span class="pill">${(g.member || []).length}</span></td>
      <td style="text-align:right;white-space:nowrap">
        <button class="btn sm" data-act="view" data-dn="${enc(g.dn)}">Members</button>
        <button class="btn sm" data-act="copy" data-dn="${enc(g.dn)}">Copy</button>
        ${App.state.is_admin ? `<button class="btn sm danger" data-act="del" data-dn="${enc(g.dn)}">Delete</button>` : ''}
      </td></tr>`).join("");
    tbody.querySelectorAll("button[data-act]").forEach(b => b.onclick = () => groupAction(b.dataset.act, b.dataset.dn));
  }
  v.querySelector("#gSearch").oninput = e => load(e.target.value);
  if (App.state.is_admin) v.querySelector("#gCreate").onclick = showCreateGroup;
  load();
}
function groupAction(act, dn) {
  if (act === "view") groupMembers(dn);
  else if (act === "copy") copyGroup(dn);
  else if (act === "del") openModal(`<div class="modal-head"><h3>Delete group?</h3><button class="btn ghost sm x" data-close>✕</button></div>
    <div class="modal-body"><p class="muted tiny">${esc(dn)}</p></div>
    <div class="modal-foot"><button class="btn ghost" data-close type="button">Cancel</button><button class="btn danger" id="gdel">Delete</button></div>`,
    () => { document.getElementById("gdel").onclick = () => api("/api/groups/" + enc(dn), { method: "DELETE" }).then(() => { toast("Deleted", "Group removed", "ok"); closeModal(); routeTo("groups"); }).catch(e => toast("Error", e.message, "err")); });
}
function groupMembers(dn) {
  api("/api/groups/" + enc(dn)).then(g => {
    const members = (g && g.member) || [];
    openModal(`<div class="modal-head"><h3>${esc(g ? g.cn : "Group")} — members</h3><button class="btn ghost sm x" data-close>✕</button></div>
      <div class="modal-body">
        <div class="field"><label>Add member (distinguished name)</label>
          <div style="display:flex;gap:8px"><input class="input" id="mAdd" placeholder="CN=Jane Doe,OU=…,DC=example,DC=com"><button class="btn primary" id="mAddBtn">Add</button></div>
          <p class="muted tiny" id="mMsg"></p></div>
        <div class="table-wrap"><table class="data"><thead><tr><th>Member DN</th><th></th></tr></thead><tbody>
          ${members.map(m => `<tr><td class="muted tiny">${esc(m)}</td><td style="text-align:right"><button class="btn sm danger" data-m="${enc(m)}">Remove</button></td></tr>`).join("") || '<tr><td colspan="2" class="empty">No members</td></tr>'}
        </tbody></table></div>
      </div>`);
    const reload = () => groupMembers(dn);
    document.getElementById("mAddBtn").onclick = async () => {
      const m = document.getElementById("mAdd").value.trim(); if (!m) return;
      try { await api("/api/groups/" + enc(dn) + "/members", { method: "POST", body: JSON.stringify({ member_dn: m }) });
        toast("Added", "Member added", "ok"); reload(); } catch (e) { document.getElementById("mMsg").textContent = e.message; }
    };
    document.querySelectorAll("[data-m]").forEach(b => b.onclick = async () => {
      try { await api("/api/groups/" + enc(dn) + "/members", { method: "DELETE", body: JSON.stringify({ member_dn: b.dataset.m }) });
        toast("Removed", "Member removed", "ok"); reload(); } catch (e) { toast("Error", e.message, "err"); }
    });
  }).catch(e => toast("Error", e.message, "err"));
}
function copyGroup(src) {
  openModal(`<div class="modal-head"><h3>Copy members</h3><button class="btn ghost sm x" data-close>✕</button></div>
    <form id="copyF"><div class="modal-body">
      <div class="field"><label>Target group DN</label><input class="input" name="tgt" required placeholder="CN=Teachers,OU=…,DC=example,DC=com"></div>
      <p class="muted tiny">Copies all members from the source group into the target (adds, does not remove).</p>
      <p class="muted tiny" id="cMsg"></p>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close type="button">Cancel</button><button class="btn primary" type="submit">Copy</button></div></form>`,
    () => document.getElementById("copyF").addEventListener("submit", async (e) => {
      e.preventDefault(); const tgt = e.target.tgt.value.trim();
      try { await api("/api/groups/copy", { method: "POST", body: JSON.stringify({ source_dn: src, target_dn: tgt }) });
        toast("Copied", "Members copied to target", "ok"); closeModal(); } catch (e2) { document.getElementById("cMsg").textContent = e2.message; }
    }));
}
function showCreateGroup() {
  openModal(`<div class="modal-head"><h3>Create group</h3><button class="btn ghost sm x" data-close>✕</button></div>
    <form id="cgF"><div class="modal-body">
      <div class="field"><label>Common name (cn)</label><input class="input" name="cn" required placeholder="Teachers"></div>
      <div class="field"><label>Target OU</label><input class="input" name="ou" value="OU=STTJ,DC=example,DC=com"></div>
      <div class="field"><label>Description</label><input class="input" name="desc"></div>
      <div class="field"><label>Scope</label><select name="scope"><option value="global">Global</option><option value="domain">Domain local</option><option value="universal">Universal</option></select></div>
      <p class="muted tiny" id="cgMsg"></p>
    </div>
    <div class="modal-foot"><button class="btn ghost" data-close type="button">Cancel</button><button class="btn primary" type="submit">Create</button></div></form>`,
    () => document.getElementById("cgF").addEventListener("submit", async (e) => {
      e.preventDefault(); const f = e.target;
      const cn = f.cn.value.trim(), ou = f.ou.value.trim();
      const sam = cn.replace(/[^A-Za-z0-9]/g, "");
      try { await api("/api/groups", { method: "POST", body: JSON.stringify({ dn: "CN=" + cn + "," + ou, sam, desc: f.desc.value.trim(), scope: f.scope.value }) });
        toast("Group created", cn, "ok"); closeModal(); routeTo("groups"); } catch (e2) { document.getElementById("cgMsg").textContent = e2.message; }
    }));
}
function ViewOus(v) {
  v.innerHTML = `
    <div class="panel"><div class="panel-head"><h3>Organizational Units</h3>
      <div class="spacer"></div><span class="muted tiny">Read-only browser</span></div>
      <div class="table-wrap"><table class="data" id="oTable">
        <thead><tr><th>OU name</th><th>Distinguished name</th></tr></thead>
        <tbody><tr><td colspan="2"><div class="loading"><span class="spinner"></span></div></td></tr></tbody>
      </table></div></div>`;
  const tbody = v.querySelector("#oTable tbody"); let path = [];
  async function load(parent) {
    try { const out = await api("/api/ous?parent=" + enc(parent || "")); const list = out || [];
      tbody.innerHTML = list.length ? list.map(o => `<tr style="cursor:pointer" data-dn="${enc(o.dn)}">
        <td><b>📁 ${esc(o.ou)}</b></td><td class="muted tiny">${esc(o.dn)}</td></tr>`).join("")
        : `<tr><td colspan="2" class="empty">No child OUs</td></tr>`;
      tbody.querySelectorAll("tr[data-dn]").forEach(r => r.onclick = () => { path.push(r.dataset.dn); load(r.dataset.dn); });
    } catch (e) { tbody.innerHTML = `<tr><td colspan="2" class="empty">${esc(e.message)}</td></tr>`; }
  }
  load("");
}
function ViewAudit(v) {
  if (!App.state.is_admin) { v.innerHTML = '<div class="empty">Audit log is restricted to Domain Administrators.</div>'; return; }
  v.innerHTML = `
    <div class="toolbar"><button class="btn" id="aRefresh">↻ Refresh</button>
      <div class="spacer"></div><span class="muted tiny">All privileged actions are recorded here.</span></div>
    <div class="panel"><div class="panel-head"><h3>Audit trail</h3><div class="spacer"></div><span class="pill" id="aCount">…</span></div>
      <div class="table-wrap"><table class="data" id="aTable">
        <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Outcome</th></tr></thead>
        <tbody><tr><td colspan="5"><div class="loading"><span class="spinner"></span></div></td></tr></tbody>
      </table></div></div>`;
  const tbody = v.querySelector("#aTable tbody");
  async function load() {
    try { const out = await api("/api/audit?limit=200"); const list = out || [];
      v.querySelector("#aCount").textContent = list.length;
      tbody.innerHTML = list.length ? list.slice().reverse().map(r => {
        const oc = r.outcome === "success" ? "green" : (r.outcome === "denied" ? "red" : "amber");
        return `<tr><td class="muted tiny">${esc(r.ts)}</td><td><b>${esc(r.actor)}</b></td>
          <td><span class="pill blue">${esc(r.action)}</span></td>
          <td class="muted tiny">${esc(r.target || "—")}</td>
          <td><span class="pill ${oc}">${esc(r.outcome)}</span></td></tr>`;
      }).join("") : `<tr><td colspan="5" class="empty">No events yet</td></tr>`;
    } catch (e) { tbody.innerHTML = `<tr><td colspan="5" class="empty">${esc(e.message)}</td></tr>`; }
  }
  v.querySelector("#aRefresh").onclick = load;
  load();
}
function ViewAdmin(v) {
  if (!App.state.is_admin) { v.innerHTML = '<div class="empty">Administration is restricted to Domain Administrators.</div>'; return; }
  v.innerHTML = `
    <div class="grid stat-grid">
      <div class="card stat purple"><div class="ico">⚙</div><div class="label">Provisioning</div><div class="value">Create</div></div>
      <div class="card stat blue"><div class="ico">👤</div><div class="label">Users</div><div class="value"><a href="#" onclick="navGo('users')">Manage →</a></div></div>
      <div class="card stat green"><div class="ico">🛡</div><div class="label">Audit</div><div class="value"><a href="#" onclick="navGo('audit')">View →</a></div></div>
    </div>
    <div class="card" style="margin-top:16px">
      <h3>Create a new user</h3>
      <p class="muted">This panel is available only to Domain Admins. Use the form to provision an account in the chosen OU.</p>
      <button class="btn primary" onclick="showCreateUser()">➕ New user</button>
    </div>`;
}

function ViewWorkflows(v) {
  if (!App.state.is_admin) { v.innerHTML = '<div class="empty">Workflows are restricted to Domain Administrators.</div>'; return; }
  v.innerHTML = `
    <div class="card">
      <div class="card-head">
        <h3>Automation workflows</h3>
        <span class="pill amber" id="wfNote">All workflows are OFF by default</span>
      </div>
      <p class="muted" style="margin:0 0 16px">Enable only the automations you want. Each can be turned on/off here. Email workflows use the internal SMTP relay.</p>
      <div id="wfList"><div class="loading"><span class="spinner"></span></div></div>
    </div>`;
  loadWorkflows(v);
}

async function loadWorkflows(v) {
  const box = v.querySelector("#wfList");
  try {
    const wfs = await api("/api/workflows");
    if (!wfs || !wfs.length) { box.innerHTML = '<div class="empty">No workflows registered.</div>'; return; }
    const cats = {};
    wfs.forEach(w => { (cats[w.category] = cats[w.category] || []).push(w); });
    box.innerHTML = Object.entries(cats).map(([cat, items]) => `
      <div style="margin-bottom:18px">
        <div class="subtle" style="text-transform:uppercase;margin-bottom:10px">${esc(cat)}</div>
        ${items.map(w => `
          <div class="wf-row" style="display:flex;align-items:center;gap:14px;padding:14px;border:1px solid var(--border-soft);border-radius:12px;margin-bottom:10px;background:${w.enabled?'var(--surface-2)':'#fff'}">
            <div style="flex:1">
              <div style="font-weight:650;font-size:14.5px">${esc(w.name)}</div>
              <div class="muted tiny">${esc(w.description)}</div>
            </div>
            <label class="switch">
              <input type="checkbox" ${w.enabled?'checked':''} onchange="toggleWf('${w.id}', this.checked)">
              <span class="slider"></span>
            </label>
          </div>`).join('')}
      </div>`).join('') + `
      <div class="grid" style="grid-template-columns:1fr 1fr;gap:14px;margin-top:10px">
        <div class="card" style="background:var(--surface-2)">
          <h3>Run password-expiry reminders now</h3>
          <p class="muted tiny">Sends emails to users whose password expires in 7 or 3 days (if that workflow is enabled).</p>
          <button class="btn primary" onclick="runExpiry()">Send reminders</button>
        </div>
        <div class="card" style="background:var(--surface-2)">
          <h3>Email configuration</h3>
          <p class="muted tiny">Internal SMTP relay (no auth). Sender: donoreply@example.com (AEGISPASS PASSWORD RESET) · Admin alerts: Jhonattan.jimenez@example.com</p>
        </div>
      </div>`;
  } catch (e) {
    box.innerHTML = '<div class="empty">Could not load workflows.</div>';
  }
}

async function toggleWf(id, enabled) {
  try {
    await api("/api/workflows/" + id, { method: "POST", body: JSON.stringify({ enabled }) });
    toast("Workflow " + (enabled ? "enabled" : "disabled"), "", "ok");
  } catch (e) {
    toast("Failed to update workflow", e.message, "err");
  }
}

async function runExpiry() {
  try {
    const r = await api("/api/workflows/run-expiry", { method: "POST" });
    toast("Reminders sent", (r.sent || 0) + " email(s) dispatched", "ok");
  } catch (e) {
    toast("Failed", e.message, "err");
  }
}

function ViewEnroll(v) {
  if (!App.state.user) { v.innerHTML = '<div class="empty">Please sign in first.</div>'; return; }
  v.innerHTML = `
    <div class="card">
      <div class="card-head">
        <h3>Enrollment center</h3>
        <span class="pill blue" id="enrStatus">Loading…</span>
      </div>
      <p class="muted">Complete enrollment so you can recover your account and secure it with MFA. Your data is encrypted and stored in Active Directory.</p>
      <div class="steps" id="enrSteps" style="display:flex;gap:12px;flex-wrap:wrap;margin:14px 0 18px">
        <div class="step" data-step="1"><b>1</b> Recovery</div>
        <div class="step" data-step="2"><b>2</b> MFA (TOTP)</div>
        <div class="step" data-step="3"><b>3</b> Finish</div>
      </div>

      <!-- Step 1: recovery profile -->
      <div id="enrRecovery" class="enr-step">
        <h4>Recovery profile</h4>
        <label class="fld">Recovery email<input id="recEmail" type="email" class="form-control" placeholder="you@example.com"></label>
        <label class="fld">Mobile (SMS recovery, optional)<input id="recMobile" class="form-control" placeholder="+1…"></label>
        <label class="fld">Security question<input id="secQ" class="form-control" placeholder="What was your first school?"></label>
        <label class="fld">Security answer<input id="secA" class="form-control" placeholder="Answer"></label>
        <button class="btn primary" onclick="enrSaveRecovery()">Save recovery info</button>
      </div>

      <!-- Step 2: TOTP MFA -->
      <div id="enrTotp" class="enr-step" style="display:none">
        <h4>Multi-factor authentication</h4>
        <p class="muted tiny">Scan this QR code with Google Authenticator, Microsoft Authenticator, or any TOTP app, then enter the 6-digit code to confirm.</p>
        <div id="qrBox" style="text-align:center;padding:12px"><div class="loading"><span class="spinner"></span></div></div>
        <label class="fld">6-digit code<input id="totpCode" class="form-control" placeholder="123456" maxlength="6"></label>
        <button class="btn primary" onclick="enrVerifyTotp()">Confirm & enable MFA</button>
        <button class="btn ghost" onclick="enrSkipTotp()">Skip for now</button>
      </div>

      <!-- Step 3: finish -->
      <div id="enrDone" class="enr-step" style="display:none">
        <h4>Finish enrollment</h4>
        <p class="muted">Mark this device/account as enrolled to complete setup.</p>
        <label class="fld">Device label (optional)<input id="devLabel" class="form-control" placeholder="My laptop"></label>
        <button class="btn primary" onclick="enrFinish()">Complete enrollment</button>
      </div>
    </div>`;
  loadEnrStatus(v);
}

async function loadEnrStatus(v) {
  try {
    const s = await api("/api/enrollment/status");
    const badge = v.querySelector("#enrStatus");
    badge.textContent = s.enrolled ? "Enrolled ✓" : "Not enrolled";
    badge.className = "pill " + (s.enrolled ? "green" : "amber");
    if (s.has_recovery) v.querySelector("#enrRecovery").style.display = "none";
    if (s.mfa_enabled) v.querySelector("#enrTotp").style.display = "none";
    if (!s.has_recovery) showEnrStep(1);
    else if (!s.mfa_enabled) showEnrStep(2);
    else showEnrStep(3);
  } catch (e) {
    v.querySelector("#enrStatus").textContent = "error";
  }
}

function showEnrStep(n) {
  document.querySelectorAll(".enr-step").forEach(el => el.style.display = "none");
  const map = {1:"enrRecovery",2:"enrTotp",3:"enrDone"};
  const el = document.getElementById(map[n]);
  if (el) el.style.display = "";
  document.querySelectorAll(".step").forEach(s => s.classList.toggle("active", +s.dataset.step === n));
  if (n === 2) loadTotpQr();
}

async function enrSaveRecovery() {
  const body = {
    recovery_email: document.getElementById("recEmail").value,
    mobile: document.getElementById("recMobile").value,
    security_question: document.getElementById("secQ").value,
    security_answer: document.getElementById("secA").value,
  };
  try {
    await api("/api/enrollment/recovery", { method:"POST", body: JSON.stringify(body) });
    toast("Recovery info saved", "", "ok");
    showEnrStep(2);
  } catch (e) { toast("Save failed", e.message, "err"); }
}

let _totpSecret = "";
async function loadTotpQr() {
  const box = document.getElementById("qrBox");
  try {
    const r = await api("/api/enrollment/totp/setup", { method:"POST", body: JSON.stringify({label:"AegisPass:"+(App.state.user.sAMAccountName||"")}) });
    _totpSecret = r.secret;
    box.innerHTML = `<div style="display:flex;justify-content:center">${r.qr_svg}</div>
      <div class="muted tiny" style="margin-top:8px;text-align:center">Secret (manual): <code>${r.secret}</code></div>`;
  } catch (e) {
    box.innerHTML = '<div class="empty">Could not load QR.</div>';
  }
}

async function enrVerifyTotp() {
  const code = document.getElementById("totpCode").value;
  try {
    const r = await api("/api/enrollment/totp/verify", { method:"POST", body: JSON.stringify({secret:_totpSecret, code}) });
    if (r.verified) { toast("MFA enabled", "", "ok"); showEnrStep(3); }
    else toast("Invalid code", "Try again", "err");
  } catch (e) { toast("Verify failed", e.message, "err"); }
}

function enrSkipTotp() { showEnrStep(3); }

async function enrFinish() {
  const device = document.getElementById("devLabel").value;
  try {
    await api("/api/enrollment/account", { method:"POST", body: JSON.stringify({device}) });
    toast("Enrollment complete", "", "ok");
    document.getElementById("enrStatus").textContent = "Enrolled ✓";
    document.getElementById("enrStatus").className = "pill green";
  } catch (e) { toast("Failed", e.message, "err"); }
}

