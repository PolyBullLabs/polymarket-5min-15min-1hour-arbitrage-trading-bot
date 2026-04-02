import threading
from app.copy_trade_backend.ct_bybit import BybitClient
from app.data.credentials import headers
from io import StringIO
import time
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
import pandas as pd
from datetime import datetime, timedelta
import requests
import random


class WebScraping(threading.Thread):
    def __init__(self, globals, userdb):
        threading.Thread.__init__(self)
        self.i = 0
        self.isStop = threading.Event()
        self.pauseload = threading.Event()
        self.cond = {}
        self.userdb = userdb
        self.globals = globals
        self.changeNotiTime = {}
        self.num_no_data = {}
        self.error = {}

    @staticmethod
    def format_results(poslist, times):
        symbol = []
        size = []
        entry_price = []
        mark_price = []
        pnl = []
        margin = []
        calculatedMargin = []
        marginList = dict()
        times = datetime.utcfromtimestamp(times / 1000).strftime("%Y-%m-%d %H:%M:%S")
        for dt in poslist:
            symbol.append(dt["symbol"])
            size.append(dt["amount"])
            entry_price.append(dt["entryPrice"])
            mark_price.append(dt["markPrice"])
            pnl.append(f"{round(dt['pnl'],2)} ({round(dt['roe']*100,2)}%)")
            margin.append(str(dt["leverage"]) + "x")
            calculatedMargin.append(True)
            marginList[dt["symbol"]] = dt["leverage"]
        dictx = {
            "symbol": symbol,
            "size": size,
            "Entry Price": entry_price,
            "Mark Price": mark_price,
            "PNL (ROE%)": pnl,
            "Estimated Margin": margin,
        }
        df = pd.DataFrame(dictx)
        return {"time": times, "data": df}, calculatedMargin, marginList

    def changes(self, df, df2):
        txtype = []
        txsymbol = []
        txsize = []
        executePrice = []
        isClosedAll = []
        if (isinstance(df, str) or df is None) and (
            isinstance(df2, str) or df2 is None
        ):
            return None
        if isinstance(df, str):
            for index, row in df2.iterrows():
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                if size > 0:
                    txtype.append("OpenLong")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
                else:
                    txtype.append("OpenShort")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
            txs = pd.DataFrame(
                {
                    "txtype": txtype,
                    "symbol": txsymbol,
                    "size": txsize,
                    "ExecPrice": executePrice,
                    "isClosedAll": isClosedAll,
                }
            )
        elif isinstance(df2, str):
            for index, row in df.iterrows():
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                if size > 0:
                    txtype.append("CloseLong")
                    txsymbol.append(row["symbol"])
                    txsize.append(-size)
                    executePrice.append(row["Mark Price"])
                    isClosedAll.append(True)
                else:
                    txtype.append("CloseShort")
                    txsymbol.append(row["symbol"])
                    txsize.append(-size)
                    executePrice.append(row["Mark Price"])
                    isClosedAll.append(True)
            txs = pd.DataFrame(
                {
                    "txtype": txtype,
                    "symbol": txsymbol,
                    "size": txsize,
                    "ExecPrice": executePrice,
                    "isClosedAll": isClosedAll,
                }
            )
        else:
            df, df2 = df.copy(), df2.copy()
            for index, row in df.iterrows():
                hasChanged = False
                temp = df2["symbol"] == row["symbol"]
                idx = df2.index[temp]
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                oldentry = row["Entry Price"]
                if isinstance(oldentry, str):
                    oldentry = oldentry.replace(",", "")
                oldentry = float(oldentry)
                oldmark = row["Mark Price"]
                if isinstance(oldmark, str):
                    oldmark = oldmark.replace(",", "")
                oldmark = float(oldmark)
                isPositive = size >= 0
                for r in idx:
                    df2row = df2.loc[r].values
                    newsize = df2row[1]
                    if isinstance(newsize, str):
                        newsize = newsize.replace(",", "")
                    newsize = float(newsize)
                    newentry = df2row[2]
                    if isinstance(newentry, str):
                        newentry = newentry.replace(",", "")
                    newentry = float(newentry)
                    newmark = df2row[3]
                    if isinstance(newmark, str):
                        newmark = newmark.replace(",", "")
                    newmark = float(newmark)
                    if newsize == size:
                        df2 = df2.drop(r)
                        hasChanged = True
                        break
                    if isPositive and newsize > 0:
                        changesize = newsize - size
                        if abs(changesize) < 1e-7:
                            df2 = df2.drop(r)
                            hasChanged = True
                            break
                        if changesize > 0:
                            txtype.append("OpenLong")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            isClosedAll.append(False)
                            try:
                                exp = (
                                    newentry * newsize - oldentry * size
                                ) / changesize
                            except:
                                exp = 0
                            if changesize / newsize < 0.05:
                                executePrice.append(newmark)
                            else:
                                executePrice.append(exp)
                        else:
                            txtype.append("CloseLong")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            executePrice.append(newmark)
                            isClosedAll.append(False)
                        df2 = df2.drop(r)
                        hasChanged = True
                        break
                    if not isPositive and newsize < 0:
                        changesize = newsize - size
                        if abs(changesize) < 1e-7:
                            df2 = df2.drop(r)
                            hasChanged = True
                            break
                        if changesize > 0:
                            txtype.append("CloseShort")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            executePrice.append(newmark)
                            isClosedAll.append(False)
                        else:
                            txtype.append("OpenShort")
                            txsymbol.append(df2row[0])
                            txsize.append(changesize)
                            isClosedAll.append(False)
                            try:
                                exp = (
                                    newentry * newsize - oldentry * size
                                ) / changesize
                            except:
                                exp = 0
                            if changesize / newsize < 0.05:
                                executePrice.append(newmark)
                            else:
                                executePrice.append(exp)
                        df2 = df2.drop(r)
                        hasChanged = True
                        break
                if not hasChanged:
                    if size > 0:
                        txtype.append("CloseLong")
                        txsymbol.append(row["symbol"])
                        txsize.append(-size)
                        executePrice.append(oldmark)
                        isClosedAll.append(True)
                    else:
                        txtype.append("CloseShort")
                        txsymbol.append(row["symbol"])
                        txsize.append(-size)
                        executePrice.append(oldmark)
                        isClosedAll.append(True)
            for index, row in df2.iterrows():
                size = row["size"]
                if isinstance(size, str):
                    size = size.replace(",", "")
                size = float(size)
                if size > 0:
                    txtype.append("OpenLong")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
                else:
                    txtype.append("OpenShort")
                    txsymbol.append(row["symbol"])
                    txsize.append(size)
                    executePrice.append(row["Entry Price"])
                    isClosedAll.append(False)
            txs = pd.DataFrame(
                {
                    "txType": txtype,
                    "symbol": txsymbol,
                    "size": txsize,
                    "ExecPrice": executePrice,
                    "isClosedAll": isClosedAll,
                }
            )
        return txs  # add this to open trade part

    def position_changes(self, positions, times, uid, prev_df, name, lasttime):
        following_users = self.userdb.fetch_following(uid)
        try:
            prev_position = self.userdb.fetch_trader_position(uid)
        except:
            logger.info(f"{uid} Cannot get past positions.")
            return
        if len(positions) == 0:
            self.num_no_data[uid] = (
                1 if uid not in self.num_no_data else self.num_no_data[uid] + 1
            )
            if self.num_no_data[uid] > 35:
                self.num_no_data[uid] = 4
            if self.num_no_data[uid] >= 3 and prev_position != "x":
                logger.info(f"{name} Change to no position.")
                # self.changeNotiTime[uid] = datetime.now()
                now = datetime.now() + timedelta(hours=8)
                # self.lastPosTime = datetime.now() + timedelta(hours=8)
                tosend = (
                    f"Trader {name}, Current time: " + str(now) + "\nNo positions.\n"
                )
                txlist = self.changes(prev_df, "x")
                self.userdb.insert_command2(
                    {
                        "cmd": "trader_update",
                        "name": name,
                        "txlist": list(txlist["symbol"].to_numpy()),
                        "position": pd.DataFrame({}).to_json(orient="index"),
                        "trader": uid,
                        "margin": {},
                    }
                )
                for users in following_users:
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "chat_id": users["chat_id"],
                            "message": tosend,
                        }
                    )
                    if users["traders"][uid]["toTrade"]:
                        tosend = "Making the following trades: \n" + txlist.to_string()
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": users["chat_id"],
                                "message": tosend,
                            }
                        )
                        retries = 0
                        while retries < 3:
                            try:
                                client = BybitClient(
                                    users["chat_id"],
                                    users["uname"],
                                    users["safety_ratio"],
                                    users["api_key"],
                                    users["api_secret"],
                                    users["slippage"],
                                    self.globals,
                                    self.userdb,
                                )
                                client.open_trade(
                                    txlist,
                                    uid,
                                    users["traders"][uid]["proportion"],
                                    users["leverage"],
                                    users["traders"][uid]["tmode"],
                                    users["traders"][uid]["positions"],
                                    users["slippage"],
                                )
                                del client
                                break
                            except Exception as e:
                                retries += 1
                                logger.error(f"Error in trade opening {e}")
                self.userdb.save_position(uid, "x", True)
            elif self.num_no_data[uid] >= 3:
                self.userdb.save_position(uid, "x", False)
            # diff = datetime.now() - datetime.strptime(lasttime, "%y-%m-%d %H:%M:%S")
            # if diff.total_seconds() / 3600 >= 24:
            # for users in following_users:
            #     self.userdb.insert_command(
            #         {
            #             "cmd": "send_message",
            #             "chat_id": users["chat_id"],
            #             "message": f"Trader {name}: 24 hours no position update.",
            #         }
            #     )
        else:
            self.num_no_data[uid] = 0
            try:
                output, calmargin, marginList = self.format_results(positions, times)
            except Exception as e:
                logger.error(f"Trader {name} may not share position anymore. {e}")
                return
            if prev_position == "x":
                isChanged = True
                txlist = self.changes(prev_position, output["data"])
            else:
                prev_position = pd.read_json(StringIO(prev_position))
                try:
                    toComp = output["data"][["symbol", "size", "Entry Price"]]
                    prevdf = prev_position[["symbol", "size", "Entry Price"]]
                except Exception as e:
                    logger.error(f"Error in position reading {e}")
                if not toComp.equals(prevdf):
                    txlist = self.changes(prev_position, output["data"])
                    if not txlist.empty:
                        isChanged = True
                    else:
                        isChanged = False
                else:
                    isChanged = False
            if isChanged:
                logger.info(f"{name} changed positions.")
                now = datetime.now() + timedelta(hours=8)
                self.lastPosTime = datetime.now() + timedelta(hours=8)
                numrows = output["data"].shape[0]
                if True:  # numrows <= 10:
                    tosend = f"Trader {name}, changed position at {now}"
                    # tosend = (
                    #     f"Trader {name}, Current time: "
                    #     + str(now)
                    #     + "\n"
                    #     + output["time"]
                    #     + "\n"
                    #     + output["data"].to_string()
                    #     + "\n"
                    # )
                    for users in following_users:
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": users["chat_id"],
                                "message": tosend,
                            }
                        )
                # else:
                #     firstdf = output["data"].iloc[0:10]
                #     tosend = (
                #         f"Trader {name}, Current time: "
                #         + str(now)
                #         + "\n"
                #         + output["time"]
                #         + "\n"
                #         + firstdf.to_string()
                #         + "\n(cont...)"
                #     )
                #     for users in following_users:
                #         self.userdb.insert_command(
                #             {
                #                 "cmd": "send_message",
                #                 "chat_id": users["chat_id"],
                #                 "message": tosend,
                #             }
                #         )
                #     for i in range(numrows // 10):
                #         seconddf = output["data"].iloc[
                #             (i + 1) * 10 : min(numrows, (i + 2) * 10)
                #         ]
                #         if not seconddf.empty:
                #             for users in following_users:
                #                 self.userdb.insert_command(
                #                     {
                #                         "cmd": "send_message",
                #                         "chat_id": users["chat_id"],
                #                         "message": seconddf.to_string(),
                #                     }
                #                 )
                # txlist = self.changes(prev_position, output["data"])
                self.userdb.insert_command2(
                    {
                        "cmd": "trader_update",
                        "name": name,
                        "txlist": list(txlist["symbol"].to_numpy()),
                        "position": output["data"].to_json(orient="index"),
                        "trader": uid,
                        "margin": marginList,
                    }
                )
                for users in following_users:
                    if users["traders"][uid]["toTrade"] and not txlist.empty:
                        tosend = "Making the following trades: \n" + txlist.to_string()
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "chat_id": users["chat_id"],
                                "message": tosend,
                            }
                        )
                        retries = 0
                        while retries < 3:
                            try:
                                client = BybitClient(
                                    users["chat_id"],
                                    users["uname"],
                                    users["safety_ratio"],
                                    users["api_key"],
                                    users["api_secret"],
                                    users["slippage"],
                                    self.globals,
                                    self.userdb,
                                )
                                client.open_trade(
                                    txlist,
                                    uid,
                                    users["traders"][uid]["proportion"],
                                    users["leverage"],
                                    users["traders"][uid]["tmode"],
                                    users["traders"][uid]["positions"],
                                    users["slippage"],
                                )
                                del client
                                break
                            except Exception as e:
                                retries += 1
                                logger.error(str(e))
                self.userdb.save_position(uid, output["data"].to_json(), True)
            else:
                self.userdb.save_position(uid, output["data"].to_json(), False)
        self.first_run = False
        diff = datetime.now() - datetime.strptime(lasttime, "%y-%m-%d %H:%M:%S")
        # if diff.total_seconds() / 3600 >= 24:
        #     for users in following_users:
        #         self.userdb.insert_command(
        #             {
        #                 "cmd": "send_message",
        #                 "chat_id": users["chat_id"],
        #                 "message": f"Trader {self.name}: 24 hours no position update.",
        #             }
        #         )

    def get_cookie(self):
        cookies = self.userdb.get_cookies()
        if len(cookies) == 0:
            return None, None, None, None
        chosen_cookie = random.choice(cookies)
        cookie_str, token, label, _id = (
            chosen_cookie["cookie"],
            chosen_cookie["csrftoken"],
            chosen_cookie["label"],
            chosen_cookie["_id"],
        )
        try:
            cookie_str = cookie_str.split(";")
            cookies = dict()
            for cookie in cookie_str:
                cookie = cookie.strip().split("=")
                cookies[cookie[0]] = cookie[1]
        except Exception as e:
            logger.error(f"Wrong cookie format, deleting: {e}")
            self.userdb.remove_cookie(_id)
            return None, None, None, None
        return cookies, token, label, _id

    def run(self):
        while not self.isStop.is_set():
            if self.pauseload.is_set():
                time.sleep(5)
                continue
            urls = self.userdb.retrieve_traders()
            for uid in urls:
                # logger.info(f"Running {uid['name']}.")
                try:
                    while True:
                        time.sleep(1)  # change to 1s
                        cookies, token, label, _id = self.get_cookie()
                        headers["Csrftoken"] = token
                        assert cookies is not None, "Out of correct cookie."
                        r = requests.post(
                            "https://www.binance.com/bapi/futures/v2/private/future/leaderboard/getOtherPosition",
                            json={"encryptedUid": uid["uid"], "tradeType": "PERPETUAL"},
                            cookies=cookies,
                            headers=headers,
                        )
                        if r.json()["success"] == False or r.status_code != 200:
                            if "too many" in r.json()["message"]:
                                time.sleep(2)
                                continue
                            logger.info(
                                f"Login credential may have expired, deleting cookie: {r.json()['message']}"
                            )
                            self.globals.send_discord_reminder(
                                f"Cookie label {label} expired."
                            )
                            self.userdb.remove_cookie(_id)
                            continue
                        positions = r.json()["data"]["otherPositionRetList"]
                        times = r.json()["data"]["updateTimeStamp"]
                        positions = [] if positions is None else positions
                        self.error[uid["uid"]] = 0
                        break
                except Exception as e:
                    time.sleep(0.05)
                    # following_users = self.userdb.fetch_following(uid["uid"])
                    if uid["uid"] not in self.error:
                        self.error[uid["uid"]] = 1
                    else:
                        self.error[uid["uid"]] += 1
                        if self.error[uid["uid"]] >= 20:
                            self.error[uid["uid"]] = 11
                    if self.error[uid["uid"]] == 10:
                        logger.error(f"{uid['name']} cannot fetch url: {e}")
                        self.globals.send_discord_reminder(
                            f"Trader {uid['name']}: May have stopped sharing positions!"
                        )
                        # for users in following_users:
                        #     self.userdb.insert_command(
                        #         {
                        #             "cmd": "send_message",
                        #             "chat_id": users["chat_id"],
                        #             "message": f"Trader {uid['name']}: May have stopped sharing positions!",
                        #         }
                        #     )
                    continue
                if uid["positions"] != "x":
                    prevpos = pd.read_json(StringIO(uid["positions"]))
                else:
                    prevpos = "x"
                self.position_changes(
                    positions,
                    times,
                    uid["uid"],
                    prevpos,
                    uid["name"],
                    uid["lastPosTime"],
                )

    def stop(self):
        self.isStop.set()

    def pause(self):
        self.pauseload.set()

    def resume(self):
        self.pauseload.clear()
