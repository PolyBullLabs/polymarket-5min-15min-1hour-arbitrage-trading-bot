import pymongo
from datetime import datetime


class ctDatabase:
    def __init__(self, glb):
        self.client = pymongo.MongoClient(glb.dbpath)
        self.db = self.client["binance"]
        self.db2 = self.client["binanceCT"]
        self.usertable = self.db["Users"]
        self.notitable = self.db["Notifications"]
        self.commandtable = self.db["Commands"]
        self.commandtable2 = self.db2["Commands"]
        self.tradertable = self.db["Traders"]
        self.historytable = self.db["TradeHistory"]
        self.cookietable = self.db["Cookies"]
        self.dblock = glb.dblock
        self.globals = glb

    def get_cookies(self):
        data = []
        self.dblock.acquire()
        for x in self.cookietable.find():
            data.append(x)
        self.dblock.release()
        return data

    def remove_cookie(self, id):
        self.cookietable.delete_one({"_id": id})

    def get_noti(self):
        data = []
        self.dblock.acquire()
        for x in self.notitable.find():
            data.append(x)
        self.dblock.release()
        return data

    def update_user(self, chat_id, userdoc):
        myquery = {"chat_id": chat_id}
        return self.usertable.replace_one(myquery, userdoc)

    def get_user(self, chat_id):
        myquery = {"chat_id": chat_id}
        return self.usertable.find_one(myquery)

    def delete_command(self, docids):
        for docid in docids:
            self.notitable.delete_one({"_id": docid})

    def fetch_following(self, uid):
        # fetch all user documents following uid.
        data = []
        self.dblock.acquire()
        for x in self.usertable.find():
            if uid in x["traders"]:
                data.append(x)
        self.dblock.release()
        return data

    def fetch_trader_position(self, uid):
        # fetch trader positions
        myquery = {"uid": uid}
        data = self.tradertable.find_one(myquery)
        return data["positions"]

    def save_position(self, uid, x, changeTime):
        # save trader positions
        myquery = {"uid": uid}
        if changeTime:
            newvalues = {
                "$set": {
                    f"positions": x,
                    "lastPosTime": datetime.now().strftime("%y-%m-%d %H:%M:%S"),
                }
            }
            history = {
                "uid": uid,
                "positions": x,
                "lastPosTime": datetime.now().strftime("%y-%m-%d %H:%M:%S"),
            }
            self.dblock.acquire()
            self.historytable.insert_one(history)
            self.dblock.release()
        else:
            newvalues = {
                "$set": {
                    f"positions": x,
                }
            }
        self.dblock.acquire()
        self.tradertable.update_one(myquery, newvalues)
        self.dblock.release()
        return 0

    def retrieve_traders(self):
        # retrieve all traders
        data = []
        self.dblock.acquire()
        for x in self.tradertable.find():
            data.append(x)
        self.dblock.release()
        return data

    def retrieve_users(self):
        # retrieve all usrs
        data = []
        self.dblock.acquire()
        for x in self.usertable.find():
            data.append(x)
        self.dblock.release()
        return data

    def update_leverage(self, chat_id, lev):
        # update user leverage
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"leverage": lev}}
        self.dblock.acquire()
        self.usertable.update_one(myquery, newvalues)
        self.dblock.release()

    def update_proportion(self, chat_id, uid, prop):
        # update user proportion
        myquery = {"chat_id": chat_id}
        newvalues = {"$set": {f"traders.{uid}.proportion": prop}}
        self.dblock.acquire()
        self.usertable.update_one(myquery, newvalues)
        self.dblock.release()

    def insert_command(self, info):
        self.dblock.acquire()
        self.commandtable.insert_one(info)
        self.dblock.release()

    def insert_command2(self, info):
        self.dblock.acquire()
        self.commandtable2.insert_one(info)
        self.dblock.release()

    def update_positions(
        self, chatid, uid, selfkey, quant, type=0
    ):  # update with our new schema
        # type 0 set 1 add 2 minus
        self.dblock.acquire()
        if type == 0:
            myquery = {"chat_id": chatid}
            newvalues = {"$set": {f"traders.{uid}.positions.{selfkey}": quant}}
            self.usertable.update_one(myquery, newvalues)
        elif type == 1:
            myquery = {"chat_id": chatid}
            data = self.usertable.find_one(myquery)
            if selfkey in data["traders"][uid]["positions"]:
                amt = data["traders"][uid]["positions"][selfkey] + quant
            else:
                amt = quant
            newvalues = {"$set": {f"traders.{uid}.positions.{selfkey}": amt}}
            self.usertable.update_one(myquery, newvalues)
        else:
            myquery = {"chat_id": chatid}
            data = self.usertable.find_one(myquery)
            if selfkey in data["traders"][uid]["positions"]:
                amt = data["traders"][uid]["positions"][selfkey]
                if amt > 0:
                    amt = max(0, amt - quant)
                else:
                    amt = min(0, amt - quant)
            else:
                amt = 0
            newvalues = {"$set": {f"traders.{uid}.positions.{selfkey}": amt}}
            self.usertable.update_one(myquery, newvalues)
        self.dblock.release()
