# server.py (v1.7 - SSH CURL only, no follower server needed)
import os, sys, json, time, hmac, base64, hashlib, asyncio, websockets
from typing import List, Dict, Tuple, Optional
import uvicorn, requests, subprocess, shlex, shutil
from dataclasses import dataclass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ====== 운영 스위치 ======
USE_DIRECT = False            # 마스터가 직접 주문(로컬에서 REST) => False 유지
FORWARD_MODE = "ssh_curl"     # 원격에서 curl 호출 (팔로워 서버/터널 불필요)

# ---------- Paths ----------
def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

ROOT = app_dir()
ENV_PATH = os.path.join(ROOT, ".block.env")
AUTH_PATH = os.path.join(ROOT, ".auth.env")
FOLLOWERS_JSON = os.path.join(ROOT, "followers.json")   # [{id,name,key,secret,passphrase}]
SERVERS_JSON = os.path.join(ROOT, "servers.json")       # [{"name","host","port","user","auth":{"type":"pem","keyPath":...},"python":"/usr/bin/python3"}]
SSH_BIN = os.environ.get("SSH_BIN", "ssh")
STATIC_DIR = os.path.join(ROOT, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

BASE_URL = "https://openapi.blockfin.com"   # Blockfin REST base

# ---------- ENV helpers ----------
def ensure_env():
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("MASTER_API_KEY_BLO=\nMASTER_API_SECRET_BLO=\npassphrase=\n")

def ensure_auth_env():
    if not os.path.exists(AUTH_PATH):
        with open(AUTH_PATH, "w", encoding="utf-8") as f:
            f.write("ADMIN_USERNAME=admin\nADMIN_PASSWORD=1234\n")

def load_env():
    ensure_env()
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    return (
        os.getenv("MASTER_API_KEY_BLO") or "",
        os.getenv("MASTER_API_SECRET_BLO") or "",
        os.getenv("passphrase") or "",
    )

def load_auth():
    ensure_auth_env()
    load_dotenv(dotenv_path=AUTH_PATH, override=True)
    return os.getenv("ADMIN_USERNAME") or "", os.getenv("ADMIN_PASSWORD") or ""

def save_env(master_key: str, master_secret: str, passphrase: str):
    existing = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    existing[k] = v
    existing["MASTER_API_KEY_BLO"] = (master_key or "").strip()
    existing["MASTER_API_SECRET_BLO"] = (master_secret or "").strip()
    existing["passphrase"] = (passphrase or "").strip()
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

# ---------- Followers (followers.json) ----------
def load_followers_config() -> List[Dict]:
    if not os.path.exists(FOLLOWERS_JSON):
        return []
    try:
        arr = json.load(open(FOLLOWERS_JSON, "r", encoding="utf-8"))
        out=[]
        for it in arr:
            out.append({
                "id": str(it.get("id") or ""),
                "name": it.get("name",""),
                "key": it.get("key",""),
                "secret": it.get("secret",""),
                "passphrase": it.get("passphrase",""),
            })
        return out
    except Exception:
        return []

def save_followers_config(text: str):
    data = json.loads(text) if (text or "").strip() else []
    if not isinstance(data, list):
        raise ValueError("followers.json must be an array")
    for it in data:
        if not isinstance(it, dict):
            raise ValueError("Each follower must be an object")
    with open(FOLLOWERS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- Servers (servers.json) ----------
def ensure_servers_config():
    if not os.path.exists(SERVERS_JSON):
        with open(SERVERS_JSON, "w", encoding="utf-8") as f:
            f.write('{"servers": []}')

def load_servers_config() -> Dict:
    ensure_servers_config()
    try:
        return json.load(open(SERVERS_JSON, "r", encoding="utf-8"))
    except Exception:
        return {"servers": []}

@dataclass
class SshServer:
    name: str
    host: str
    port: int
    user: str
    keyPath: Optional[str]

def _fix_key_perms_windows(p: str):
    try:
        subprocess.run(["icacls", p, "/inheritance:r"], check=False, capture_output=True)
        subprocess.run(["icacls", p, "/grant:r", f"{os.getlogin()}:R"], check=False, capture_output=True)
    except Exception:
        pass

def _sq(s: str) -> str:
    """단일 인자로 bash -lc 에 안전하게 넘기기 위한 single-quote escape"""
    return "'" + s.replace("'", "'\"'\"'") + "'"

def _ssh_exec(server: Dict, remote_cmd: str, timeout: int = 25) -> Tuple[int, str, str]:
    host = server["host"]
    user = server.get("user", "ubuntu")
    port = int(server.get("port") or 22)
    auth = server.get("auth", {})
    key_path = auth.get("keyPath")

    cmd: list[str] = [
        SSH_BIN, "-p", str(port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
    ]
    if auth.get("type") == "pem" and key_path:
        if os.name == "nt":
            _fix_key_perms_windows(key_path)
        cmd += ["-i", key_path]

    dest = f"{user}@{host}"
    cmd += [dest, "bash", "-lc", _sq(remote_cmd)]

    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = p.stdout.decode(errors="ignore")
        err = p.stderr.decode(errors="ignore")
        safe_cmd = " ".join([c if c != key_path else "<PEM>" for c in cmd])
        print(f"[SSH] cmd: {safe_cmd}  rc={p.returncode}")
        if err.strip():
            print(f"[SSH] stderr: {err[:1200]}")
        return p.returncode, out, err
    except Exception as e:
        print(f"[SSH] exec error: {e}")
        return 255, "", str(e)

# ---------- HMAC (Blockfin spec: base64(hexdigest)) ----------
def _bf_sign(secret_key: str, method: str, path: str, body: Optional[dict]) -> Tuple[str, str, str]:
    ts = str(int(time.time() * 1000))
    nonce = ts
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body else ""
    prehash = f"{path}{method.upper()}{ts}{nonce}{body_str}"
    hex_sig = hmac.new(secret_key.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    sign = base64.b64encode(hex_sig.encode()).decode()
    return sign, ts, nonce

# ---------- Remote curl helpers ----------
def _ssh_curl(server: Dict, method: str, path: str, headers: Dict[str,str], body: Optional[dict], timeout: int = 25) -> Tuple[int, str]:
    url = f"{BASE_URL}{path}"
    # body
    data_raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body else ""
    data_escaped = shlex.quote(data_raw)
    # headers
    hdrs = " ".join([f"-H {shlex.quote(k+': '+v)}" for k,v in headers.items()])
    # method & data flags
    if method.upper() == "GET":
        data_part = ""
        mflag = "-X GET"
    else:
        data_part = f"-d @-"
        mflag = f"-X {method.upper()}"

    cmd = (
        (f"echo {data_escaped} | " if data_part else "") +
        f"curl -sS {mflag} -w ' HTTPSTATUS:%{{http_code}}' {hdrs} " +
        (data_part + " " if data_part else "") +
        shlex.quote(url)
    )
    rc, out, err = _ssh_exec(server, cmd, timeout=timeout)
    if rc != 0:
        return 0, f"ssh-exec-failed: {err or out}"
    if "HTTPSTATUS:" in out:
        text, _, status = out.rpartition(" HTTPSTATUS:")
        try:
            st = int(status.strip())
        except:
            st = 0
        print(f"[SSH CURL] {method} {path}  status={st}  len={len(text.strip())}")
        return st, text
    return 0, out

# ---------- Business: place/close through SSH curl ----------
def _list_pairs_followers_servers() -> List[Tuple[Dict, Dict]]:
    followers = load_followers_config()
    servers = load_servers_config().get("servers", [])
    pairs: List[Tuple[Dict, Dict]] = []
    if not followers or not servers:
        return pairs
    # name 또는 id 매칭 우선
    for f in followers:
        fid = (f.get("id") or "").strip()
        fname = (f.get("name") or "").strip()
        matched = None
        for s in servers:
            sname = str(s.get("name") or "").strip()
            if sname and (sname == fid or sname == fname):
                matched = s; break
        if not matched and len(servers) == 1:
            matched = servers[0]
        if matched:
            pairs.append((f, matched))
    return pairs

def ssh_place_order(inst_id: str, marginMode: str, side: str, orderType: str, price, size) -> List[Dict]:
    results=[]
    for f, srv in _list_pairs_followers_servers():
        if not (f.get("key") and f.get("secret") and f.get("passphrase")):
            results.append({"target": f.get("name") or f.get("id"), "error": "missing-keys"}); continue
        body = {
            "instId": inst_id,
            "marginMode": marginMode,
            "side": side.lower(),
            "orderType": (orderType or "market").lower(),
            "price": "" if (orderType or "market").lower()=="market" else (price or ""),
            "size": str(size),
        }
        path = "/api/v1/trade/order"
        sign, ts, nonce = _bf_sign(f["secret"], "POST", path, body)
        headers = {
            "ACCESS-KEY": f["key"],
            "ACCESS-PASSPHRASE": f["passphrase"],
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-NONCE": nonce,
            "Content-Type": "application/json",
        }
        st, txt = _ssh_curl(srv, "POST", path, headers, body, timeout=25)
        results.append({"target": f.get("name") or f.get("id"), "status": st, "text": txt})
    return results

def ssh_close_position(inst_id: str, size) -> List[Dict]:
    results=[]
    for f, srv in _list_pairs_followers_servers():
        if not (f.get("key") and f.get("secret") and f.get("passphrase")):
            results.append({"target": f.get("name") or f.get("id"), "error": "missing-keys"}); continue
        # 1) 포지션 조회 (원격 GET)
        qpath = f"/api/v1/account/positions?instId={inst_id}"
        sign_q, ts_q, nonce_q = _bf_sign(f["secret"], "GET", qpath, None)
        headers_q = {
            "ACCESS-KEY": f["key"],
            "ACCESS-PASSPHRASE": f["passphrase"],
            "ACCESS-SIGN": sign_q,
            "ACCESS-TIMESTAMP": ts_q,
            "ACCESS-NONCE": nonce_q,
        }
        st_q, txt_q = _ssh_curl(srv, "GET", qpath, headers_q, None, timeout=20)
        margin_mode, close_side = None, None
        try:
            jj = json.loads(txt_q)
            if jj.get("code") == "0" and jj.get("data"):
                pos = jj["data"][0]
                margin_mode = pos.get("marginMode")
                try:
                    size_now = float(pos.get("positions") or pos.get("position") or 0)
                except Exception:
                    size_now = 0.0
                close_side = "sell" if size_now > 0 else "buy"
        except Exception:
            pass

        if not margin_mode or not close_side:
            results.append({"target": f.get("name") or f.get("id"), "error":"position-lookup-failed", "status": st_q, "resp": txt_q[:300]})
            continue

        # 2) 시장가 청산 주문
        body = {
            "instId": inst_id,
            "marginMode": margin_mode,
            "side": close_side,
            "orderType": "market",
            "price": "",
            "size": str(size),
        }
        path = "/api/v1/trade/order"
        sign, ts, nonce = _bf_sign(f["secret"], "POST", path, body)
        headers = {
            "ACCESS-KEY": f["key"],
            "ACCESS-PASSPHRASE": f["passphrase"],
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-NONCE": nonce,
            "Content-Type": "application/json",
        }
        st, txt = _ssh_curl(srv, "POST", path, headers, body, timeout=25)
        results.append({"target": f.get("name") or f.get("id"), "status": st, "text": txt})
    return results

# ---------- WS Broadcaster ----------
class Broadcaster:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.queue: asyncio.Queue = asyncio.Queue()
    async def connect(self, ws: WebSocket):
        await ws.accept(); self.clients.add(ws)
    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)
    async def log(self, msg: str):
        print(msg)
        await self.queue.put({"type":"log","ts":int(time.time()*1000),"msg":msg})
    async def loop(self):
        while True:
            item = await self.queue.get()
            dead=[]
            for ws in list(self.clients):
                try: await ws.send_text(json.dumps(item, ensure_ascii=False))
                except: dead.append(ws)
            for d in dead: self.disconnect(d)

broad = Broadcaster()

# ---------- Master WS to Blockfin (로그인/구독) ----------
WS_URL = "wss://openapi.blockfin.com/ws/private"
listener_task: asyncio.Task | None = None
should_stop = asyncio.Event()

def _sign_login(secret: str):
    ts = str(int(time.time() * 1000))
    nonce = ts
    method = "GET"
    path = "/users/self/verify"
    msg = f"{path}{method}{ts}{nonce}"
    sig = base64.b64encode(hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest().encode()).decode()
    return sig, ts, nonce

def place_order_forward(inst_id, marginMode, side, orderType, price, size):
    # SSH 원격 curl
    return ssh_place_order(inst_id, marginMode, side, orderType, price, size)

def close_position_forward(inst_id, size):
    # SSH 원격 curl
    return ssh_close_position(inst_id, size)

async def master_session():
    master_key, master_secret, passphrase = load_env()
    if not all([master_key, master_secret, passphrase]):
        await broad.log("[ERROR] .env의 MASTER_API_KEY_BLO / MASTER_API_SECRET_BLO / passphrase 필요")
        await asyncio.sleep(5); return

    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20, close_timeout=10) as ws:
        sign, ts, nonce = _sign_login(master_secret)
        login_payload = {"op":"login","args":[{"apiKey":master_key,"passphrase":passphrase,"timestamp":ts,"sign":sign,"nonce":nonce}]}
        await ws.send(json.dumps(login_payload)); await broad.log(f"[→] 로그인 요청: {login_payload}")
        resp = await ws.recv(); await broad.log(f"[←] 로그인 응답: {resp}")
        try:
            j = json.loads(resp)
            if j.get("event")=="error":
                await broad.log(f"[LOGIN ERROR] code={j.get('code')} msg={j.get('msg')}"); await asyncio.sleep(5); return
        except Exception: pass

        sub_payload = {"op":"subscribe","args":[{"channel":"orders","instType":"SWAP"}]}
        await ws.send(json.dumps(sub_payload)); await broad.log(f"[→] orders 채널 구독 요청: {sub_payload}")

        while not should_stop.is_set():
            msg = await ws.recv()
            try:
                data = json.loads(msg) if isinstance(msg, (str, bytes)) else None
            except Exception:
                await broad.log(f"[WS RAW] {repr(msg)}"); continue
            if not isinstance(data, dict) or "data" not in data: continue

            for order in data["data"]:
                inst_id     = order.get("instId")
                side        = (order.get("side") or "").lower()
                order_state = (order.get("state") or "").upper()
                size        = order.get("size") or "0"
                price       = order.get("price")
                margin_mode = order.get("marginMode")
                order_type  = (order.get("orderType") or "market").lower()
                reduce_only = str(order.get("reduceOnly","false")).lower()=="true"
                await broad.log(f"[ORDER] {inst_id} {order_state} side={side} size={size} ro={reduce_only}")

                if order_state == "FILLED":
                    if reduce_only:
                        await broad.log(f"[MASTER] 청산 신호: {inst_id} size={size}")
                        res = close_position_forward(inst_id=inst_id, size=size)
                        await broad.log(f"[FOLLOWERS CLOSE RES] {json.dumps(res, ensure_ascii=False)[:900]}")
                    else:
                        await broad.log(f"[MASTER] 진입 신호: {inst_id} side={side} size={size} type={order_type}")
                        res = place_order_forward(inst_id=inst_id, marginMode=margin_mode or "cross",
                                                  side=side, orderType=order_type, price=price, size=size)
                        await broad.log(f"[FOLLOWERS PLACE RES] {json.dumps(res, ensure_ascii=False)[:900]}")

async def master_loop():
    backoff = 1
    while not should_stop.is_set():
        try:
            await master_session(); backoff = 1
        except websockets.ConnectionClosed as e:
            await broad.log(f"[WS CLOSED] code={getattr(e,'code',None)} reason={getattr(e,'reason',None)}")
        except Exception as e:
            await broad.log(f"[WS ERROR] {e}")
        await asyncio.sleep(backoff); backoff = min(backoff*2, 30)
        await broad.log(f"[RECONNECT] backoff={backoff}s")

# ---------- FastAPI ----------
app = FastAPI(title="Blockfin Master (SSH CURL forward)", version="1.7")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
async def on_start():
    asyncio.create_task(broad.loop())
    # 상태 요약
    cfg = load_servers_config()
    await broad.log(f"[SSH] servers.json loaded: {len(cfg.get('servers', []))} server(s)  mode={FORWARD_MODE}")
    global listener_task, should_stop
    should_stop.clear()
    listener_task = asyncio.create_task(master_loop())
    print(f"[MASTER] boot OK, http://0.0.0.0:8090  FORWARD_MODE={FORWARD_MODE}")

@app.on_event("shutdown")
async def on_stop():
    global listener_task
    should_stop.set()
    if listener_task: listener_task.cancel()

# ---- Auth (cookie) ----
SESSION_COOKIE = "bf_session"
def _make_session_token(username: str) -> str:
    raw = f"{username}:{int(time.time())}"
    return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()).decode()

def _check_session(request: Request) -> bool:
    return bool(request.cookies.get(SESSION_COOKIE))

def require_auth(request: Request) -> bool:
    return _check_session(request)

# ---- Pages ----
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if not require_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

@app.post("/api/login")
async def api_login(req: Request):
    data = await req.json()
    input_user = (data.get("username") or "").strip()
    input_pass = (data.get("password") or "").strip()
    admin_user, admin_pass = load_auth()
    if not admin_user or not admin_pass:
        return JSONResponse({"ok": False, "error": "관리자 계정 미설정(.auth.env)"}, status_code=400)
    if input_user != admin_user or input_pass != admin_pass:
        return JSONResponse({"ok": False, "error": "아이디/비밀번호 불일치"}, status_code=401)
    token = _make_session_token(admin_user)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(key=SESSION_COOKIE, value=token, httponly=True, max_age=60*60*12, samesite="Lax", path="/")
    return resp

@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp

# ---- ENV + followers 관리 ----
@app.get("/api/env")
async def get_env(request: Request):
    if not require_auth(request): return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    k, s, p = load_env()
    followers = load_followers_config()
    return {"ok": True,
            "master":{"key":k, "secret":"***" if s else "", "passphrase": "***" if p else ""},
            "followers": followers}

@app.post("/api/save-env")
async def api_save_env(request: Request):
    if not require_auth(request): return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    data = await request.json()
    mk = data.get("masterKey",""); ms = data.get("masterSecret",""); mp = data.get("passphrase","")
    followers_text = data.get("followersJson", None)
    try:
        save_env(mk, ms, mp)
        if followers_text is not None:
            save_followers_config(followers_text)
        global listener_task, should_stop
        should_stop.set(); await asyncio.sleep(0.2); should_stop.clear()
        listener_task = asyncio.create_task(master_loop())
        await broad.log("[CONFIG] 저장 및 리스너 재시작 완료")
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

@app.post("/api/upload-env")
async def api_upload_env(request: Request, file: UploadFile = File(...)):
    if not require_auth(request): return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    try:
        content = (await file.read()).decode("utf-8")
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        global listener_task, should_stop
        should_stop.set(); await asyncio.sleep(0.2); should_stop.clear()
        listener_task = asyncio.create_task(master_loop())
        await broad.log("[CONFIG] .env 업로드 완료 및 리스너 재시작")
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

# ---- WebSocket for logs ----
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    try:
        if "bf_session" not in ws.cookies:
            await ws.close(); return
    except:
        pass
    await broad.connect(ws)
    try:
        await broad.log("[CLIENT] connected")
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        broad.disconnect(ws)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8090, reload=True)
