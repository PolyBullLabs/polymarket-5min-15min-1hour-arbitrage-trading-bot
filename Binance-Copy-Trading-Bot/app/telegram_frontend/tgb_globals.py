import threading
import math
import time
import urllib.parse

# from selenium import webdriver
import pandas as pd
from pybit.unified_trading import HTTP

# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
import requests
import re
from app.data.credentials import db_user, db_pw, headers
import logging
from datetime import datetime

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class tgGlobals:
    # Define integer flags for use in Event Handlers
    def __init__(self, udt):
        username = urllib.parse.quote_plus(db_user)
        password = urllib.parse.quote_plus(db_pw)
        self.dbpath = "mongodb://%s:%s@localhost:27017/" % (username, password)
        self.is_reloading = False
        self.reloading = False
        self.updater = udt
        self.dictLock = threading.Lock()
        self.piclock = threading.Lock()
        self.stop_update = False
        self.current_position = None
        self.current_balance = None

    def get_all_symbols(self):
        client = HTTP(testnet=False)
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
        result = []
        for sym in res:
            result.append(sym["symbol"])
        return result

    def retrieve_command(self, db, stopcond):
        while not stopcond.is_set():
            time.sleep(1)
            msgs = db.getall("commandtable")
            recent_msg = []
            for msg in msgs:
                time.sleep(0.9)
                todelete = []
                if msg["cmd"] == "send_message":
                    # delete_flag = False
                    # for m in recent_msg:
                    #     if Levenshtein.ratio(m, msg["message"]) > 0.8:
                    #         logger.info(f"message deleted.")
                    #         todelete.append(msg["_id"])
                    #         db.delete_command(todelete)
                    #         delete_flag = True
                    #         break
                    # if delete_flag:
                    #     continue
                    try:
                        for i in range(len(msg["message"]) // 500 + 1):
                            time.sleep(0.7)
                            sendmsg = msg["message"][500 * i : 500 * (i + 1)]
                            if (
                                int(msg["chat_id"]) > 20
                                and re.sub(r"[^a-zA-Z0-9]+", "", sendmsg) != ""
                            ):
                                self.updater.bot.sendMessage(msg["chat_id"], sendmsg)
                                time.sleep(0.1)
                            elif int(msg["chat_id"]) < 20:
                                logger.info(
                                    f"Master Trader {msg['chat_id']}: {sendmsg}"
                                )
                        todelete.append(msg["_id"])
                        db.delete_command(todelete)
                        recent_msg.append(msg["message"])
                    except Exception as e:
                        logger.error(f"Connection Error: {str(e)}")

    def round_up(self, n, decimals=0):
        multiplier = 10**decimals
        return math.ceil(n * multiplier) / multiplier

    @staticmethod
    def format_results(poslist, times):
        symbol = []
        size = []
        entry_price = []
        mark_price = []
        pnl = []
        margin = []
        calculatedMargin = []
        times = datetime.utcfromtimestamp(times / 1000).strftime("%Y-%m-%d %H:%M:%S")
        for dt in poslist:
            symbol.append(dt["symbol"])
            size.append(dt["amount"])
            entry_price.append(dt["entryPrice"])
            mark_price.append(dt["markPrice"])
            pnl.append(f"{round(dt['pnl'],2)} ({round(dt['roe']*100,2)}%)")
            margin.append(str(dt["leverage"]) + "x")
            calculatedMargin.append(True)
        dictx = {
            "symbol": symbol,
            "size": size,
            "Entry Price": entry_price,
            "Mark Price": mark_price,
            "PNL (ROE%)": pnl,
            "Estimated Margin": margin,
        }
        df = pd.DataFrame(dictx)
        return {"time": times, "data": df}, calculatedMargin

    def get_cookie(self, db):
        cookies = db.get_cookies()
        if len(cookies) == 0:
            return None
        cookie_str, token = cookies[0]["cookie"], cookies[0]["csrftoken"]
        cookie_str = cookie_str.split(";")
        cookies = dict()
        for cookie in cookie_str:
            cookie = cookie.strip().split("=")
            cookies[cookie[0]] = cookie[1]
        return cookies, token

    def get_init_traderPosition(self, uid, db):
        try:
            cookies, token = self.get_cookie(db)
            assert cookies is not None, "Out of correct cookie."
            headers["Csrftoken"] = token
            r = requests.post(
                "https://www.binance.com/bapi/futures/v2/private/future/leaderboard/getOtherPosition",
                json={"encryptedUid": uid, "tradeType": "PERPETUAL"},
                cookies=cookies,
                headers=headers,
            )
            logger.info(f"{r.json()}")
            assert r.status_code == 200, "Status code is not 200"
            positions = r.json()["data"]["otherPositionRetList"]
            times = r.json()["data"]["updateTimeStamp"]
            assert positions is not None, "Null positions"
            assert times is not None, "Null times"
        except Exception as e:
            logger.error(f"Error in init positions: {e}")
            return "x"
        output, _ = self.format_results(positions, times)
        return output["data"]
