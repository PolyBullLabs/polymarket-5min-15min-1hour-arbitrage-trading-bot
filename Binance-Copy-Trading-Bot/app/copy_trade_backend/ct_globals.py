import math
import requests
import threading
import logging
from app.copy_trade_backend.ct_bybit import BybitClient
import time
from pybit.unified_trading import HTTP
import pandas as pd
import urllib.parse
from app.data.credentials import db_user, db_pw, discord_webhook

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class ctGlobal:
    def __init__(self):
        self.stopevent = threading.Event()
        self.dblock = threading.Lock()
        self.apilock = threading.Lock()
        self.past_balances = dict()
        self.has_announced = dict()
        username = urllib.parse.quote_plus(db_user)
        password = urllib.parse.quote_plus(db_pw)
        self.dbpath = "mongodb://%s:%s@localhost:27017/" % (username, password)
        logger.info(self.dbpath)
        return

    def send_discord_reminder(self, message):
        data = {"content": message}
        requests.post(discord_webhook, data)

    def cookie_check(self, db):
        sent = 0
        while True:
            time.sleep(1)
            cookie = db.get_cookies()
            if len(cookie) == 0:
                sent += 1
                if sent == 1:
                    self.send_discord_reminder("Out of usable credentials for api!!!")
                sent = sent % 3000
                continue
            sent = 0

    def round_up(self, n, decimals=0):
        multiplier = 10**decimals
        return math.ceil(n * multiplier) / multiplier

    def get_latest_price(self, symbol):
        session = HTTP(testnet=False)
        try:
            res = session.get_kline(
                category="linear", symbol=symbol, interval="1", limit=1
            )
            assert res["retMsg"] == "OK", "return message not ok"
            res = res["result"]["list"][0][4]
            res = float(res)
        except Exception as e:
            logger.error(f"Error in fetching price for {symbol}: {e}")
        return res

    def getIdx(self, side, isOpen):
        if side == "Buy":
            if isOpen:
                return 1
            return 2
        else:
            if isOpen:
                return 2
            return 1

    def reload_symbols(self, userdb):
        client = HTTP(testnet=False, api_key="", api_secret="")
        res = []
        try:
            temp = client.get_instruments_info(category="linear")
            assert temp["retMsg"] == "OK", "Return message not ok."
            res.extend(temp["result"]["list"])
            while temp["result"]["nextPageCursor"] != "":
                temp = client.get_instruments_info(
                    category="linear", cursor=temp["result"]["nextPageCursor"]
                )
                assert temp["retMsg"] == "OK", "Return message not ok."
                res.extend(temp["result"]["list"])
        except Exception as e:
            logger.error(f"Cannot query symbol: {e}.")
            return
        for user in userdb.retrieve_users():
            new_lev = {}
            for sym in res:
                if sym["symbol"] in user["leverage"]:
                    new_lev[sym["symbol"]] = user["leverage"][sym["symbol"]]
                else:
                    new_lev[sym["symbol"]] = user["leverage"]["XRPUSDT"]
                    userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "chat_id": user["chat_id"],
                            "message": f"There is a new symbol {sym['symbol']} available.",
                        }
                    )
            userdb.update_leverage(user["chat_id"], new_lev)
            for trader in user["traders"]:
                new_prop = {}
                for sym in res:
                    if sym["symbol"] in user["traders"][trader]["proportion"]:
                        new_prop[sym["symbol"]] = user["traders"][trader]["proportion"][
                            sym["symbol"]
                        ]
                    else:
                        new_prop[sym["symbol"]] = user["traders"][trader]["proportion"][
                            "XRPUSDT"
                        ]
                userdb.update_proportion(user["chat_id"], trader, new_prop)

    def check_noti(self, userdb):
        while not self.stopevent.is_set():
            time.sleep(3)
            allnoti = userdb.get_noti()
            todelete = []
            for noti in allnoti:
                if noti["cmd"] == "delete_and_closeall":
                    chat_id = noti["user"]
                    uid = noti["trader"]
                    user = userdb.get_user(chat_id)
                    if "positions" not in user["traders"][uid]:
                        del user["traders"][uid]
                        userdb.update_user(chat_id, user)
                        # TODO update the trader list?
                    else:
                        all_positions = user["traders"][uid]["positions"]
                        # bla bla bla: closing position
                        client = BybitClient(
                            chat_id,
                            user["uname"],
                            user["safety_ratio"],
                            user["api_key"],
                            user["api_secret"],
                            user["slippage"],
                            self,
                            userdb,
                        )
                        txtype, txsymbol, txsize, execprice, isClosedAll = (
                            [],
                            [],
                            [],
                            [],
                            [],
                        )
                        for pos in all_positions:
                            if pos[-4:].upper() == "LONG":
                                txtype.append("CloseLong")
                                txsymbol.append(pos[:-4])
                                txsize.append(float(all_positions[pos]))
                                execprice.append(self.get_latest_price(pos[:-4]))
                                isClosedAll.append(True)
                            else:
                                txtype.append("CloseShort")
                                txsymbol.append(pos[:-5])
                                txsize.append(float(all_positions[pos]))
                                execprice.append(self.get_latest_price(pos[:-5]))
                                isClosedAll.append(True)
                        txs = pd.DataFrame(
                            {
                                "txtype": txtype,
                                "symbol": txsymbol,
                                "size": txsize,
                                "ExecPrice": execprice,
                                "isClosedAll": isClosedAll,
                            }
                        )
                        prop = user["traders"][uid]["proportion"]
                        for key in prop:
                            prop[key] = 1
                        client.open_trade(
                            txs,
                            uid,
                            prop,
                            user["leverage"],
                            user["traders"][uid]["tmode"],
                            user["traders"][uid]["positions"],
                            user["slippage"],
                            True,
                        )
                        del user["traders"][uid]
                        userdb.update_user(chat_id, user)
                        userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": chat_id,
                                "message": f"Successfully deleted trader!",
                            }
                        )
                todelete.append(noti["_id"])
            userdb.delete_command(todelete)
