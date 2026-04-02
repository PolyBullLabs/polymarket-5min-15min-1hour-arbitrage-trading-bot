# positions_open_close_log.py
import os, time, json, requests
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

# ===== 고정 엔드포인트 =====
OAUTH_URL  = "https://p-api.bitruth.com/api/v1/oauth/token"
FAPI_BASE  = "https://f-api.bitruth.com/api/v1/"
CLIENT_ID  = 7

ROOT = os.path.dirname(os.path.abspath(__file__))
FOLLOWERS_JSON = os.path.join(ROOT, "followers.json")

# ===== 유틸 =====
def _compact(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}

def _load_followers() -> List[Dict[str, str]]:
    """
    followers.json 예시:
    [
      {"gmail":"user1@gmail.com","password":"pw1","client_secret":"xxxxx"},
      {"gmail":"user2@gmail.com","password":"pw2","client_secret":"yyyyy"}
    ]
    """
    try:
        with open(FOLLOWERS_JSON, "r", encoding="utf-8") as f:
            arr = json.load(f)
        out = []
        for it in arr:
            out.append({
                "username": str(it.get("gmail") or ""),
                "password": str(it.get("password") or ""),
                "client_secret": str(it.get("client_secret") or ""),
            })
        return [a for a in out if a["username"] and a["password"] and a["client_secret"]]
    except Exception:
        return []

@dataclass
class AuthInfo:
    username: str
    password: str
    client_secret: str

