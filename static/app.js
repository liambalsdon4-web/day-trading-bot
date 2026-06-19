const POLL_MS = 5000;
let maxPositionHours = 4;

async function api(path, method = "GET") {
  const res = await fetch("/api" + path, { method });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function fmt(n, decimals = 2) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtMoney(n) {
  if (n == null) return "—";
  return "$" + fmt(n);
}

function fmtPct(n) {
  if (n == null) return "—";
  return (n >= 0 ? "+" : "") + (n * 100).toFixed(2) + "%";
}

function colourClass(n) {
  return n > 0 ? "pos" : n < 0 ? "neg" : "";
}

function fmtDuration(openedAt) {
  const mins = Math.floor((Date.now() - new Date(openedAt).getTime()) / 60000);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function timeColourClass(openedAt) {
  const hours = (Date.now() - new Date(openedAt).getTime()) / 3600000;
  const pct = hours / maxPositionHours;
  if (pct >= 0.9) return "time-danger";
  if (pct >= 0.65) return "time-warn";
  return "";
}

function renderPortfolio(p) {
  const dayPnl = document.getElementById("day-pnl");
  dayPnl.textContent = fmtMoney(p.day_pnl) + " (" + fmtPct(p.day_pnl_pct) + ")";
  dayPnl.className = "stat-value mono " + colourClass(p.day_pnl);

  const totalPnl = document.getElementById("total-pnl");
  totalPnl.textContent = fmtMoney(p.total_pnl) + " (" + fmtPct(p.total_pnl_pct) + ")";
  totalPnl.className = "stat-value mono " + colourClass(p.total_pnl);

  document.getElementById("total-value").textContent = fmtMoney(p.total_value);
  document.getElementById("cash").textContent = fmtMoney(p.cash);
  document.getElementById("positions-count").textContent = `${p.positions.length} / ${p.max_positions}`;
  document.getElementById("daily-loss").textContent =
    fmt(p.daily_loss_used_pct * 100, 2) + "% / " + fmt(p.daily_loss_limit_pct * 100, 2) + "%";
}

function renderPositions(positions) {
  const empty = document.getElementById("positions-empty");
  const cards = document.getElementById("positions-cards");

  if (!positions.length) {
    empty.classList.remove("hidden");
    cards.innerHTML = "";
    return;
  }
  empty.classList.add("hidden");

  cards.innerHTML = positions.map(p => `
    <div class="pos-card">
      <div class="pos-card-header">
        <div>
          <div class="pos-symbol">${p.symbol}</div>
          <div class="pos-type">${p.asset_class}</div>
        </div>
        <div class="pos-pnl">
          <div class="pos-pnl-value ${colourClass(p.unrealized_pnl)}">${fmtMoney(p.unrealized_pnl)}</div>
          <div class="pos-pnl-pct ${colourClass(p.unrealized_pnl)}">${fmtPct(p.unrealized_pnl_pct)}</div>
        </div>
      </div>
      <div class="pos-grid">
        <div class="pos-field">
          <div class="pos-field-label">Stake</div>
          <div class="pos-field-value">${fmtMoney(p.qty * p.entry_price)}</div>
        </div>
        <div class="pos-field">
          <div class="pos-field-label">Entry</div>
          <div class="pos-field-value">${fmtMoney(p.entry_price)}</div>
        </div>
        <div class="pos-field">
          <div class="pos-field-label">Current</div>
          <div class="pos-field-value">${fmtMoney(p.current_price)}</div>
        </div>
        <div class="pos-field">
          <div class="pos-field-label">Qty</div>
          <div class="pos-field-value">${fmt(p.qty, 6)}</div>
        </div>
        <div class="pos-field">
          <div class="pos-field-label">Time Open</div>
          <div class="pos-field-value ${timeColourClass(p.opened_at)}">${fmtDuration(p.opened_at)} / ${maxPositionHours}h</div>
        </div>
      </div>
      <div class="pos-levels">
        <div class="level-bar stop">
          <div class="level-bar-label">Stop Loss</div>
          <div class="level-bar-val">${fmtMoney(p.stop_loss_price)}</div>
        </div>
        <div class="level-bar tp">
          <div class="level-bar-label">Take Profit</div>
          <div class="level-bar-val">${fmtMoney(p.take_profit_price)}</div>
        </div>
      </div>
      <button class="close-btn" onclick="closePosition('${p.symbol}')">Close Position</button>
    </div>
  `).join("");
}

function renderSignals(signals) {
  const grid = document.getElementById("signals-grid");
  const empty = document.getElementById("signals-empty");

  if (!signals.length) {
    empty.classList.remove("hidden");
    grid.innerHTML = "";
    return;
  }
  empty.classList.add("hidden");

  grid.innerHTML = signals.map(s => {
    const bullW = Math.max(0, Math.min(100, s.bull_score));
    const bearW = Math.max(0, Math.min(100, s.bear_score));
    const cls = s.action === "BUY" ? "sig-buy" : s.action === "SELL" ? "sig-sell" : "sig-hold";

    const votesHtml = s.votes.map(v => `
      <div class="vote-row">
        <span class="vote-indicator">${v.indicator}</span>
        <span class="vote-${v.vote}">${v.vote.toUpperCase()} — ${v.reason}</span>
      </div>
    `).join("");

    return `
      <div class="signal-card ${cls}">
        <div class="signal-header">
          <span class="signal-symbol">${s.symbol}</span>
          <span class="signal-badge ${s.action}">${s.action}</span>
        </div>
        <div class="score-bars">
          <div class="score-bar-row">
            <span class="score-bar-label">Bull</span>
            <div class="score-bar-track"><div class="score-bar-fill bull" style="width:${bullW}%"></div></div>
          </div>
          <div class="score-bar-row">
            <span class="score-bar-label">Bear</span>
            <div class="score-bar-track"><div class="score-bar-fill bear" style="width:${bearW}%"></div></div>
          </div>
        </div>
        <div class="signal-meta">Net ${s.net_score > 0 ? "+" : ""}${s.net_score} &middot; Confidence ${(s.confidence * 100).toFixed(0)}%</div>
        <div class="votes">${votesHtml}</div>
      </div>
    `;
  }).join("");
}

function renderTrades(trades) {
  const empty = document.getElementById("trades-empty");
  const wrap = document.getElementById("trades-table-wrap");
  const tbody = document.getElementById("trades-body");

  if (!trades.length) {
    empty.classList.remove("hidden");
    wrap.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  wrap.classList.remove("hidden");

  tbody.innerHTML = trades.map(t => `
    <tr>
      <td class="time-cell">${new Date(t.timestamp).toLocaleString()}</td>
      <td class="symbol-cell">${t.symbol}</td>
      <td class="${t.side === "BUY" ? "side-buy" : "side-sell"}">${t.side}</td>
      <td>${fmt(t.qty, 4)}</td>
      <td>${fmtMoney(t.price)}</td>
      <td>${t.exit_price != null ? fmtMoney(t.exit_price) : "—"}</td>
      <td>${fmtMoney(t.total_value)}</td>
      <td class="${t.realized_pnl != null ? colourClass(t.realized_pnl) : ""}">${t.realized_pnl != null ? fmtMoney(t.realized_pnl) : "—"}</td>
      <td class="${t.signal_score != null ? colourClass(t.signal_score) : ""}">${t.signal_score != null ? (t.signal_score > 0 ? "+" : "") + fmt(t.signal_score, 1) : "—"}</td>
    </tr>
  `).join("");
}

function renderStatus(s) {
  const modePill = document.getElementById("mode-pill");
  document.getElementById("mode-badge").textContent = s.mode.toUpperCase();
  modePill.className = "pill " + s.mode;

  const botPill = document.getElementById("bot-pill");
  document.getElementById("bot-status").textContent = s.running ? "RUNNING" : "STOPPED";
  botPill.className = "pill " + (s.running ? "running" : "stopped");

  const mktPill = document.getElementById("market-pill");
  document.getElementById("market-status").textContent = s.market_open ? "MARKET OPEN" : "MARKET CLOSED";
  mktPill.className = "pill " + (s.market_open ? "open" : "closed");

  document.getElementById("last-tick").textContent = s.last_tick_at
    ? new Date(s.last_tick_at).toLocaleTimeString()
    : "—";

  const errSection = document.getElementById("errors-section");
  const errList = document.getElementById("errors-list");
  if (s.errors && s.errors.length) {
    errSection.classList.remove("hidden");
    errList.innerHTML = s.errors.map(e => `<li>${e}</li>`).join("");
  } else {
    errSection.classList.add("hidden");
  }
}

async function poll() {
  try {
    const data = await api("/dashboard");
    renderStatus(data.status);
    renderPortfolio(data.portfolio);
    renderPositions(data.portfolio.positions);
    renderSignals(data.recent_signals);
    renderTrades(data.recent_trades);
  } catch (e) {
    console.error("Poll error:", e);
  }
}

async function startBot() {
  await api("/bot/start", "POST");
  poll();
}

async function stopBot() {
  await api("/bot/stop", "POST");
  poll();
}

async function manualTick() {
  const btn = document.getElementById("btn-tick");
  btn.textContent = "Ticking…";
  try {
    await api("/bot/tick", "POST");
    await poll();
  } finally {
    btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Tick`;
  }
}

async function closePosition(symbol) {
  if (!confirm(`Force-close ${symbol}?`)) return;
  await fetch("/api/positions/" + encodeURIComponent(symbol), { method: "DELETE" });
  poll();
}

api("/config").then(cfg => { if (cfg.max_position_hours) maxPositionHours = cfg.max_position_hours; }).catch(() => {});
poll();
setInterval(poll, POLL_MS);
