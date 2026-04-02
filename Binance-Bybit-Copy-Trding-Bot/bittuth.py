# positions_open_close_log.py
import os, time, json, requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from bittus_follower import order_all,close_position_all
load_dotenv(dotenv_path=".env", override=True)

# ===== 고정 엔드포인트/인증 (변경 금지) =====
OAUTH_URL  = "https://p-api.bitruth.com/api/v1/oauth/token"
FAPI_BASE  = "https://f-api.bitruth.com/api/v1/"
CLIENT_ID     = 7
CLIENT_SECRET = os.getenv("BITURUS_SECRIT")
USERNAME      = os.getenv("GMAIL")
PASSWORD      = os.getenv("PASS")
if not (CLIENT_SECRET and USERNAME and PASSWORD):
    raise SystemExit("환경변수 CLIENT_SECRET(BITURUS_SECRIT), GMAIL, PASS 설정 필요")

POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.8"))
SYM_FILTER    = os.getenv("SYM")  # 예: ETHUSDT, 없으면 전체

SESSION = requests.Session()
_token: Optional[str] = None
_exp_ms: float = 0.0

# ===== 공통 =====
def _auth_headers() -> Dict[str, str]:
    global _token, _exp_ms
    now = time.time() * 1000
    if not _token or _exp_ms <= now:
        r = SESSION.post(
            OAUTH_URL,
            json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "password",
                "scope": "*",
                "username": USERNAME,
                "password": PASSWORD,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        j = r.json()
        _token  = j["access_token"]
        _exp_ms = now + int(j.get("expires_in", 3600)) * 1000
    return {"Accept": "application/json", "Authorization": f"Bearer {_token}"}

def get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = FAPI_BASE + path.lstrip("/")
    r = SESSION.get(url, params=params or {}, headers=_auth_headers(), timeout=15)
    r.raise_for_status()
    return r.json()

# ===== 유틸 =====
def _f(v) -> float:
    try:
        if v is None: return 0.0
        return float(v)
    except Exception:
        return 0.0

def _ts_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def side_from_qty(q) -> str:
    v = _f(q)
    return "LONG" if v > 0 else ("SHORT" if v < 0 else "FLAT")

def side_send(q) -> str:
    v = _f(q)
    return "BUY" if v > 0 else ("SELL" if v < 0 else "FLAT")


def fetch_positions(symbol: Optional[str] = None, page: int = 1, size: int = 500) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"page": page, "size": size}
    if symbol:
        params["symbol"] = symbol
    res = get_json("positions", params=params)
    return res.get("data", []) or []

def pos_key(p: Dict[str, Any]) -> str:
    """
    포지션을 유일하게 식별할 키.
    id가 있으면 id, 없으면 (accountId|symbol|contractType)
    """
    pid = p.get("id")
    if pid is not None:
        return f"PID:{pid}"
    return f"ACC:{p.get('accountId')}|SYM:{p.get('symbol')}|CT:{p.get('contractType')}"

def get_instrument_id(symbol: str, contract_type: str = "USD_M") -> Optional[int]:
    j = get_json("instruments")
    data = j.get("data") or []
    for it in data:
        if str(it.get("symbol")) == symbol and str(it.get("contractType", "USD_M")) == contract_type:
            try:
                return int(it.get("id"))
            except Exception:
                pass
    print(f"[WARN] instrumentId not found for symbol={symbol} contractType={contract_type}")
    return None

def get_margin_mode(symbol: str, contract_type: str = "USD_M") -> Dict[str, Any]:
    """GET /api/v1/marginMode?instrumentId=... 로 현재 마진 모드/레버리지 조회"""
    inst_id = get_instrument_id(symbol, contract_type)
    if inst_id is None:
        raise ValueError(f"instrumentId not found for {symbol}/{contract_type}")
    params = {"instrumentId": inst_id}
    print("[MARGIN GET] params", params)
    res = get_json("marginMode", params=params)
    print("[MARGIN GET RES]", res)
    return res
