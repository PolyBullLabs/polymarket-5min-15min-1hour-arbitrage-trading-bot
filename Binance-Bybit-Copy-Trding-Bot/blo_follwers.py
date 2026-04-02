# follower_server.py
import os, sys, json, time, hmac, base64, hashlib
from typing import Dict, Any
import uvicorn, requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from uuid import uuid4

def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

ROOT = app_dir()
ENV_PATH = os.path.join(ROOT, ".env")

# ---- env 준비
if not os.path.exists(ENV_PATH):
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(
            "SUB_KEY=\n"
            "SUB_SECRET=\n"
            "SUB_PASSPHRASE=\n"
            "MASTER_SHARED_TOKEN=\n"
            "PORT=9010\n"
        )

load_dotenv(dotenv_path=ENV_PATH, override=True)
SUB_KEY = os.getenv("SUB_KEY") or ""
SUB_SECRET = os.getenv("SUB_SECRET") or ""
SUB_PASSPHRASE = os.getenv("SUB_PASSPHRASE") or ""
MASTER_SHARED_TOKEN = (os.getenv("MASTER_SHARED_TOKEN") or "").encode()
PORT = int(os.getenv("PORT") or "9010")

BASE_URL = "https://openapi.blockfin.com"

def _sign_rest(secret_key: str, method: str, path: str, body: Dict[str, Any] | None):
    ts = str(int(time.time() * 1000))
    nonce = str(uuid4())
    body_str = json.dumps(body) if body else ""
    prehash = f"{path}{method.upper()}{ts}{nonce}{body_str}"
    hex_signature = hmac.new(secret_key.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    sig = base64.b64encode(hex_signature.encode()).decode()
    return sig, ts, nonce

def _sign_blockfin_get(secret_key: str, method: str, path: str):
    ts = str(int(time.time() * 1000))
    nonce = ts
    body = ""
    prehash = f"{path}{method}{ts}{nonce}{body}"
    hex_signature = hmac.new(secret_key.encode(), prehash.encode(), hashlib.sha256).hexdigest().encode()
    sig = base64.b64encode(hex_signature).decode()
    return sig, ts, nonce

def verify_master(request: Request, raw_body: bytes):
    if not MASTER_SHARED_TOKEN:
        raise HTTPException(500, "MASTER_SHARED_TOKEN not set in follower .env")
    got = request.headers.get("x-master-sign", "")
    calc = hmac.new(MASTER_SHARED_TOKEN, raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(got, calc):
        raise HTTPException(401, "invalid master signature")

app = FastAPI(title="Follower Server", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)

@app.get("/health")
def health():
    return {"ok": True, "who": "follower", "port": PORT}

@app.post("/api/order")
async def api_order(request: Request):
    raw = await request.body()
    verify_master(request, raw)
    data = json.loads(raw or b"{}")
    inst_id     = data.get("instId")
    marginMode  = data.get("marginMode")
    side        = data.get("side")
    orderType   = data.get("orderType") or "market"
    price       = data.get("price") or ""
    size        = str(data.get("size") or "")

    path = "/api/v1/trade/order"; method="POST"
    body = {"instId":inst_id,"marginMode":marginMode,"side":side,"orderType":orderType,"price":price,"size":size}
    sign, ts, nonce = _sign_rest(SUB_SECRET, method, path, body)
    headers = {
        "ACCESS-KEY": SUB_KEY,
        "ACCESS-PASSPHRASE": SUB_PASSPHRASE,
        "ACCESS-SIGN": sign, "ACCESS-TIMESTAMP": ts, "ACCESS-NONCE": nonce,
        "Content-Type": "application/json"
    }
    r = requests.post(BASE_URL+path, headers=headers, json=body, timeout=10)
    return JSONResponse({"ok": r.status_code==200, "status": r.status_code, "text": r.text})

@app.post("/api/close")
async def api_close(request: Request):
    raw = await request.body()
    verify_master(request, raw)
    data = json.loads(raw or b"{}")
    inst_id = data.get("instId")
    size    = str(data.get("size") or "")

    # 현재 포지션 조회
    path = f"/api/v1/account/positions?instId={inst_id}"; method="GET"
    sign, ts, nonce = _sign_blockfin_get(SUB_SECRET, method, path)
    headers = {
        "ACCESS-KEY": SUB_KEY,
        "ACCESS-PASSPHRASE": SUB_PASSPHRASE,
        "ACCESS-SIGN": sign, "ACCESS-TIMESTAMP": ts, "ACCESS-NONCE": nonce
    }
    j = requests.get(BASE_URL+path, headers=headers, timeout=10).json()
    if j.get("code")!="0" or not j.get("data"):
        return JSONResponse({"ok": False, "error": f"position query fail: {j}"}, status_code=400)
    pos = j["data"][0]
    marginMode = pos.get("marginMode")
    try:
        psize = float(pos.get("positions") or pos.get("position", 0))
    except:
        psize = 0.0
    close_side = "sell" if psize>0 else "buy"

    # 청산 주문
    path = "/api/v1/trade/order"; method="POST"
    body = {"instId":inst_id,"marginMode":marginMode,"side":close_side,"orderType":"market","price":"","size":size}
    sign, ts, nonce = _sign_rest(SUB_SECRET, method, path, body)
    headers = {
        "ACCESS-KEY": SUB_KEY,
        "ACCESS-PASSPHRASE": SUB_PASSPHRASE,
        "ACCESS-SIGN": sign, "ACCESS-TIMESTAMP": ts, "ACCESS-NONCE": nonce,
        "Content-Type": "application/json"
    }
    r = requests.post(BASE_URL+path, headers=headers, json=body, timeout=10)
    return JSONResponse({"ok": r.status_code==200, "status": r.status_code, "text": r.text})

if __name__ == "__main__":
    uvicorn.run("follower_server:app", host="0.0.0.0", port=PORT, reload=True)
