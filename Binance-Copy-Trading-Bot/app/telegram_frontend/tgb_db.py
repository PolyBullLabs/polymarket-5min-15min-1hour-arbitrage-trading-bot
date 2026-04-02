import pymongo
import pandas as pd
import time
import logging
from pybit.unified_trading import HTTP

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class dbOperations:
    def __init__(self, glb, udt):
        self.globals = glb
        self.client = pymongo.MongoClient(glb.dbpath)
        self.db = self.client["binance"]
        self.usertable = self.db["Users"]
        self.commandtable = self.db["Commands"]
        self.tradertable = self.db["Traders"]
        self.notitable = self.db["Notifications"]
        self.cookietable = self.db["Cookies"]
        self.allowedTraders = self.db["allowedTraders"]
        self.allowedUsers = self.db["allowedUsers"]
        self.updater = udt

    def get_uid(self, api_key, api_secret):
        try:
            client = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)
            res = client.get_api_key_information()
            return res["result"]["userID"]
        except Exception as e:
            logger.error(f"Get UID {e}")
        return None

    def find_allowed_user(self, name, uid=None):
        if uid is None:
            myquery = {"user": name}
        else:
            myquery = {"user": name, "uid": uid}
        return self.allowedUsers.find_one(myquery)

    def get_cookies(self):
        data = []
        for x in self.cookietable.find():
            data.append(x)
        return data

    def add_credential(self, cookie, token, label):
        doc = {"cookie": cookie, "csrftoken": token, "label": label}
        self.cookietable.insert_one(doc)

    # Do not allow removing cookie in front end

    def getall(self, table):
        data = []
        if table == "usertable":
            for x in self.usertable.find():
                data.append(x)
        if table == "commandtable":
            for x in self.commandtable.find():
                data.append(x)
        return data

    def delete_command(self, docids):
        for docid in docids:
            self.commandtable.delete_one({"_id": docid})

    def add_user(self, chat_id, userdoc):
        self.usertable.insert_one(userdoc)
        self.updater.bot.sendMessage(chat_id, "Initialization successful!")

    def get_trader(self, name):
        myquery = {"name": name}
        return self.tradertable.find_one(myquery)

    def add_trader(self, traderdoc):
        self.tradertable.insert_one(traderdoc)

    def get_user(self, chat_id):
        myquery = {"chat_id": chat_id}
        return self.usertable.find_one(myquery)

    def update_user(self, chat_id, userdoc):
        myquery = {"chat_id": chat_id}
        return self.usertable.replace_one(myquery, userdoc)

    def update_trader(self, uid, traderdoc):
        myquery = {"uid": uid}
        return self.tradertable.replace_one(myquery, traderdoc)

    def check_presence(self, chat_id):
        myquery = {"chat_id": chat_id}
        mydoc = self.usertable.find(myquery)
        i = 0
        for doc in mydoc:
            i += 1
        return i >= 1

    def deleteuser(self, chat_id):
        myquery = {"chat_id": chat_id}
        user = self.usertable.find_one(myquery)
        for uid in user["traders"]:
            self.delete_trader(uid)
        self.usertable.delete_many(myquery)
        self.updater.bot.sendMessage(chat_id, "Account successfully deleted.")

    def get_trader_list(self, chat_id):
        myquery = {"chat_id": chat_id}
        user = self.usertable.find_one(myquery)
        data = []
        for x in user["traders"]:
            data.append(user["traders"][x]["name"])
        return data

    def get_trader_fromuser(self, chat_id, tradername):
        myquery = {"chat_id": chat_id}
        user = self.usertable.find_one(myquery)
        for uid in user["traders"]:
            if user["traders"][uid]["name"] == tradername:
                return user["traders"][uid]
        return None

    def delete_trader(self, uid, chat_id=None):
        myquery = {"uid": uid}
        data = self.tradertable.find_one(myquery)
        if data["num_followed"] == 1:
            self.tradertable.delete_one(myquery)
        else:
            data["num_followed"] -= 1
            self.tradertable.replace_one(myquery, data)
        if chat_id is not None:
            user = self.get_user(chat_id)
            del user["traders"][uid]
            myquery = {"chat_id": chat_id}
            self.usertable.replace_one(myquery, user)

    def insert_notification(self, noti):
        self.notitable.insert_one(noti)

    def set_all_leverage(self, chat_id, lev):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        temp = dict()
        for symbol in data["leverage"]:
            temp[f"leverage.{symbol}"] = lev
        newvalues = {"$set": temp}
        self.usertable.update_one(myquery, newvalues)
        self.updater.bot.sendMessage(chat_id, "successfully updated leverage!")

    def get_user_symbols(self, chat_id):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        return list(data["leverage"].keys())

    def set_leverage(self, chat_id, symbol, lev):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"leverage.{symbol}": lev}}
        self.usertable.update_one(myquery, newvalues)
        self.updater.bot.sendMessage(chat_id, "successfully updated leverage!")

    def list_followed_traders(self, chat_id):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        traderlist = []
        for uid in data["traders"]:
            traderlist.append(data["traders"][uid]["name"])
        return traderlist

    def set_all_proportion(self, chat_id, uid, prop):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        temp = dict()
        for symbol in data["traders"][uid]["proportion"]:
            temp[f"traders.{uid}.proportion.{symbol}"] = prop
        newvalues = {"$set": temp}
        self.usertable.update_many(myquery, newvalues)

    def set_proportion(self, chat_id, uid, symbol, prop):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"traders.{uid}.proportion.{symbol}": prop}}
        self.usertable.update_one(myquery, newvalues)
        self.updater.bot.sendMessage(chat_id, "Successfully changed proportion!")

    def query_field(self, chat_id, *args):
        myquery = {"chat_id": chat_id}
        result = self.usertable.find_one(myquery)
        for key in list(args):
            result = result[key]
        return result

    def set_all_tmode(self, chat_id, uid, tmode):
        myquery = {"chat_id": chat_id}
        data = self.usertable.find_one(myquery)
        temp = dict()
        for symbol in data["traders"][uid]["tmode"]:
            temp[f"traders.{uid}.tmode.{symbol}"] = tmode
        newvalues = {"$set": temp}
        self.usertable.update_many(myquery, newvalues)

    def set_tmode(self, chat_id, uid, symbol, tmode):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"traders.{uid}.tmode.{symbol}": tmode}}
        self.usertable.update_one(myquery, newvalues)

    def set_safety(self, chat_id, sr):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"safety_ratio": sr}}
        self.usertable.update_one(myquery, newvalues)

    def set_slippage(self, chat_id, sr):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"slippage": sr}}
        self.usertable.update_one(myquery, newvalues)

    def set_api(self, chat_id, key, secret):
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"api_key": key, "api_secret": secret}}
        self.usertable.update_one(myquery, newvalues)

    def check_uta(self, session):
        try:
            res = session.get_account_info()
            res = res["result"]["unifiedMarginStatus"]
            if res == 3 or res == 4:
                return True
            return False
        except Exception as e:
            logger.error(f"Check UTA {e}")
        return False

    def get_balance(self, chat_id):
        result = self.usertable.find_one({"chat_id": chat_id})
        try:
            client = HTTP(
                testnet=False,
                api_key=result["api_key"],
                api_secret=result["api_secret"],
            )
            if self.check_uta(client):
                result = client.get_wallet_balance(accountType="UNIFIED", coin="USDT")[
                    "result"
                ]["list"][0]["coin"][0]
            else:
                result = client.get_wallet_balance(accountType="CONTACT", coin="USDT")[
                    "result"
                ]["list"][0]["coin"][0]
            tosend = f"Your USDT account balance:\nBalance: {result['equity']}\nAvailable: {result['availableToWithdraw']}\nRealised PNL: {result['cumRealisedPnl']}\nUnrealized PNL: {result['unrealisedPnl']}"
            self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
        except Exception as e:
            logger.info(str(e))
            self.updater.bot.sendMessage(
                chat_id=chat_id, text="Unable to retrieve balance."
            )

    def get_positions(self, chat_id):
        result = self.usertable.find_one({"chat_id": chat_id})
        try:
            client = HTTP(
                testnet=False,
                api_key=result["api_key"],
                api_secret=result["api_secret"],
            )
            havenext = True
            npc = None
            allpos = []
            while havenext:
                havenext = False
                try:
                    if npc is None:
                        result2 = client.get_positions(
                            category="linear", settleCoin="USDT"
                        )["result"]
                    else:
                        result2 = client.get_positions(
                            category="linear", settleCoin="USDT", cursor=npc
                        )["result"]
                    allpos.extend(result2["list"])
                except Exception as e:
                    logger.error(f"Other errors {e}")
                    return -1
                if "nextPageCursor" in result2 and result2["nextPageCursor"] != "":
                    npc = result2["nextPageCursor"]
                    havenext = True
        except:
            logger.error("Other errors")
        try:
            symbol = []
            size = []
            EnPrice = []
            MarkPrice = []
            PNL = []
            margin = []
            for pos in allpos:
                if float(pos["size"]) != 0:
                    try:
                        mp = client.get_mark_price_kline(
                            category="linear", interval=1, limit=1, symbol=pos["symbol"]
                        )["result"]["list"][0][1]
                    except:
                        mp = pos["avgPrice"]
                    symbol.append(pos["symbol"])
                    tsize = pos["size"]
                    tsize = float(tsize) if pos["side"] == "Buy" else -float(tsize)
                    size.append(tsize)
                    EnPrice.append(pos["avgPrice"])
                    MarkPrice.append(mp)
                    PNL.append(pos["unrealisedPnl"])
                    margin.append(pos["leverage"])
            newPosition = pd.DataFrame(
                {
                    "symbol": symbol,
                    "size": size,
                    "Entry Price": EnPrice,
                    "Mark Price": MarkPrice,
                    "PNL": PNL,
                    "leverage": margin,
                }
            )
            numrows = newPosition.shape[0]
            if numrows <= 10:
                tosend = (
                    f"Your current Position: " + "\n" + newPosition.to_string() + "\n"
                )
                self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
            else:
                firstdf = newPosition.iloc[0:10]
                tosend = (
                    f"Your current Position: "
                    + "\n"
                    + firstdf.to_string()
                    + "\n(cont...)"
                )
                self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                for i in range(numrows // 10):
                    seconddf = newPosition.iloc[
                        (i + 1) * 10 : min(numrows, (i + 2) * 10)
                    ]
                    if not seconddf.empty:
                        self.updater.bot.sendMessage(
                            chat_id=chat_id, text=seconddf.to_string()
                        )
        except Exception as e:
            logger.info(f"hi {str(e)}")
            self.updater.bot.sendMessage(chat_id, "Unable to get positions.")
        return
