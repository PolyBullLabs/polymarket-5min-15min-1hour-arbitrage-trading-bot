# block_follwers.py
import os, time, hmac, json, base64, hashlib, requests
from typing import List, Dict, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
FOLLOWERS_JSON = os.path.join(ROOT, "followers.json")
BASE_URL = "https://openapi.blockfin.com"

# -------- followers.json 로드 --------
def _load_followers() -> List[Dict]:
    try:
        arr = json.load(open(FOLLOWERS_JSON, "r", encoding="utf-8"))
        out=[]
        for it in arr:
            # id는 숫자/문자 상관없이 문자열로 보관
            out.append({
                "id": str(it.get("id") or ""),
                "name": it.get("name") or "",
                "key": it.get("key") or "",
                "secret": it.get("secret") or "",
                "passphrase": it.get("passphrase") or "",
            })
        return out
    except Exception as e:
        print(f"[WARN] followers.json 로드 실패: {e}")
        return []

def _pick_targets(follower_id: Optional[str]) -> List[Dict]:
    flw = _load_followers()
    if follower_id:
        return [f for f in flw if f.get("id")==str(follower_id)]
    return flw

# -------- Blockfin 시그니처 --------
def _sign(secret_key: str, method: str, path: str, body: Optional[dict]) -> Tuple[str,str,str]:
    # 서버측이 쓰는 방식: timestamp=ms, nonce=uuid or timestamp, body는 json 문자열
    # 여기선 method/path/body 모두 포함
    ts = str(int(time.time() * 1000))
    nonce = ts  # 간단히 timestamp 재사용
    body_str = json.dumps(body) if body else ""
    prehash = f"{path}{method.upper()}{ts}{nonce}{body_str}"
    hex_sig = hmac.new(secret_key.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    return base64.b64encode(hex_sig.encode()).decode(), ts, nonce

# -------- 포지션 조회(마진모드/청산사이드) --------
def _get_marginmode_and_close_side(f: Dict, inst_id: str) -> Tuple[Optional[str], Optional[str]]:
    path = f"/api/v1/account/positions?instId={inst_id}"
    sign, ts, nonce = _sign(f["secret"], "GET", path, None)
    headers = {
        "ACCESS-KEY": f["key"],
        "ACCESS-PASSPHRASE": f["passphrase"],
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-NONCE": nonce,
    }
    try:
        r = requests.get(BASE_URL+path, headers=headers, timeout=10)
        j = r.json()
    except Exception as e:
        print(f"[{f.get('name')}] [POS-NETERR] {e}")
        return None, None

    if j.get("code") != "0" or not j.get("data"):
        print(f"[{f.get('name')}] 포지션 조회 실패: {j}")
        return None, None

    pos = j["data"][0]
    margin_mode = pos.get("marginMode")
    try:
        # 거래소 응답에 따라 positions/position 어느 키든 수용
        size = float(pos.get("positions") or pos.get("position") or 0)
    except Exception:
        size = 0.0
    close_side = "sell" if size > 0 else "buy"
    return margin_mode, close_side

# -------- 주문/청산 --------
def place_order(inst_id: str, marginMode: str, side: str, orderType: str, price, size, follower_id: Optional[str]=None):
    targets = _pick_targets(follower_id)
    results=[]
    orderType = (orderType or "market").lower()
    side = (side or "").lower()
    price = "" if (orderType=="market" or price in (None, "", 0, "0")) else price
    body_base = {"instId": inst_id, "marginMode": marginMode, "orderType": orderType}

    for f in targets:
        if not (f["key"] and f["secret"] and f["passphrase"]):
            results.append({"id": f.get("id"), "name": f.get("name"), "error":"missing-keys"})
            continue

        body = {**body_base, "side": side, "price": price, "size": str(size)}
        path = "/api/v1/trade/order"
        sign, ts, nonce = _sign(f["secret"], "POST", path, body)
        headers = {
            "ACCESS-KEY": f["key"],
            "ACCESS-PASSPHRASE": f["passphrase"],
            "ACCESS-SIGN": sign, "ACCESS-TIMESTAMP": ts, "ACCESS-NONCE": nonce,
            "Content-Type": "application/json"
        }
        try:
            resp = requests.post(BASE_URL+path, headers=headers, json=body, timeout=10)
            results.append({"id": f.get("id"), "name": f.get("name"), "status": resp.status_code, "text": resp.text})
        except Exception as e:
            results.append({"id": f.get("id"), "name": f.get("name"), "error": str(e)})
    return results

def close_position(inst_id: str, size, follower_id: Optional[str]=None):
    targets = _pick_targets(follower_id)
    results=[]
    for f in targets:
        if not (f["key"] and f["secret"] and f["passphrase"]):
            results.append({"id": f.get("id"), "name": f.get("name"), "error":"missing-keys"})
            continue

        margin_mode, close_side = _get_marginmode_and_close_side(f, inst_id)
        if not margin_mode or not close_side:
            results.append({"id": f.get("id"), "name": f.get("name"), "error":"position-lookup-failed"})
            continue

        body = {
            "instId": inst_id, "marginMode": margin_mode,
            "side": close_side, "orderType": "market",
            "price": "", "size": str(size)
        }
        path = "/api/v1/trade/order"
        sign, ts, nonce = _sign(f["secret"], "POST", path, body)
        headers = {
            "ACCESS-KEY": f["key"],
            "ACCESS-PASSPHRASE": f["passphrase"],
            "ACCESS-SIGN": sign, "ACCESS-TIMESTAMP": ts, "ACCESS-NONCE": nonce,
            "Content-Type": "application/json"
        }
        try:
            resp = requests.post(BASE_URL+path, headers=headers, json=body, timeout=10)
            results.append({"id": f.get("id"), "name": f.get("name"), "status": resp.status_code, "text": resp.text})
        except Exception as e:
            results.append({"id": f.get("id"), "name": f.get("name"), "error": str(e)})
    return results