# ===== 메인: 진입 + 청산 감지 =====
if __name__ == "__main__":
    prev: Dict[str, Dict[str, Any]] = {}
    seeded = False

    try:
        while True:
            # 현재 스냅샷 수집
            try:
                cur_list = fetch_positions(symbol=SYM_FILTER)
                
            except requests.HTTPError as e:
                msg = e.response.text[:300] if e.response is not None else str(e)
                print(json.dumps({"error": "HTTP_POS", "msg": msg}, ensure_ascii=False), flush=True)
                time.sleep(POLL_INTERVAL); continue
            except Exception as e:
                print(json.dumps({"error": "GEN_POS", "msg": str(e)[:300]}, ensure_ascii=False), flush=True)
                time.sleep(POLL_INTERVAL); continue

            cur: Dict[str, Dict[str, Any]] = {pos_key(p): p for p in cur_list}

            # 최초 루프: 현재 상태로 시드만 하고 알림은 생략
            if not seeded:
                prev = cur
                seeded = True
                time.sleep(POLL_INTERVAL)
                continue
            EPS = float(os.getenv("QTY_EPS", "1e-10"))
            # ---- (1) 청산 감지: 이전엔 있었는데 지금 목록에서 사라짐 ----
            # ---- (2.5) 부분 변경 감지: 수량 감소/증가, 그리고 방향 전환까지 처리 ----
            for k, nowp in cur.items():
                now_qty = _f(nowp.get("currentQty"))
                if k not in prev:
                    continue
                was = prev[k]; was_qty = _f(was.get("currentQty"))

                # 둘 다 포지션이 살아있고(0이 아님), 같은 방향(부호 동일)일 때
                if abs(was_qty) > 0 and abs(now_qty) > 0 and (was_qty * now_qty) > 0:
                    # (a) 수량 감소 → 부분 청산
                    if abs(now_qty) + EPS < abs(was_qty):
                        delta = abs(was_qty) - abs(now_qty)  # 줄어든 만큼
                        evt = {
                            "event":        "POSITION_PARTIALLY_CLOSED",
                            "symbol":       nowp.get("symbol"),
                            "contractType": nowp.get("contractType"),
                            "side":         side_from_qty(was_qty),
                            "closedQty":    delta,
                            "entryPrice":   _f(was.get("entryPrice")),
                            "avgClosePrice": _f(nowp.get("avgClosePrice")),
                            "leverage":     nowp.get("leverage"),
                            "positionId":   nowp.get("id"),
                            "closedAt":     nowp.get("updatedAt") or _ts_iso(),
                        }
                        print(json.dumps(evt, ensure_ascii=False), flush=True)
                        print(f"[LOG] {evt['symbol']} {evt['side']} 부분 청산 {evt['closedQty']}", flush=True)

                        print("[CALL] close_position_all partial", evt["symbol"], delta)
                        try:
                            close_position_all(
                                quantity=delta,
                                symbol=evt["symbol"],
                                side=evt["side"],  # LONG/SHORT 그대로 넘김
                                contract_type=evt["contractType"],
                            )
                        except Exception as e:
                            print("[ERR] close_position_all partial:", e)

                    # (b) 수량 증가 → 부분 진입(증액)
                    elif abs(now_qty) > abs(was_qty) + EPS:
                        delta = abs(now_qty) - abs(was_qty)  # 늘어난 만큼
                        # 마진모드/레버리지는 마스터 현재 설정을 조회해 반영
                        try:
                            margin = get_margin_mode(symbol=nowp.get("symbol"), contract_type=nowp.get("contractType"))
                            data = margin.get("data") or {}
                            mode = str(data.get("marginMode") or data.get("mode") or "").upper()
                        except Exception:
                            mode = "CROSS"

                        evt = {
                            "event":        "POSITION_SCALED_IN",
                            "symbol":       nowp.get("symbol"),
                            "contractType": nowp.get("contractType"),
                            "side":         side_from_qty(now_qty),
                            "addedQty":     delta,
                            "entryPrice":   _f(nowp.get("entryPrice")),
                            "leverage":     nowp.get("leverage"),
                            "positionId":   nowp.get("id"),
                            "openedAt":     nowp.get("lastOpenTime") or nowp.get("createdAt") or _ts_iso(),
                        }
                        print(json.dumps(evt, ensure_ascii=False), flush=True)
                        print(f"[LOG] {evt['symbol']} {evt['side']} 증액 {evt['addedQty']}", flush=True)

                        order_all(
                            symbol=nowp.get("symbol"),
                            quantity=delta,
                            side=side_send(now_qty),      # BUY or SELL
                            is_market=True,
                            price=None,                    # 마켓이면 가격 제거
                            margin_mode=mode,
                            leverage=nowp.get("leverage"),
                            contract_type=nowp.get("contractType", "USD_M")
                        )

                # (c) 방향 전환: 부호가 바뀌었는데 중간에 0을 찍지 않고 바로 반대로 된 경우
                elif abs(was_qty) > 0 and abs(now_qty) > 0 and (was_qty * now_qty) < 0:
                    # 1) 기존 방향 물량 전부 청산
                    close_position_all(
                        quantity=abs(was_qty),
                        symbol=nowp.get("symbol"),
                        side=side_from_qty(was_qty),
                        contract_type=nowp.get("contractType")
                    )
                    # 2) 새 방향으로 now_qty 만큼 진입
                    try:
                        margin = get_margin_mode(symbol=nowp.get("symbol"), contract_type=nowp.get("contractType"))
                        data = margin.get("data") or {}
                        mode = str(data.get("marginMode") or data.get("mode") or "").upper()
                    except Exception:
                        mode = "CROSS"

                    order_all(
                        symbol=nowp.get("symbol"),
                        quantity=abs(now_qty),
                        side=side_send(now_qty),
                        is_market=True,
                        price=None,
                        margin_mode=mode,
                        leverage=nowp.get("leverage"),
                        contract_type=nowp.get("contractType", "USD_M")
                    )

                    print(json.dumps(evt, ensure_ascii=False), flush=True)
                    print(f"[LOG] {evt['symbol']} {evt['side']} {evt['qty']} 진입 (entry={evt['entryPrice']})", flush=True)

            # 스냅샷 교체
            prev = cur
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
