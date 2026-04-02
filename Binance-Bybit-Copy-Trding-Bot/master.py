from binance import ThreadedWebsocketManager
from binance.client import Client
from dotenv import load_dotenv
import os
import time
from followers import copy_trade_to_followers

# 1. 환경 변수 불러오기
load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("MASTER_API_KEY")
api_secret = os.getenv("MASTER_API_SECRET")

# 2. Binance Client 초기화
client = Client(api_key, api_secret)

# 🔹 시간 동기화 함수
def sync_binance_time():
    try:
        server_time = client.get_server_time()
        server_ts = int(server_time['serverTime'])
        local_ts = int(time.time() * 1000)
        offset = server_ts - local_ts
        client.timestamp_offset = offset
        print(f"[✅ 시간 동기화 완료] 서버-로컬 오프셋: {offset}ms")
    except Exception as e:
        print(f"[ERROR] 시간 동기화 실패: {e}")

# 최초 실행 시 시간 동기화
sync_binance_time()

# 3. WebSocket Manager 시작
twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)
twm.start()

# 🔹 선물 레버리지 / 마진 조회 함수
def get_futures_position_info(symbol):
    try:
        sync_binance_time()

        # 1️⃣ 레버리지 조회 (futures_account)
        account_info = client.futures_account()
        leverage = None
        for pos in account_info['positions']:
            if pos['symbol'] == symbol.upper():
                leverage = pos['leverage']

        # 2️⃣ 마진 타입 조회 (isolatedMargin 값 확인)
        positions = client.futures_position_information(symbol=symbol.upper())
        margin_type = "CROSS"
        for pos in positions:
            if pos['symbol'] == symbol.upper():
                if float(pos.get('isolatedMargin', 0)) > 0:
                    margin_type = "ISOLATED"

        return leverage, margin_type

    except Exception as e:
        print(f"[ERROR] 레버리지/마진 조회 실패: {e}")
    return None, None


# 🔹 체결 이벤트 핸들러
def handle_msg(msg):
    if msg['e'] == 'ORDER_TRADE_UPDATE':
        order = msg['o']
        if order['x'] == 'TRADE' and order['X'] == 'FILLED':
            symbol = order['s']
            side = order['S']
            qty = float(order['q'])
            price = float(order['L'])
            position_side = order.get('ps', 'BOTH')
             
            leverage, margin_type = get_futures_position_info(symbol)
            print(leverage)
            print(margin_type)
            margin_text = "교차 마진 (Cross)" if margin_type == "CROSS" else "격리 마진 (Isolated)"

            print("\n[📈 선물 체결 감지]")
            print(f"🔹 심볼       : {symbol}")
            print(f"🔹 방향       : {side} | 포지션: {position_side}")
            print(f"🔹 수량(Qty)  : {qty}")
            print(f"🔹 체결가     : {price}")
            print(f"🔹 레버리지   : {leverage if leverage else '조회 실패'}배")
            print(f"🔹 마진 모드  : {margin_text if margin_type else '조회 실패'}")

            copy_trade_to_followers(symbol,side,position_side,qty,price,leverage,margin_text)
            
# 4. WebSocket 시작
twm.start_futures_socket(callback=handle_msg)

# 실행 유지
if __name__ == "__main__":
    print("📡 체결 감지 시작... 종료하려면 Ctrl+C")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 종료 요청 받음. WebSocket 정리 중...")
        twm.stop()
        print("✅ 정상 종료 완료.")
