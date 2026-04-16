"""
Local web dashboard: FastAPI + single-page UI, JSON at /api/state.
Runs in a daemon thread; state is updated from the bot's main loop.
"""

from __future__ import annotations

import logging
import math
import socket
import threading
import time
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, Response
import uvicorn

logger = logging.getLogger("btc_live")

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>BTC Live Bot</title>
  <style>
    :root {
      --bg: #0d1117; --panel: #161b22; --border: #30363d;
      --text: #e6edf3; --muted: #8b949e; --green: #3fb950; --red: #f85149;
      --yellow: #d29922; --blue: #58a6ff; --violet: #a371f7;
    }
    * { box-sizing: border-box; }
    body { font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text);
      margin: 0; padding: 1rem; line-height: 1.45; }
    h1 { font-size: 1.1rem; font-weight: 600; margin: 0 0 0.75rem; }
    .meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }
    .grid { display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 0.85rem; }
    .card h2 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted);
      margin: 0 0 0.5rem; }
    .row { display: flex; justify-content: space-between; gap: 0.5rem; font-size: 0.9rem; }
    .sig { font-size: 1rem; font-weight: 600; }
    .sig.wait { color: var(--yellow); }
    .sig.buy { color: var(--green); }
    .sig.block { color: var(--red); }
    .mono { font-family: ui-monospace, monospace; font-size: 0.82rem; }
    .btc { border-color: #d29922; }
    footer { margin-top: 1rem; color: var(--muted); font-size: 0.75rem; }
  </style>
</head>
<body>
  <h1>BTC up/down — live</h1>
  <div class="meta" id="meta">Loading…</div>
  <div class="grid">
    <div class="card"><h2>Session</h2><div id="session" class="mono"></div></div>
    <div class="card"><h2>Strategy</h2><div id="strategy"></div></div>
    <div class="card"><h2>UP</h2><div id="up" class="mono"></div></div>
    <div class="card"><h2>DOWN</h2><div id="down" class="mono"></div></div>
    <div class="card btc"><h2>BTC / USD (Chainlink)</h2><div id="btc" class="mono"></div></div>
    <div class="card"><h2>Trading</h2><div id="trading" class="mono"></div></div>
  </div>
  <footer>Refreshes every second · <span id="err"></span></footer>
  <script>
    /* No optional chaining (?.) — must run in older browsers / Edge legacy. */
    function esc(s) {
      if (s === null || s === undefined) return "";
      var el = document.createElement("div");
      el.textContent = String(s);
      return el.innerHTML;
    }
    function sigClass(t) {
      if (!t) return "wait";
      if (t.indexOf("BUY") >= 0) return "buy";
      /* Do not use \\uD83D\\uDEAB here: Python treats \\u.... in the template as escapes and emits invalid UTF-8 surrogates. */
      if (t.indexOf("NO ENTRY") >= 0) return "block";
      return "wait";
    }
    function numFmt(n, dec) {
      if (n === null || n === undefined || typeof n !== "number" || isNaN(n)) return "\u2014";
      return n.toFixed(dec);
    }
    function tick() {
      var errEl = document.getElementById("err");
      var r = new XMLHttpRequest();
      r.open("GET", "/api/state", true);
      r.onreadystatechange = function () {
        if (r.readyState !== 4) return;
        try {
          if (r.status !== 200) throw new Error("HTTP " + r.status);
          var d = JSON.parse(r.responseText);
          errEl.textContent = "";
          var hdr = d.header || {};
          var slug = hdr.slug != null ? String(hdr.slug) : "\u2014";
          var ts = "";
          if (d.ts) ts = new Date(d.ts * 1000).toISOString();
          document.getElementById("meta").innerHTML = esc(slug) + " \u00b7 " + esc(ts);
          document.getElementById("session").innerHTML = [
            "Timer: " + (hdr.time_left_sec != null ? esc(Math.floor(hdr.time_left_sec) + "s left") : "\u2014"),
            "WS: " + (hdr.ws_connected ? "live" : "disconnected"),
            "Mode: " + (hdr.simulation ? "simulation" : "real"),
          ].join("<br/>");
          var st = d.strategy || {};
          var sig = st.signal_text || "\u2014";
          function chk(x) { return x === true ? "\u2713" : x === false ? "\u2717" : "\u2014"; }
          var ck = st.checks || {};
          document.getElementById("strategy").innerHTML =
            '<div class="sig ' + sigClass(sig) + '">' + esc(sig) + "</div>" +
            '<div class="mono" style="margin-top:0.4rem">' +
            "Fav: " + esc(st.favorite) + " \u00b7 WR: " + esc(st.win_rate_str) + "<br/>" +
            "Checks: P=" + chk(ck.price) + " T=" + chk(ck.time) + " D=" + chk(ck.dev) +
            " M=" + chk(ck.mom) + " cutoff=" + chk(ck.time_cutoff) +
            "</div>";
          function book(x, id) {
            var el = document.getElementById(id);
            if (!x) { el.textContent = "No data"; return; }
            var bk = x.book || {};
            var ind = x.indicators || {};
            el.innerHTML = [
              "Last " + esc(bk.last_price),
              "Bid " + esc(bk.best_bid) + " / Ask " + esc(bk.best_ask),
              "VWAP " + numFmt(ind.vwap, 4) +
                " \u00b7 Dev " + (ind.deviation_pct != null ? numFmt(ind.deviation_pct, 2) + "%" : "\u2014"),
              "Z " + numFmt(ind.zscore, 2) +
                " \u00b7 Mom " + (ind.momentum_pct != null ? numFmt(ind.momentum_pct, 2) + "%" : "\u2014"),
              "Vol " + (bk.volume_total != null ? esc(Math.round(bk.volume_total)) : "\u2014"),
            ].join("<br/>");
          }
          book(d.up, "up");
          book(d.down, "down");
          var b = d.btc || {};
          var btcEl = document.getElementById("btc");
          if (b.btc_current_price > 0) {
            btcEl.innerHTML = [
              "$" + esc(numFmt(b.btc_current_price, 2)),
              "Anchor $" + (b.btc_anchor_price > 0 ? esc(numFmt(b.btc_anchor_price, 2)) : "\u2014"),
              esc(b.deviation_line || ""),
              "Feed: " + (b.btc_connected ? "ok" : "off") +
                (b.fresh_sec != null ? " \u00b7 " + Math.floor(b.fresh_sec) + "s" : ""),
            ].join("<br/>");
          } else {
            btcEl.textContent = "Waiting for Chainlink\u2026";
          }
          var tr = d.trading || {};
          var tHtml = "Markets " + esc(tr.markets_seen) + " \u00b7 Trades " + esc(tr.trade_count) +
            " \u00b7 PnL $" + (tr.total_pnl != null ? numFmt(tr.total_pnl, 2) : "\u2014") + "<br/>";
          if (tr.position) {
            var p = tr.position;
            tHtml += "LONG " + esc(p.token_name) + " @ " + esc(p.entry_price) +
              " \u00d7" + esc(p.contracts) + (p.hedged ? " hedged" : "") + "<br/>";
            tHtml += "Unreal $" + (p.unrealized_pnl != null ? numFmt(p.unrealized_pnl, 2) : "\u2014") + "<br/>";
          } else {
            tHtml += "No open position<br/>";
          }
          if (tr.recent_trades && tr.recent_trades.length) {
            var lines = [];
            for (var i = 0; i < tr.recent_trades.length; i++) {
              lines.push(esc(tr.recent_trades[i].line));
            }
            tHtml += "<br/>Recent:<br/>" + lines.join("<br/>");
          }
          document.getElementById("trading").innerHTML = tHtml;
        } catch (e) {
          errEl.textContent = "Poll error: " + (e && e.message ? e.message : e);
        }
      };
      r.onerror = function () {
        errEl.textContent = "Network error (is the bot running?)";
      };
      r.send();
    }
    tick();
    setInterval(tick, 1000);
  </script>
</body>
</html>
"""


def _sanitize_for_json(obj: Any) -> Any:
    """
    Starlette JSONResponse serializes with allow_nan=False; NaN/Inf break the ASGI handler.
    """
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


class WebSnapshotHolder:
    """Thread-safe snapshot for /api/state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {"status": "starting"}

    def set(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._data = dict(data)

    def get(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)


def build_app(holder: WebSnapshotHolder) -> FastAPI:
    app = FastAPI(title="BTC Live Bot", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _HTML

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/state")
    async def api_state():
        return JSONResponse(_sanitize_for_json(holder.get()))

    return app


def _client_probe_address(bind_host: str) -> str:
    """Address to test with socket.connect(); 0.0.0.0 / :: are not valid client targets."""
    if bind_host in ("0.0.0.0", ""):
        return "127.0.0.1"
    if bind_host in ("::", "[::]"):
        return "::1"
    return bind_host


def start_web_dashboard(host: str, port: int, holder: WebSnapshotHolder) -> bool:
    """
    Start uvicorn in a daemon thread. Returns True if the port accepts connections
    shortly after start (False if bind failed or port is in use).
    """
    app = build_app(holder)

    def run() -> None:
        try:
            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level="warning",
                access_log=False,
            )
        except Exception:
            logger.exception("Web dashboard: uvicorn exited with an error")

    t = threading.Thread(target=run, name="web-dashboard", daemon=True)
    t.start()

    probe = _client_probe_address(host)
    for _ in range(60):
        time.sleep(0.1)
        try:
            with socket.create_connection((probe, port), timeout=0.4):
                return True
        except OSError:
            continue
    return False