class BitruthClient:
    def __init__(self, auth: AuthInfo):
        self.auth = auth
        self.session = requests.Session()
        self._token: Optional[str] = None
        self._exp_ms: float = 0.0

    # ---- 토큰/요청 공통 ----
    def _auth_headers(self) -> Dict[str, str]:
        now = time.time() * 1000
        if (not self._token) or (self._exp_ms <= now):
            r = self.session.post(
                OAUTH_URL,
                json={
                    "client_id": CLIENT_ID,
                    "client_secret": self.auth.client_secret,
                    "grant_type": "password",
                    "scope": "*",
                    "username": self.auth.username,
                    "password": self.auth.password,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            r.raise_for_status()
            j = r.json()
            self._token = j["access_token"]
            self._exp_ms = now + (int(j.get("expires_in", 3600)) * 1000)
        return {"Accept": "application/json", "Authorization": f"Bearer {self._token}"}

    def _post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = FAPI_BASE + path.lstrip("/")
        r = self.session.post(url, json=body or {}, headers=self._auth_headers(), timeout=20)
        if not r.ok:
            print(f"[{self.auth.username}] [HTTP {r.status_code}] POST {url}")
            try: print("[RESP JSON]", r.json())
            except: print("[RESP TEXT]", r.text[:1000])
            r.raise_for_status()
        return r.json()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = FAPI_BASE + path.lstrip("/")
        r = self.session.get(url, params=params or {}, headers=self._auth_headers(), timeout=20)
        if not r.ok:
            print(f"[{self.auth.username}] [HTTP {r.status_code}] GET {url}")
            print(r.text[:1000])
            r.raise_for_status()
        return r.json()

    # ---- 인스트루먼트/마진 ----
    def get_instrument_id(self, symbol: str, contract_type: str = "USD_M") -> Optional[int]:
        j = self._get("instruments")
        data = j.get("data") or []
        for it in data:
            if str(it.get("symbol")) == symbol and str(it.get("contractType", "USD_M")) == contract_type:
                try:
                    return int(it.get("id"))
                except:
                    pass
        print(f"[{self.auth.username}] [WARN] instrumentId not found for {symbol}/{contract_type}")
        return None

    def set_margin_mode(self, symbol: str, margin_mode: str = "CROSS",
                        leverage: Union[int, str] = 5, contract_type: str = "USD_M") -> Optional[Dict[str, Any]]:
        inst_id = self.get_instrument_id(symbol, contract_type)
        if inst_id is None:
            print(f"[{self.auth.username}] [ERROR] instrumentId not found → skip marginMode set")
            return None
        body = {"instrumentId": inst_id, "marginMode": str(margin_mode).upper(), "leverage": str(leverage)}
        print(f"[{self.auth.username}] [MARGIN SET] {body}")
        try:
            res = self._post("/marginMode", body)
            print(f"[{self.auth.username}] [MARGIN RES]", res)
            return res
        except Exception as e:
            print(f"[{self.auth.username}] [MARGIN WARN] set fail → {e} (continue)")
            return None

    def get_margin_mode(self, symbol: str, contract_type: str = "USD_M") -> Dict[str, Any]:
        inst_id = self.get_instrument_id(symbol, contract_type)
        if inst_id is None:
            raise ValueError(f"[{self.auth.username}] instrumentId not found for {symbol}/{contract_type}")
        res = self._get("marginMode", params={"instrumentId": str(inst_id)})
        print(f"[{self.auth.username}] [MARGIN GET] {res}")
        return res

    # ---- 주문/포지션 ----
    def order(self, side: str, symbol: str, quantity: Union[float, str],
              is_market: bool = True, price: Optional[float] = None,
              margin_mode: str = "CROSS", leverage: Union[int, str] = 5,
              contract_type: str = "USD_M") -> Dict[str, Any]:

        # 필요 시 마진/레버리지 맞추기
        self.set_margin_mode(symbol, margin_mode, leverage, contract_type)

        body = {
            "side": side.upper(),                   # "BUY" / "SELL"
            "contractType": contract_type,          # "USD_M"
            "symbol": symbol,
            "type": "MARKET" if is_market else "LIMIT",
            "quantity": str(quantity),
            "price": None if is_market else (str(price) if price is not None else None),
            "timeInForce": "GTC",
            "asset": "USDT",
            "tpSLType": "",
            "isPostOnly": False,
        }
        body = _compact(body)
        print(f"[{self.auth.username}] [ORDER] {body}")
        res = self._post("/order", body)
        print(f"[{self.auth.username}] [ORDER RES]", res)
        return res

    def fetch_positions(self, symbol: Optional[str] = None,
                        side: Optional[str] = None,
                        contract_type: str = "USD_M",
                        page: int = 1, size: int = 500) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"page": page, "size": size, "contractType": contract_type}
        if symbol:
            params["symbol"] = symbol
        res = self._get("positions", params=params)
        items: List[Dict[str, Any]] = res.get("data", []) or []
        if side:
            s = side.upper()
            items = [p for p in items
                     if str(p.get("side", "")).upper() == s
                     or str(p.get("positionSide", "")).upper() == s]
        return items

    def close_position(self, quantity: Union[float, str],
                       symbol: Optional[str] = None,
                       side: Optional[str] = None,
                       contract_type: str = "USD_M") -> Dict[str, Any]:
        pos_list = self.fetch_positions(symbol=symbol, side=side, contract_type=contract_type)
        if not pos_list:
            raise ValueError(f"[{self.auth.username}] No open position (symbol={symbol}, side={side}, ct={contract_type})")
        first = pos_list[0]
        pid = first.get("id") or first.get("positionId")
        body: Dict[str, Any] = {
            "positionId": int(pid),
            "quantity": str(quantity),
            "type": "MARKET",
        }
        print(f"[{self.auth.username}] [CLOSE] {body}")
        res = self._post("/positions/close", body)
        print(f"[{self.auth.username}] [CLOSE RES]", res)
        return res

# ===== 클라이언트 로딩 (여러 계정) =====
def load_clients() -> List[BitruthClient]:
    followers = _load_followers()
    clients: List[BitruthClient] = []

    if followers:
        for f in followers:
            auth = AuthInfo(username=f["username"], password=f["password"], client_secret=f["client_secret"])
            clients.append(BitruthClient(auth))
        return clients

    # followers.json 없으면 환경변수 1계정 사용 (백워드 호환)
    env_secret = os.getenv("BITURUS_SECRIT")
    env_user   = os.getenv("GMAIL")
    env_pass   = os.getenv("PASS")
    if env_secret and env_user and env_pass:
        clients.append(BitruthClient(AuthInfo(env_user, env_pass, env_secret)))
        return clients

    raise SystemExit("followers.json 이 비었고 환경변수(BITURUS_SECRIT/GMAIL/PASS)도 없습니다.")

# ===== 브로드캐스트 헬퍼 =====
def order_all(symbol: str, quantity: Union[float, str], *,
              side: str = "BUY",
              is_market: bool = True,
              price: Optional[float] = None,
              margin_mode: str = "CROSS",
              leverage: Union[int, str] = 5,
              contract_type: str = "USD_M") -> List[Dict[str, Any]]:
    results = []
    for cli in load_clients():
        try:
            r = cli.order(side=side, symbol=symbol, quantity=quantity,
                          is_market=is_market, price=price,
                          margin_mode=margin_mode, leverage=leverage,
                          contract_type=contract_type)
            results.append({"user": cli.auth.username, "ok": True, "res": r})
        except Exception as e:
            results.append({"user": cli.auth.username, "ok": False, "error": str(e)})
    return results

def close_position_all(quantity: Union[float, str], *,
                       symbol: Optional[str] = None,
                       side: Optional[str] = None,
                       contract_type: str = "USD_M") -> List[Dict[str, Any]]:
    results = []
    for cli in load_clients():
        try:
            r = cli.close_position(quantity=quantity, symbol=symbol, side=side, contract_type=contract_type)
            results.append({"user": cli.auth.username, "ok": True, "res": r})
        except Exception as e:
            results.append({"user": cli.auth.username, "ok": False, "error": str(e)})
    return results

# ===== 예시 실행 =====
if __name__ == "__main__":
    # 1) 여러 계정에 동시에 주문 예시
    # print(order_all(symbol="ETHUSDT", quantity=0.00339516,
    #                 side="BUY", is_market=True,
    #                 margin_mode="ISOLATED", leverage="3"))

    # 2) 여러 계정에 동시에 포지션 청산 예시
    print(close_position_all(symbol="ETHUSDT", quantity=0.0028820175))
