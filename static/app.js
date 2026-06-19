const POLL_MS = 5000;
let pollTimer = null;

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
  const pct = (n * 100).toFixed(2);
  return (n >= 0 ? "+" : "") + pct + "%";
}

function colourClass(n) {
  return n > 0 ? "pos" : n < 0 ? "neg" : "";
}

function renderPortfolio(p) {
  const dayPnl = document.getElementById("day-pnl");
  dayPnl.textContent = fmtMoney(p.day_pnl) + " (" + fmtPct(p.day_pnl_pct) + ")";
  dayPnl.className = "card-value " + colourClass(p.day_pnl);

  const totalPnl = document.getElementById("total-pnl");
  totalPnl.textContent = fmtMoney(p.total_pnl) + " (" + fmtPct(p.total_pnl_pct) + ")";
  totalPnl.className = "card-value " + colourClass(p.total_pnl);

  document.getElementById("total-value").textContent = fmtMoney(p.total_value);
  document.getElementById("cash").textContent = fmtMoney(p.cash);
  document.getElementById("positions-count").textContent = `${p.positions.length} / ${p.max_positions}`;
  document.getElementById("daily-loss").textContent = fmt(p.daily_loss_used_pct * 100, 2) + "% / " + fmt(p.daily_loss_limit_pct * 100, 2) + "%";
}

function renderPositions(positions) {
  const empty = document.getElementById("positions-empty");
  const table = document.getElementById("positions-table");
  const tbody = document.getElementById("positions-body");

  if (!positions.length) {
    empty.classList.remove("hidden");
    table.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  table.classList.remove("hidden");

  tbody.innerHTML = positions.map(p => `
    <tr>
      <td><strong>${p.symbol}</strong></td>
      <td>${p.asset_class}</td>
      <td>${fmt(p.qty, 6)}</td>
      <td>${fmtMoney(p.entry_price)}</td>
      <td>${fmtMoney(p.current_price)}</td>
      <td class="neg">${fmtMoney(p.stop_loss_price)}</td>
      <td class="pos">${fmtMoney(p.take_profit_price)}</td>
      <td class="${colourClass(p.unrealized_pnl)}">${fmtMoney(p.unrealized_pnl)} (${fmtPct(p.unrealized_pnl_pct)})</td>
      <td><button class="close-btn" onclick="closePosition('${p.symbol}')">Close</button></td>
    </tr>
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
    const votesHtml = s.votes.map(v => `
      <div class="vote-row">
        <span class="vote-${v.vote}">${v.indicator}</span>
        <span class="vote-${v.vote}">${v.vote.toUpperCase()} – ${v.reason}</span>
      </div>
    `).join("");
    return `
      <div class="signal-card">
        <div class="signal-header">
          <span class="signal-symbol">${s.symbol}</span>
          <span class="signal-action ${s.action}">${s.action}</span>
        </div>
        <div class="score-bar-wrap"><div class="score-bar bull" style="width:${bullW}%"></div></div>
        <div class="score-bar-wrap"><div class="score-bar bear" style="width:${bearW}%"></div></div>
        <div class="signal-meta">Net: ${s.net_score > 0 ? "+" : ""}${s.net_score} &bull; Conf: ${(s.confidence * 100).toFixed(0)}%</div>
        <div class="votes">${votesHtml}</div>
      </div>
    `;
  }).join("");
}

function renderTrades(trades) {
  const empty = document.getElementById("trades-empty");
  const table = document.getElementById("trades-table");
  const tbody = document.getElementById("trades-body");

  if (!trades.length) {
    empty.classList.remove("hidden");
    table.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  table.classList.remove("hidden");

  tbody.innerHTML = trades.map(t => `
    <tr>
      <td>${new Date(t.timestamp).toLocaleString()}</td>
      <td>${t.symbol}</td>
      <td class="${t.side === "BUY" ? "side-buy" : "side-sell"}">${t.side}</td>
      <td>${fmt(t.qty, 4)}</td>
      <td>${fmtMoney(t.price)}</td>
      <td>${fmtMoney(t.total_value)}</td>
      <td>${t.exit_price != null ? fmtMoney(t.exit_price) : "—"}</td>
      <td class="${t.realized_pnl != null ? colourClass(t.realized_pnl) : ""}">${t.realized_pnl != null ? fmtMoney(t.realized_pnl) : "—"}</td>
      <td>${t.signal_score != null ? (t.signal_score > 0 ? "+" : "") + fmt(t.signal_score, 1) : "—"}</td>
    </tr>
  `).join("");
}

function renderStatus(s) {
  const modeBadge = document.getElementById("mode-badge");
  modeBadge.textContent = s.mode.toUpperCase();
  modeBadge.className = "badge " + s.mode;

  const botBadge = document.getElementById("bot-status");
  botBadge.textContent = s.running ? "RUNNING" : "STOPPED";
  botBadge.className = "badge " + (s.running ? "green" : "grey");

  const mktBadge = document.getElementById("market-status");
  mktBadge.textContent = s.market_open ? "MARKET OPEN" : "MARKET CLOSED";
  mktBadge.className = "badge " + (s.market_open ? "green" : "orange");

  document.getElementById("last-tick").textContent = s.last_tick_at
    ? "Last tick: " + new Date(s.last_tick_at).toLocaleTimeString()
    : "Last tick: —";

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
  document.getElementById("btn-tick").textContent = "Ticking...";
  try {
    await api("/bot/tick", "POST");
    await poll();
  } finally {
    document.getElementById("btn-tick").textContent = "Tick Now";
  }
}

async function closePosition(symbol) {
  if (!confirm(`Force-close ${symbol}?`)) return;
  await fetch("/api/positions/" + encodeURIComponent(symbol), { method: "DELETE" });
  poll();
}

poll();
pollTimer = setInterval(poll, POLL_MS);
