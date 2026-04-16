"""
Resolve Polymarket market window from config: user-friendly market_window + market_interval_sec.
"""


def apply_market_window_settings(cfg: dict) -> None:
    """
    Mutates cfg in place: sets data_sources.polymarket.market_interval_sec.

    Priority:
    1. market_window: "5m" or "15m" (also accepts 5min, 15min, 5, 15)
    2. existing market_interval_sec (e.g. 300 or 900)
    3. default 900 (15m)
    """
    ds = cfg.get("data_sources")
    if not isinstance(ds, dict):
        return
    pm = ds.get("polymarket")
    if not isinstance(pm, dict):
        return

    mw = str(pm.get("market_window", "")).strip().lower()
    if mw in ("5m", "5min", "5"):
        pm["market_interval_sec"] = 300
        return
    if mw in ("15m", "15min", "15"):
        pm["market_interval_sec"] = 900
        return

    sec = pm.get("market_interval_sec")
    if sec is not None:
        try:
            pm["market_interval_sec"] = int(sec)
        except (TypeError, ValueError):
            pm["market_interval_sec"] = 900
        return

    pm["market_interval_sec"] = 900
