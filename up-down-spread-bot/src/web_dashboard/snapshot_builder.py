"""
Build JSON-serializable dashboard snapshot from live trading objects.
"""
import time
from typing import Any, Dict, List, Optional


def build_snapshot(
    *,
    coins: List[str],
    strategy_base: str,
    multi_trader,
    data_feed,
    wallet_balance: Optional[float],
    config: Dict[str, Any],
    session_start_time: float,
    dry_run: bool,
    markets_skipped: Dict[str, int],
) -> Dict[str, Any]:
    now = time.time()
    uptime = now - session_start_time

    portfolio = multi_trader.get_portfolio_stats()

    coin_blocks: Dict[str, Any] = {}
    for coin in coins:
        trader_name = f"{strategy_base}_{coin}"
        st = data_feed.get_state(coin)
        trader = multi_trader.traders.get(trader_name)

        ms: Dict[str, Any] = {
            "market_slug": st.get("market_slug") or "",
            "seconds_till_end": int(st.get("seconds_till_end") or 0),
            "up_ask": float(st.get("up_ask") or 0),
            "down_ask": float(st.get("down_ask") or 0),
            "confidence": float(st.get("confidence") or 0),
            "price": float(st.get("price") or 0),
        }
        ua, da = ms["up_ask"], ms["down_ask"]
        ms["favorite"] = "UP" if ua > da else "DOWN"

        trading_cfg = config.get("trading", {}).get(coin, {})
        ms["trading_enabled"] = bool(trading_cfg.get("enabled", True))
        ms["trading_reason"] = trading_cfg.get("reason") or ""

        pos_detail = None
        if trader:
            perf = trader.get_performance_stats()
            pnl_coin = trader.current_capital - trader.starting_capital
            slug = ms["market_slug"]
            ms["stats"] = {
                "pnl": round(pnl_coin, 2),
                "total_trades": perf.get("total_trades", 0),
                "wins": perf.get("wins", 0),
                "losses": perf.get("losses", 0),
                "win_rate": round(perf.get("win_rate", 0), 2),
            }
            if slug:
                pos = multi_trader.get_current_positions(trader_name, slug)
                if pos and (pos.get("up_shares", 0) > 0 or pos.get("down_shares", 0) > 0):
                    detailed = trader.get_market_detailed_stats(slug, ua, da)
                    if detailed:
                        pos_detail = {
                            "up_shares": detailed.get("up_shares", 0),
                            "down_shares": detailed.get("down_shares", 0),
                            "up_invested": round(detailed.get("up_invested", 0), 2),
                            "down_invested": round(detailed.get("down_invested", 0), 2),
                            "total_invested": round(detailed.get("total_invested", 0), 2),
                            "unrealized_pnl": round(detailed.get("unrealized_pnl", 0), 2),
                            "unrealized_pct": round(detailed.get("unrealized_pct", 0), 2),
                            "max_drawdown": round(detailed.get("max_drawdown", 0), 2),
                            "entries_count": detailed.get("entries_count", 0),
                            "our_side": "UP"
                            if detailed.get("up_shares", 0) > detailed.get("down_shares", 0)
                            else "DOWN",
                        }
                        pos_detail["if_up_wins"] = round(
                            (pos_detail["up_shares"] * 1.0) - pos_detail["total_invested"], 2
                        )
                        pos_detail["if_down_wins"] = round(
                            (pos_detail["down_shares"] * 1.0) - pos_detail["total_invested"], 2
                        )
        else:
            ms["stats"] = None

        ms["position"] = pos_detail
        coin_blocks[coin] = ms

    recent: List[Dict[str, Any]] = []
    for name, tr in multi_trader.traders.items():
        closed = getattr(tr, "closed_trades", []) or []
        for trade in closed[-1:]:
            t = dict(trade)
            t["strategy"] = name
            recent.append(t)
    recent.sort(key=lambda x: x.get("close_time", 0), reverse=True)
    recent_trimmed = []
    for t in recent[:12]:
        recent_trimmed.append(
            {
                "strategy": t.get("strategy"),
                "market_slug": t.get("market_slug"),
                "pnl": round(float(t.get("pnl", 0)), 2),
                "winner": t.get("winner"),
                "close_time": t.get("close_time"),
            }
        )

    strat_cfg = config.get("strategy", {})
    safety_cfg = config.get("safety", {})
    exit_cfg = config.get("exit", {})
    pm = config.get("data_sources", {}).get("polymarket", {})
    market_interval_sec = int(pm.get("market_interval_sec", 900))

    return {
        "status": "running",
        "uptime_sec": round(uptime, 1),
        "session_start": session_start_time,
        "wallet_balance": round(wallet_balance, 2) if wallet_balance is not None else None,
        "dry_run": dry_run,
        "markets_skipped": dict(markets_skipped),
        "portfolio": {
            "total_capital": round(portfolio.get("total_capital", 0), 2),
            "total_pnl": round(portfolio.get("total_pnl", 0), 2),
            "portfolio_roi": round(portfolio.get("portfolio_roi", 0), 2),
            "total_trades": portfolio.get("total_trades", 0),
        },
        "market_interval_sec": market_interval_sec,
        "market_label": "5m" if market_interval_sec == 300 else ("15m" if market_interval_sec == 900 else f"{market_interval_sec}s"),
        "strategy_summary": {
            "entry_window_sec": strat_cfg.get("entry_window_sec"),
            "entry_frequency_sec": strat_cfg.get("entry_frequency_sec"),
            "min_confidence": strat_cfg.get("min_confidence"),
            "price_max": strat_cfg.get("price_max"),
            "max_spread": strat_cfg.get("max_spread"),
            "max_investment_per_market": strat_cfg.get("max_investment_per_market"),
            "sizing": strat_cfg.get("sizing", {}),
        },
        "safety_summary": {
            "max_order_size_usd": safety_cfg.get("max_order_size_usd"),
            "max_orders_per_minute": safety_cfg.get("max_orders_per_minute"),
            "max_total_investment": safety_cfg.get("max_total_investment"),
        },
        "flip_stop": exit_cfg.get("flip_stop", {}),
        "coins": coin_blocks,
        "recent_trades": recent_trimmed,
    }
