#!/usr/bin/env python3
"""
Generate a modern, beautiful P&L chart from trading_log.json
"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
from datetime import datetime, timezone
from pathlib import Path

# ─── Load data ──────────────────────────────────────────────
data = json.load(open(Path(__file__).parent / "logs" / "trading_log.json"))
trades = data["trades"]
markets_seen = data.get("markets_seen", 0)

if not trades:
    print("No trades found.")
    exit()

# ─── Prepare arrays ─────────────────────────────────────────
timestamps = [datetime.fromtimestamp(t["timestamp"], tz=timezone.utc) for t in trades]
pnls = [t["pnl"] for t in trades]
cumulative = np.cumsum(pnls)
won = [t["won"] for t in trades]
tokens = [t["token_name"] for t in trades]
entries = [t["entry_price"] for t in trades]
exits = [t["exit_price"] for t in trades]
contracts = [t["contracts"] for t in trades]
labels = [f"#{i+1}" for i in range(len(trades))]

wins = sum(won)
losses = len(won) - wins
win_rate = wins / len(won) * 100 if won else 0
total_pnl = sum(pnls)
total_won_pnl = sum(p for p, w in zip(pnls, won) if w)
total_lost_pnl = sum(p for p, w in zip(pnls, won) if not w)
avg_win = total_won_pnl / wins if wins else 0
avg_loss = total_lost_pnl / losses if losses else 0
total_volume = sum(e * c for e, c in zip(entries, contracts))
best_trade = max(pnls)
worst_trade = min(pnls)

# ─── Dark theme ──────────────────────────────────────────────
BG = '#0d1117'
CARD_BG = '#161b22'
TEXT = '#e6edf3'
TEXT_DIM = '#8b949e'
GREEN = '#3fb950'
RED = '#f85149'
BLUE = '#58a6ff'
PURPLE = '#bc8cff'
ORANGE = '#d29922'
GRID = '#21262d'
ACCENT = '#1f6feb'

plt.rcParams.update({
    'figure.facecolor': BG,
    'axes.facecolor': CARD_BG,
    'axes.edgecolor': GRID,
    'axes.labelcolor': TEXT,
    'text.color': TEXT,
    'xtick.color': TEXT_DIM,
    'ytick.color': TEXT_DIM,
    'grid.color': GRID,
    'grid.alpha': 0.5,
    'font.family': 'monospace',
    'font.size': 11,
})

fig = plt.figure(figsize=(16, 10))
fig.patch.set_facecolor(BG)

# ─── Layout: top stats bar, main chart, bottom bars ──────────
gs = fig.add_gridspec(3, 1, height_ratios=[0.8, 3, 2], hspace=0.35,
                      left=0.08, right=0.95, top=0.92, bottom=0.06)

# ═══════════════════════════════════════════════════════════════
#  Title
# ═══════════════════════════════════════════════════════════════
pnl_color = GREEN if total_pnl >= 0 else RED
pnl_sign = "+" if total_pnl >= 0 else ""
fig.text(0.08, 0.96, "BTC 15m Live Trading", fontsize=22, fontweight='bold',
         color=TEXT, ha='left', va='center')
fig.text(0.08, 0.935, f"Session Performance  •  {len(trades)} trades  •  {markets_seen} markets observed",
         fontsize=10, color=TEXT_DIM, ha='left', va='center')

# ═══════════════════════════════════════════════════════════════
#  Stats cards (top row)
# ═══════════════════════════════════════════════════════════════
ax_stats = fig.add_subplot(gs[0])
ax_stats.set_xlim(0, 10)
ax_stats.set_ylim(0, 1)
ax_stats.axis('off')

cards = [
    ("Total P&L",      f"{pnl_sign}${total_pnl:.2f}",  pnl_color),
    ("Win Rate",        f"{win_rate:.1f}%",              GREEN if win_rate >= 50 else RED),
    ("Wins / Losses",   f"{wins}W / {losses}L",          BLUE),
    ("Avg Win",         f"+${avg_win:.2f}",              GREEN),
    ("Avg Loss",        f"${avg_loss:.2f}",              RED),
    ("Best Trade",      f"+${best_trade:.2f}",           GREEN),
    ("Worst Trade",     f"${worst_trade:.2f}",           RED),
    ("Volume",          f"${total_volume:.0f}",          PURPLE),
]

card_w = 10 / len(cards)
for i, (label, value, color) in enumerate(cards):
    cx = i * card_w + card_w / 2
    # Card background
    rect = FancyBboxPatch((i * card_w + 0.08, 0.05), card_w - 0.16, 0.9,
                          boxstyle="round,pad=0.05", facecolor=BG,
                          edgecolor=GRID, linewidth=1.2,
                          transform=ax_stats.transData)
    ax_stats.add_patch(rect)
    # Value
    ax_stats.text(cx, 0.6, value, fontsize=13, fontweight='bold',
                  color=color, ha='center', va='center')
    # Label
    ax_stats.text(cx, 0.25, label, fontsize=8, color=TEXT_DIM,
                  ha='center', va='center')

# ═══════════════════════════════════════════════════════════════
#  Cumulative P&L line chart (main)
# ═══════════════════════════════════════════════════════════════
ax1 = fig.add_subplot(gs[1])

x = np.arange(len(trades))
cum_with_zero = np.insert(cumulative, 0, 0)
x_with_zero = np.arange(-1, len(trades)) + 1

# Fill area under curve
for i in range(len(cum_with_zero) - 1):
    y0, y1 = cum_with_zero[i], cum_with_zero[i + 1]
    color = GREEN if y1 >= 0 else RED
    ax1.fill_between([i, i + 1], [y0, y1], alpha=0.08, color=color, zorder=1)

# Main line with gradient effect
ax1.plot(range(len(cum_with_zero)), cum_with_zero, color=BLUE, linewidth=2.5,
         zorder=3, solid_capstyle='round')

# Scatter points: green=win, red=loss
for i, (pnl, w) in enumerate(zip(pnls, won)):
    c = GREEN if w else RED
    marker = '▲' if w else '▼'
    size = 100 if w else 120
    ax1.scatter(i + 1, cumulative[i], color=c, s=size, zorder=5,
                edgecolors='white', linewidths=0.5, marker='o')
    # P&L annotation
    offset = 8 if pnl >= 0 else -14
    sign = "+" if pnl >= 0 else ""
    ax1.annotate(f"{sign}${pnl:.2f}", (i + 1, cumulative[i]),
                 textcoords="offset points", xytext=(0, offset),
                 fontsize=8, fontweight='bold', color=c, ha='center', zorder=6)

# Zero line
ax1.axhline(y=0, color=TEXT_DIM, linewidth=0.8, linestyle='--', alpha=0.5, zorder=2)

# Style
ax1.set_xlim(-0.3, len(trades) + 0.3)
y_margin = max(abs(cumulative.max()), abs(cumulative.min())) * 0.3
ax1.set_ylim(cumulative.min() - y_margin, cumulative.max() + y_margin)
ax1.set_ylabel("Cumulative P&L ($)", fontsize=11, fontweight='bold')
ax1.set_xticks(range(len(cum_with_zero)))
ax1.set_xticklabels(["Start"] + labels)
ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter('$%.1f'))
ax1.grid(True, alpha=0.3)
ax1.set_title("Equity Curve", fontsize=13, fontweight='bold', color=TEXT, pad=10, loc='left')

# ═══════════════════════════════════════════════════════════════
#  Per-trade P&L bars (bottom)
# ═══════════════════════════════════════════════════════════════
ax2 = fig.add_subplot(gs[2])

bar_colors = [GREEN if w else RED for w in won]
bars = ax2.bar(x, pnls, color=bar_colors, width=0.6, edgecolor=[
    GREEN if w else RED for w in won
], linewidth=0.8, alpha=0.85, zorder=3)

# Add glow effect
for i, (bar, w) in enumerate(zip(bars, won)):
    c = GREEN if w else RED
    ax2.bar(i, pnls[i], color=c, width=0.7, alpha=0.15, zorder=2)

# Labels on bars
for i, (pnl, w, tok, ct) in enumerate(zip(pnls, won, tokens, contracts)):
    sign = "+" if pnl >= 0 else ""
    y_off = pnl + (1.5 if pnl >= 0 else -2.5)
    ax2.text(i, y_off, f"{sign}${pnl:.2f}", fontsize=9, fontweight='bold',
             color=bar_colors[i], ha='center', va='bottom' if pnl >= 0 else 'top')
    # Token label below bar
    ax2.text(i, -0.5 if pnl >= 0 else 0.5,
             f"{tok}\n{ct}ct", fontsize=7, color=TEXT_DIM,
             ha='center', va='top' if pnl >= 0 else 'bottom')

ax2.axhline(y=0, color=TEXT_DIM, linewidth=0.8, linestyle='-', alpha=0.4, zorder=1)
ax2.set_xlim(-0.7, len(trades) - 0.3)
ax2.set_xticks(x)
ax2.set_xticklabels(labels)
ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter('$%.0f'))
ax2.grid(True, axis='y', alpha=0.3)
ax2.set_ylabel("Trade P&L ($)", fontsize=11, fontweight='bold')
ax2.set_title("Individual Trades", fontsize=13, fontweight='bold', color=TEXT, pad=10, loc='left')

# ─── Watermark ───────────────────────────────────────────────
fig.text(0.95, 0.96, datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
         fontsize=9, color=TEXT_DIM, ha='right', va='center')

# ─── Save ────────────────────────────────────────────────────
out_path = Path(__file__).parent / "logs" / "pnl_chart.png"
fig.savefig(out_path, dpi=180, facecolor=BG, bbox_inches='tight')
plt.close()
print(f"Chart saved: {out_path}")
