from telegram.ext import (
    ConversationHandler,
    CallbackContext,
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
import telegram
import os
from io import StringIO
import signal
import pandas as pd
import threading
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
)
from datetime import datetime
import requests
from app.data.credentials import ip, admin_chatid, headers

import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

(
    COOKIE,
    CSRF,
    COOKIELABEL,
    AUTH,
    SLIPPAGE,
    CLOSEALL,
    SEP1,
    SEP2,
    COCO,
    TRADERURL,
    MUTE1,
    MUTE2,
    MUTE3,
    ALLPROP2,
    REALSETPROP4,
    LEVTRADER6,
    LEVTRADER7,
    REALSETLEV7,
    LEVTRADER3,
    REALSETLEV4,
    LEVTRADER4,
    REALSETLEV5,
    LEVTRADER5,
    REALSETLEV6,
    TRADERURL2,
    LEVTRADER2,
    REALSETLEV3,
    TRADERNAME,
    AUTH2,
    ANNOUNCE,
    DISCLAIMER,
    VIEWTRADER,
    TP,
    SL,
    TOTRADE,
    TMODE,
    LMODE,
    APIKEY,
    APISECRET,
    ALLLEV,
    REALSETLEV,
    LEVTRADER,
    LEVSYM,
    REALSETLEV2,
    ALLPROP,
    REALSETPROP,
    PROPTRADER,
    PROPSYM,
    REALSETPROP2,
    PROPTRADER3,
    PROPSYM3,
    REALSETPROP5,
    PROPTRADER2,
    PROPSYM2,
    REALSETPROP3,
    SAFERATIO,
    SEP3,
    CP1,
    PLATFORM,
) = range(59)


class tgHandlers:
    def __init__(self, upd, db, authcode, admincode, glb):
        self.dbobject = db
        self.auth_code = authcode
        self.admin_code = admincode
        self.updater = upd
        self.globals = glb
        return

    @staticmethod
    def format_username(x, y):
        words = []
        prev_idx = 0
        for i, ch in enumerate(x):
            result = y.find(x[prev_idx:i])
            if result == -1:
                words.append(x[prev_idx : i - 1])
                prev_idx = i - 1
        words.append(x[prev_idx:])
        return words[-1]

    @staticmethod
    def split(a, n):
        if n == 0:
            return [a]
        k, m = divmod(len(a), n)
        return [a[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(n)]

    def initUserThread(
        self,
        chat_id,
        uname,
        safe_ratio,
        trader_name,
        trader_uid,
        api_key,
        api_secret,
        toTrade,
        tmode,
    ):
        # get symbols, set all leverage to 5x, proportion to 0
        res = self.globals.get_all_symbols()
        lev = dict()
        prop = dict()
        tmoded = dict()
        for sym in res:
            lev[sym] = 5
            prop[sym] = 0
            tmoded[sym] = tmode
        user_doc = {
            "api_key": api_key,
            "api_secret": api_secret,
            "chat_id": chat_id,
            "uname": uname,
            "safety_ratio": safe_ratio,
            "slippage": 0.05,
            "leverage": lev,
            "traders": {
                trader_uid: {
                    "name": trader_name,
                    "proportion": prop,
                    "uid": trader_uid,
                    "toTrade": toTrade,
                    "tmode": tmoded,
                    "positions": {},
                }
            },
        }
        # add to database
        self.dbobject.add_user(chat_id, user_doc)
        # next: init trader and send to everyone following
        traderdoc = self.dbobject.get_trader(trader_name)
        if traderdoc is not None:
            traderdoc["num_followed"] += 1
            self.dbobject.update_trader(trader_uid, traderdoc)
            self.updater.bot.sendMessage(
                chat_id=chat_id,
                text=f"Thanks! {trader_name}'s latest position:",
            )
            df = pd.read_json(StringIO(traderdoc["positions"]))
            numrows = df.shape[0]
            if numrows <= 10:
                tosend = f"Trader {traderdoc['name']}" + "\n" + df.to_string() + "\n"
                self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
            else:
                firstdf = df.iloc[0:10]
                tosend = (
                    f"Trader {traderdoc['name']}: "
                    + "\n"
                    + firstdf.to_string()
                    + "\n(cont...)"
                )
                self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                for i in range(numrows // 10):
                    seconddf = df.iloc[(i + 1) * 10 : min(numrows, (i + 2) * 10)]
                    if not seconddf.empty:
                        self.updater.bot.sendMessage(
                            chat_id=chat_id, text=seconddf.to_string()
                        )
            balance = self.totalbalance(df)
            self.updater.bot.sendMessage(
                chat_id=chat_id, text=f"Total USDT Position balance: {balance}"
            )
            if toTrade:
                self.updater.bot.sendMessage(
                    chat_id=chat_id,
                    text="*All your proportions have been set to 0x , all leverage has ben set to 5x, and your slippage has been set to 0.05. Change these settings with extreme caution.*",
                    parse_mode=telegram.ParseMode.MARKDOWN,
                )
        else:
            # add to trader database
            df = self.globals.get_init_traderPosition(trader_uid, self.dbobject)
            try:
                df = df.to_json()
            except:
                df = "x"
            traderdoc = {
                "uid": trader_uid,
                "positions": df,
                "lastPosTime": datetime.now().strftime("%y-%m-%d %H:%M:%S"),
                "name": trader_name,
                "num_followed": 1,
            }
            self.dbobject.add_trader(traderdoc)
            self.updater.bot.sendMessage(
                chat_id=chat_id,
                text=f"Thanks! {trader_name}'s latest position:",
            )
            try:
                df = pd.read_json(StringIO(traderdoc["positions"]))
                numrows = df.shape[0]
                if numrows <= 10:
                    tosend = (
                        f"Trader {traderdoc['name']}" + "\n" + df.to_string() + "\n"
                    )
                    self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                else:
                    firstdf = df.iloc[0:10]
                    tosend = (
                        f"Trader {traderdoc['name']}: "
                        + "\n"
                        + firstdf.to_string()
                        + "\n(cont...)"
                    )
                    self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                    for i in range(numrows // 10):
                        seconddf = df.iloc[(i + 1) * 10 : min(numrows, (i + 2) * 10)]
                        if not seconddf.empty:
                            self.updater.bot.sendMessage(
                                chat_id=chat_id, text=seconddf.to_string()
                            )
                balance = self.totalbalance(df)
                self.updater.bot.sendMessage(
                    chat_id=chat_id, text=f"Total USDT Position balance: {balance}"
                )
            except:
                self.updater.bot.sendMessage(chat_id=chat_id, text="No Positions.")
            if toTrade:
                self.updater.bot.sendMessage(
                    chat_id=chat_id,
                    text="*All your proportions have been set to 0x , all leverage has ben set to 5x, and your slippage has been set to 0.05. Change these settings with extreme caution.*",
                    parse_mode=telegram.ParseMode.MARKDOWN,
                )

    def addTraderThread(self, chat_id, trader_name, trader_uid, toTrade, tmode):
        res = self.globals.get_all_symbols()
        prop = dict()
        tmoded = dict()
        for sym in res:
            prop[sym] = 0
            tmoded[sym] = tmode
        userdoc = self.dbobject.get_user(chat_id)
        userdoc["traders"][trader_uid] = {
            "name": trader_name,
            "proportion": prop,
            "uid": trader_uid,
            "toTrade": toTrade,
            "tmode": tmoded,
            "positions": {},
        }
        self.dbobject.update_user(chat_id, userdoc)
        traderdoc = self.dbobject.get_trader(trader_name)
        if traderdoc is not None:
            traderdoc["num_followed"] += 1
            self.dbobject.update_trader(trader_uid, traderdoc)
            self.updater.bot.sendMessage(
                chat_id=chat_id,
                text=f"Thanks! {trader_name}'s latest position:",
            )
            try:
                df = pd.read_json(StringIO(traderdoc["positions"]))
                numrows = df.shape[0]
                if numrows <= 10:
                    tosend = (
                        f"Trader {traderdoc['name']}" + "\n" + df.to_string() + "\n"
                    )
                    self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                else:
                    firstdf = df.iloc[0:10]
                    tosend = (
                        f"Trader {traderdoc['name']}: "
                        + "\n"
                        + firstdf.to_string()
                        + "\n(cont...)"
                    )
                    self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                    for i in range(numrows // 10):
                        seconddf = df.iloc[(i + 1) * 10 : min(numrows, (i + 2) * 10)]
                        if not seconddf.empty:
                            self.updater.bot.sendMessage(
                                chat_id=chat_id, text=seconddf.to_string()
                            )
                balance = self.totalbalance(df)
                self.updater.bot.sendMessage(
                    chat_id=chat_id, text=f"Total USDT Position balance: {balance}"
                )
            except:
                self.updater.bot.sendMessage(chat_id=chat_id, text="No Positions.")
            if toTrade:
                self.updater.bot.sendMessage(
                    chat_id=chat_id,
                    text="*All your proportions have been set to 0x , all leverage has ben set to 5x, and your slippage has been set to 0.05. Change these settings with extreme caution.*",
                    parse_mode=telegram.ParseMode.MARKDOWN,
                )
        else:
            # add to trader database
            df = self.globals.get_init_traderPosition(trader_uid, self.dbobject)
            try:
                df = df.to_json()
            except:
                df = "x"
            traderdoc = {
                "uid": trader_uid,
                "positions": df,
                "lastPosTime": datetime.now().strftime("%y-%m-%d %H:%M:%S"),
                "name": trader_name,
                "num_followed": 1,
            }
            self.dbobject.add_trader(traderdoc)
            self.updater.bot.sendMessage(
                chat_id=chat_id,
                text=f"Thanks! {trader_name}'s latest position:",
            )
            try:
                df = pd.read_json(StringIO(traderdoc["positions"]))
                numrows = df.shape[0]
                if numrows <= 10:
                    tosend = (
                        f"Trader {traderdoc['name']}" + "\n" + df.to_string() + "\n"
                    )
                    self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                else:
                    firstdf = df.iloc[0:10]
                    tosend = (
                        f"Trader {traderdoc['name']}: "
                        + "\n"
                        + firstdf.to_string()
                        + "\n(cont...)"
                    )
                    self.updater.bot.sendMessage(chat_id=chat_id, text=tosend)
                    for i in range(numrows // 10):
                        seconddf = df.iloc[(i + 1) * 10 : min(numrows, (i + 2) * 10)]
                        if not seconddf.empty:
                            self.updater.bot.sendMessage(
                                chat_id=chat_id, text=seconddf.to_string()
                            )
                balance = self.totalbalance(df)
                self.updater.bot.sendMessage(
                    chat_id=chat_id, text=f"Total USDT Position balance: {balance}"
                )
            except:
                self.updater.bot.sendMessage(chat_id=chat_id, text="No Positions.")
            if toTrade:
                self.updater.bot.sendMessage(
                    chat_id=chat_id,
                    text="*All your proportions have been set to 0x , all leverage has ben set to 5x, and your slippage has been set to 0.05. Change these settings with extreme caution.*",
                    parse_mode=telegram.ParseMode.MARKDOWN,
                )

    def retrieveUserName(self, uid):
        name = ""
        try:
            r = requests.post(
                "https://www.binance.com/bapi/futures/v2/public/future/leaderboard/getOtherLeaderboardBaseInfo",
                json={"encryptedUid": uid},
            )
            assert r.status_code == 200
            name = r.json()["data"]["nickName"]
        except:
            return None
        return name

    def start(self, update: Update, context: CallbackContext) -> int:
        # if self.dbobject.check_presence(update.message.chat_id):
        #     update.message.reply_text(
        #         "You have already initalized! Please use other commands, or use /end to end current session before initializing another."
        #     )
        #     return ConversationHandler.END
        logger.info(f"{update.message.from_user.username} is registering.")
        allowed_users = self.dbobject.find_allowed_user(
            update.message.from_user.username
        )
        if allowed_users is None:
            update.message.reply_text(
                "Sorry! You are not white-listed to use this bot."
            )
            return ConversationHandler.END
        update.message.reply_text(
            f'*Welcome {update.message.from_user.first_name}!* Before you start, please confirm that you agree to the disclaimer (type "yes" in lowercase).',
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        context.user_data["uname"] = update.message.from_user.first_name
        return DISCLAIMER

    def auth_check(self, update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        logger.info(
            "%s is doing authentication check.", update.message.from_user.first_name
        )
        if update.message.text == self.auth_code:
            update.message.reply_text(
                'Great! Please read the following disclaimer:\nThis software is for non-commercial purposes only.\n\
                Do not risk money which you are afraid to lose.\nUSE THIS SOFTWARE AT YOUR OWN RISK.\n*THE DEVELOPERS ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS.*\n\
                Do not engage money before you understand how it works and what profit/loss you should expect. \n\
                Type "yes" (lowercase) if you agree. Otherwise type /cancel and exit.',
                parse_mode=telegram.ParseMode.MARKDOWN,
            )
            return DISCLAIMER
        else:
            update.message.reply_text(
                "Sorry! The access code is wrong. Type /start again if you need to retry."
            )
            return ConversationHandler.END

    def disclaimer_check(self, update: Update, context: CallbackContext):
        logger.info(
            "%s has agreed to the disclaimer.", update.message.from_user.first_name
        )
        context.user_data["is_sub"] = False
        # update.message.reply_text(
        #     "Please enter 2. (This field Reserved for choosing platforms, but currently only bybit is supported)."  # choose the platform:\n1. AAX\n2. Bybit\n3.Binance\nPlease enter your choice (1,2,3)"
        # )
        update.message.reply_text(
            f"Please provide your API key from Bybit. Bind your API key to the IP address {ip}."
        )
        return APIKEY

    def check_api(self, update: Update, context: CallbackContext):
        context.user_data["api_key"] = update.message.text
        if not update.message.text.isalnum():
            update.message.reply_text("Your API key is invalid, please enter again.")
            return APIKEY
        update.message.reply_text(
            "Please provide your Secret Key.\n*DELETE YOUR MESSAGE IMMEDIATELY AFTERWARDS.*",
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        return APISECRET

    def check_secret(self, update: Update, context: CallbackContext):
        context.user_data["api_secret"] = update.message.text
        if not update.message.text.isalnum():
            update.message.reply_text("Your secret key is invalid, please enter again.")
            return APISECRET
        uid = self.dbobject.get_uid(
            context.user_data["api_key"], context.user_data["api_secret"]
        )
        user = self.dbobject.find_allowed_user(
            update.message.from_user.username, str(uid)
        )
        logger.info(f"Check uid {uid}")
        # if user is None:
        #     update.message.reply_text(
        #         "The API you use has not been whitelisted to use the bot. Sorry! Please contact the admin."
        #     )
        #     return ConversationHandler.END
        update.message.reply_text(
            "Now, please provide the UID of the trader you want to follow. (can be found in the trader's URL)"
        )
        context.user_data["safe_ratio"] = 1  # preset this to 1 first.
        return TRADERURL

    def url_check(self, update: Update, context: CallbackContext) -> int:
        url = update.message.text
        context.user_data["uid"] = url
        update.message.reply_text("Please wait...")
        logger.info(
            "%s has entered the first url.", update.message.from_user.first_name
        )
        traderName = self.retrieveUserName(url)
        if traderName is None:
            update.message.reply_text(
                "Sorry! Your UID is invalid. Please try entering again."
            )
            return TRADERURL
        context.user_data["name"] = traderName
        context.user_data["First"] = True
        update.message.reply_text(
            f"Do you want us to copy the positions of {traderName} automatically, or do you only want to follow and get alerts?"
        )
        update.message.reply_text(
            "Pick 'yes' to set up copy trade, 'no' to just follow.",
            reply_markup=ReplyKeyboardMarkup([["yes", "no"]], one_time_keyboard=True),
        )
        return TOTRADE

    def trade_confirm(self, update: Update, context: CallbackContext):
        response = update.message.text
        if response == "yes":
            context.user_data["toTrade"] = True
            context.user_data["tmode"] = 0
            if context.user_data["First"]:
                t1 = threading.Thread(
                    target=self.initUserThread,
                    args=(
                        update.message.chat_id,
                        context.user_data["uname"],
                        context.user_data["safe_ratio"],
                        context.user_data["name"],
                        context.user_data["uid"],
                        context.user_data["api_key"],
                        context.user_data["api_secret"],
                        context.user_data["toTrade"],
                        context.user_data["tmode"],
                    ),
                )
                t1.start()
            else:
                t1 = threading.Thread(
                    target=self.addTraderThread,
                    args=(
                        update.message.chat_id,
                        context.user_data["name"],
                        context.user_data["uid"],
                        context.user_data["toTrade"],
                        context.user_data["tmode"],
                    ),
                )
                t1.start()
        else:
            context.user_data["toTrade"] = False
            update.message.reply_text(
                "Please wait...", reply_markup=ReplyKeyboardRemove()
            )
            if context.user_data["First"]:
                t1 = threading.Thread(
                    target=self.initUserThread,
                    args=(
                        update.message.chat_id,
                        context.user_data["uname"],
                        context.user_data["safe_ratio"],
                        context.user_data["name"],
                        context.user_data["uid"],
                        context.user_data["api_key"],
                        context.user_data["api_secret"],
                        context.user_data["toTrade"],
                        -1,
                    ),
                )
                t1.start()
            else:
                t1 = threading.Thread(
                    target=self.addTraderThread,
                    args=(
                        update.message.chat_id,
                        context.user_data["name"],
                        context.user_data["uid"],
                        context.user_data["toTrade"],
                        -1,
                    ),
                )
                t1.start()
            return ConversationHandler.END
        # update.message.reply_text("Please select the default trading mode:")
        # update.message.reply_text(
        #     "0. MARKET: Once we detected a change in position, you will make an order immediately at the market price. As a result, your entry price might deviate from the trader's entry price (especially when there are significant market movements)."
        # )
        # update.message.reply_text(
        #     "1. LIMIT: You will make an limit order at the same price as the trader's estimated entry price. However, due to fluctuating market movements, your order might not be fulfilled."
        # )
        # update.message.reply_text(
        #     "2. LIMIT, THEN MARKET: When opening positions, you will make an limit order at the same price as the trader's estimated entry price. When closing positions, you will follow market."
        # )
        # update.message.reply_text(
        #     "Please type 0,1 or 2 to indicate your choice. Note that you can change it later for every (trader,symbol) pair."
        # )

        return ConversationHandler.END

    # def tmode_confirm(self, update: Update, context: CallbackContext):
    #     context.user_data["tmode"] = int(update.message.text)
    #     update.message.reply_text("Please wait...", reply_markup=ReplyKeyboardRemove())
    #     if context.user_data["First"]:
    #         t1 = threading.Thread(
    #             target=self.initUserThread,
    #             args=(
    #                 update.message.chat_id,
    #                 context.user_data["uname"],
    #                 context.user_data["safe_ratio"],
    #                 context.user_data["name"],
    #                 context.user_data["uid"],
    #                 context.user_data["api_key"],
    #                 context.user_data["api_secret"],
    #                 context.user_data["toTrade"],
    #                 context.user_data["tmode"],
    #             ),
    #         )
    #         t1.start()
    #     else:
    #         t1 = threading.Thread(
    #             target=self.addTraderThread,
    #             args=(
    #                 update.message.chat_id,
    #                 context.user_data["name"],
    #                 context.user_data["uid"],
    #                 context.user_data["toTrade"],
    #                 context.user_data["tmode"],
    #             ),
    #         )
    #         t1.start()
    #     return ConversationHandler.END

    def cancel(self, update: Update, context: CallbackContext) -> int:
        """Cancels and ends the conversation."""
        logger.info(
            "User %s canceled the conversation.", update.message.from_user.first_name
        )
        update.message.reply_text(
            "Operation canceled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    def add_trader(self, update: Update, context: CallbackContext) -> int:
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        context.user_data["uname"] = update.message.from_user.first_name
        update.message.reply_text(
            "Please enter UID of the trader you want to add. (can be found in the trader's URL)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return TRADERURL2

    def url_add(self, update: Update, context: CallbackContext) -> int:
        context.user_data["uid"] = update.message.text
        user = self.dbobject.get_user(update.message.chat_id)
        if context.user_data["uid"] in user["traders"].keys():
            update.message.reply_text("You have already added this trader.")
            return ConversationHandler.END
        traderName = self.retrieveUserName(context.user_data["uid"])
        if traderName is None:
            update.message.reply_text(
                "Sorry! Your UID is invalid. Please try entering again."
            )
            return TRADERURL2
        context.user_data["name"] = traderName
        context.user_data["First"] = False
        update.message.reply_text(
            f"Do you want us to copy the positions of {traderName} automatically, or do you only want to follow and get alerts?"
        )
        update.message.reply_text(
            "Pick 'yes' to set up copy trade, 'no' to just follow.",
            reply_markup=ReplyKeyboardMarkup([["yes", "no"]], one_time_keyboard=True),
        )
        return TOTRADE

    def delete_trader(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listtraders = self.dbobject.get_trader_list(update.message.chat_id)
        if len(listtraders) == 0:
            update.message.reply_text("You are not following any traders.")
            return ConversationHandler.END
        listtraders = self.split(listtraders, len(listtraders) // 2)
        update.message.reply_text(
            "Please choose the trader to remove.\n(/cancel to cancel)",
            reply_markup=ReplyKeyboardMarkup(
                listtraders,
                one_time_keyboard=True,
                input_field_placeholder="Which Trader?",
            ),
        )
        return TRADERNAME

    def view_trader(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listtraders = self.dbobject.get_trader_list(update.message.chat_id)
        if len(listtraders) == 0:
            update.message.reply_text("You are not following any traders.")
            return ConversationHandler.END
        listtraders = self.split(listtraders, len(listtraders) // 2)
        update.message.reply_text(
            "Please choose the trader to view.\n(/cancel to cancel)",
            reply_markup=ReplyKeyboardMarkup(
                listtraders,
                one_time_keyboard=True,
                input_field_placeholder="Which Trader?",
            ),
        )
        return VIEWTRADER

    def totalbalance(self, df):
        total = 0
        for index, row in df.iterrows():
            size = float(row["size"])
            mark_price = float(row["Mark Price"])
            symbol = row["symbol"]
            if symbol[-4:] == "USDT":
                total += abs(size * mark_price)
        return round(total, 4)
        # Rest of your code here

    def view_traderInfo(self, update: Update, context: CallbackContext):
        traderinfo = self.dbobject.get_trader(update.message.text)
        update.message.reply_text(
            f"{update.message.text}'s current position: \n(Last position update: {str(traderinfo['lastPosTime'])})",
            reply_markup=ReplyKeyboardRemove(),
        )
        msg = traderinfo["positions"]
        if msg == "x":
            update.message.reply_text("None.")
        else:
            msg = pd.read_json(StringIO(msg))
            numrows = msg.shape[0]
            if numrows <= 10:
                update.message.reply_text(f"{msg.to_string()}")
            else:
                firstdf = msg.iloc[0:10]
                tosend = firstdf.to_string() + "\n(cont...)"
                update.message.reply_text(f"{tosend}")
                for i in range(numrows // 10):
                    seconddf = msg.iloc[(i + 1) * 10 : min(numrows, (i + 2) * 10)]
                    if not seconddf.empty:
                        update.message.reply_text(f"{seconddf.to_string()}")
            update.message.reply_text(
                f"Total USDT Position balance: {self.totalbalance(msg)}"
            )
        # update.message.reply_text(f"Successfully removed {update.message.text}.")
        return ConversationHandler.END

    def delTrader(self, update: Update, context: CallbackContext):
        logger.info("deleting trader %s.", update.message.text)
        try:
            traderinfo = self.dbobject.get_trader_fromuser(
                update.message.chat_id, update.message.text
            )
            assert traderinfo is not None
        except:
            update.message.reply_text("This is not a valid trader.")
            return ConversationHandler.END
        context.user_data["trader"] = traderinfo["uid"]
        update.message.reply_text(
            "Do you wish to close all positions with the trader automatically?",
            reply_markup=ReplyKeyboardMarkup([["yes", "no"]], one_time_keyboard=True),
        )
        return CLOSEALL

    def delete_closePos(self, update, context):
        if update.message.text == "no":
            logger.info(context.user_data["trader"])
            self.dbobject.delete_trader(
                context.user_data["trader"], update.message.chat_id
            )
            update.message.reply_text("Success!", reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text("Closing all positions...")
            self.dbobject.insert_notification(
                {
                    "cmd": "delete_and_closeall",
                    "user": update.message.chat_id,
                    "trader": context.user_data["trader"],
                }
            )
            self.dbobject.delete_trader(context.user_data["trader"])
        return ConversationHandler.END

    def end_all(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return
        logger.info("%s ended the service.", update.message.from_user.first_name)
        update.message.reply_text(
            "Confirm ending the service? This means that we will not make trades for you anymore and you have to take care of the positions previously opened by yourself. Type 'yes' to confirm, /cancel to cancel."
        )
        return COCO

    def realEndAll(self, update: Update, context: CallbackContext):
        self.dbobject.deleteuser(update.message.chat_id)
        update.message.reply_text(
            "Sorry to see you go. You can press /start to restart the service."
        )
        return ConversationHandler.END

    def admin(self, update: Update, context: CallbackContext):
        logger.info(
            "%s is doing authentication check for admin.",
            update.message.from_user.first_name,
        )
        if not update.message.chat_id in admin_chatid:
            update.message.reply_text(
                "Sorry you are not authorized to access this endpoint."
            )
            return ConversationHandler.END
        update.message.reply_text(
            "Great! /cancel to cancel, /addcookie to add cookie, /viewcookie to view cookie."
        )
        return ANNOUNCE

    def add_cookie(self, update: Update, context: CallbackContext):
        update.message.reply_text("Please enter the cookie copied from binance.")
        return COOKIE

    def add_csrf(self, update: Update, context: CallbackContext):
        context.user_data["cookie"] = update.message.text
        update.message.reply_text("Please enter the csrftoken.")
        return COOKIELABEL

    def add_cookie_label(self, update: Update, context: CallbackContext):
        context.user_data["csrftoken"] = update.message.text
        update.message.reply_text("Enter a label for this cookie.")
        return CSRF

    def add_credential(self, update: Update, context: CallbackContext):
        self.dbobject.add_credential(
            context.user_data["cookie"],
            context.user_data["csrftoken"],
            update.message.text,
        )
        update.message.reply_text("Success!!!")
        return ConversationHandler.END

    def show_cookie(self, update: Update, context: CallbackContext):
        data = self.dbobject.get_cookies()
        msg = "The cookies in database are:\n"
        for i, cookie in enumerate(data):
            msg += f"{i+1}. {cookie['label']}\n"
        update.message.reply_text(msg)
        return ConversationHandler.END

    def announce(self, update: Update, context: CallbackContext):
        for doc in self.dbobject.getall("usertable"):
            chatid = doc["chat_id"]
            self.updater.bot.sendMessage(chat_id=chatid, text=update.message.text)
        logger.info("Message announced for all users.")
        return ConversationHandler.END

    def set_all_leverage(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        update.message.reply_text(
            "Please enter the target leverage (Integer between 1 and 125)"
        )
        return REALSETLEV

    def setAllLeverageReal(self, update: Update, context: CallbackContext):
        try:
            lev = int(update.message.text)
            assert lev >= 1 and lev <= 125
        except:
            update.message.reply_text(
                "This is not a valid leverage, please enter again."
            )
            return REALSETLEV
        self.dbobject.set_all_leverage(update.message.chat_id, lev)
        return ConversationHandler.END

    def set_leverage(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        listsymbols = [[x] for x in listsymbols]
        update.message.reply_text(
            "Please choose the symbol to set.",
            reply_markup=ReplyKeyboardMarkup(
                listsymbols,
                one_time_keyboard=True,
                input_field_placeholder="Which Symbol?",
            ),
        )
        return LEVSYM

    def leverage_choosesymbol(self, update: Update, context: CallbackContext):
        context.user_data["symbol"] = update.message.text
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        if update.message.text not in listsymbols:
            listsymbols = [[x] for x in listsymbols]
            update.message.reply_text(
                "Sorry, the symbol is not valid, please choose again.",
                reply_markup=ReplyKeyboardMarkup(
                    listsymbols,
                    one_time_keyboard=True,
                    input_field_placeholder="Which Symbol?",
                ),
            )
            return LEVSYM
        update.message.reply_text(
            "Please enter the target leverage (Integer between 1 and 125)"
        )
        return REALSETLEV2

    def setLeverageReal(self, update: Update, context: CallbackContext):
        try:
            lev = int(update.message.text)
            assert lev >= 1 and lev <= 125
        except:
            update.message.reply_text(
                "This is not a valid leverage, please enter again."
            )
            return REALSETLEV
        self.dbobject.set_leverage(
            update.message.chat_id,
            context.user_data["symbol"],
            lev,
        )
        update.message.reply_text(
            "The leverage is changed successfully!", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    def set_all_proportion(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listtraders = self.dbobject.list_followed_traders(update.message.chat_id)
        if len(listtraders) == 0:
            update.message.reply_text("You are not following any traders.")
            return ConversationHandler.END
        listtraders = self.split(listtraders, len(listtraders) // 2)
        update.message.reply_text(
            "Please choose the trader to set proportion for all symbols.\n(/cancel to cancel)",
            reply_markup=ReplyKeyboardMarkup(
                listtraders,
                one_time_keyboard=True,
                input_field_placeholder="Which Trader?",
            ),
        )
        return ALLPROP

    def setAllProportion(self, update: Update, context: CallbackContext):
        logger.info(f"User adjusting proportion.")
        traderinfo = self.dbobject.get_trader_fromuser(
            update.message.chat_id, update.message.text
        )
        if ("toTrade" not in traderinfo) or (not traderinfo["toTrade"]):
            update.message.reply_text(
                "You did not set copy trade option for this trader. If needed, /delete this trader and /add again.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END
        context.user_data["trader"] = traderinfo["uid"]
        update.message.reply_text("Please enter the target proportion.")
        return REALSETPROP

    def setAllProportionReal(self, update: Update, context: CallbackContext):
        try:
            prop = float(update.message.text)
            assert prop >= 0
        except:
            update.message.reply_text(
                "This is not a valid proportion, please enter again."
            )
            return REALSETPROP
        self.dbobject.set_all_proportion(
            update.message.chat_id, context.user_data["trader"], prop
        )
        update.message.reply_text("Success!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def set_proportion(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listtraders = self.dbobject.list_followed_traders(update.message.chat_id)
        if len(listtraders) == 0:
            update.message.reply_text("You are not following any traders.")
            return ConversationHandler.END
        listtraders = self.split(listtraders, len(listtraders) // 2)
        update.message.reply_text(
            "Please choose the trader to set proportion for.\n(/cancel to cancel)",
            reply_markup=ReplyKeyboardMarkup(
                listtraders,
                one_time_keyboard=True,
                input_field_placeholder="Which Trader?",
            ),
        )
        return PROPTRADER

    def proportion_choosetrader(self, update: Update, context: CallbackContext):
        traderinfo = self.dbobject.get_trader_fromuser(
            update.message.chat_id, update.message.text
        )
        if ("toTrade" not in traderinfo) or (not traderinfo["toTrade"]):
            update.message.reply_text(
                "You did not set copy trade option for this trader. If needed, /delete this trader and /add again."
            )
            return ConversationHandler.END
        context.user_data["trader"] = traderinfo["uid"]
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        listsymbols = [[x] for x in listsymbols]
        update.message.reply_text(
            "Please choose the symbol to set.",
            reply_markup=ReplyKeyboardMarkup(
                listsymbols,
                one_time_keyboard=True,
                input_field_placeholder="Which Symbol?",
            ),
        )
        return PROPSYM

    def proportion_choosesymbol(self, update: Update, context: CallbackContext):
        context.user_data["symbol"] = update.message.text
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        if update.message.text not in listsymbols:
            listsymbols = [[x] for x in listsymbols]
            update.message.reply_text(
                "Sorry, the symbol is not valid, please choose again.",
                reply_markup=ReplyKeyboardMarkup(
                    listsymbols,
                    one_time_keyboard=True,
                    input_field_placeholder="Which Symbol?",
                ),
            )
            return PROPSYM
        update.message.reply_text("Please enter the target proportion.")
        return REALSETPROP2

    def setProportionReal(self, update: Update, context: CallbackContext):
        try:
            prop = float(update.message.text)
            assert prop >= 0
        except:
            update.message.reply_text(
                "This is not a valid proportion, please enter again."
            )
            return REALSETPROP2
        self.dbobject.set_proportion(
            update.message.chat_id,
            context.user_data["trader"],
            context.user_data["symbol"],
            prop,
        )
        return ConversationHandler.END

    def get_leverage(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        username = self.dbobject.query_field(update.message.chat_id, "uname")
        logger.info(f"User {username} querying leverage.")
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        listsymbols = [[x] for x in listsymbols]
        update.message.reply_text(
            "Please choose the symbol.",
            reply_markup=ReplyKeyboardMarkup(
                listsymbols,
                one_time_keyboard=True,
                input_field_placeholder="Which Symbol?",
            ),
        )
        return REALSETLEV3

    def getLeverageReal(self, update: Update, context: CallbackContext):
        symbol = update.message.text
        result = self.dbobject.query_field(update.message.chat_id, "leverage", symbol)
        update.message.reply_text(
            f"The leverage set for {symbol} is {result}x.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    def get_proportion(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listtraders = self.dbobject.list_followed_traders(update.message.chat_id)
        if len(listtraders) == 0:
            update.message.reply_text("You are not following any traders.")
            return ConversationHandler.END
        listtraders = self.split(listtraders, len(listtraders) // 2)
        update.message.reply_text(
            "Please choose the trader to query proportion for.\n(/cancel to cancel)",
            reply_markup=ReplyKeyboardMarkup(
                listtraders,
                one_time_keyboard=True,
                input_field_placeholder="Which Trader?",
            ),
        )
        return LEVTRADER3

    def getproportion_choosetrader(self, update: Update, context: CallbackContext):
        traderinfo = self.dbobject.get_trader_fromuser(
            update.message.chat_id, update.message.text
        )
        if ("toTrade" not in traderinfo) or (not traderinfo["toTrade"]):
            update.message.reply_text(
                "You did not set copy trade option for this trader. If needed, /delete this trader and /add again."
            )
            return ConversationHandler.END
        context.user_data["trader"] = traderinfo["uid"]
        context.user_data["traderName"] = traderinfo["name"]
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        listsymbols = [[x] for x in listsymbols]
        update.message.reply_text(
            "Please choose the symbol.",
            reply_markup=ReplyKeyboardMarkup(
                listsymbols,
                one_time_keyboard=True,
                input_field_placeholder="Which Symbol?",
            ),
        )
        return REALSETLEV4

    def getproportionReal(self, update: Update, context: CallbackContext):
        symbol = update.message.text
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        if symbol not in listsymbols:
            listsymbols = [[x] for x in listsymbols]
            update.message.reply_text(
                "Sorry, the symbol is not valid, please choose again.",
                reply_markup=ReplyKeyboardMarkup(
                    listsymbols,
                    one_time_keyboard=True,
                    input_field_placeholder="Which Symbol?",
                ),
            )
            return REALSETLEV4
        result = self.dbobject.query_field(
            update.message.chat_id,
            "traders",
            context.user_data["trader"],
            "proportion",
            symbol,
        )
        update.message.reply_text(
            f"The proportion set for {context.user_data['traderName']}, {symbol} is {result}x.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    def set_omode(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listtraders = self.dbobject.list_followed_traders(update.message.chat_id)
        if len(listtraders) == 0:
            update.message.reply_text("You are not following any traders.")
            return ConversationHandler.END
        listtraders = self.split(listtraders, len(listtraders) // 2)
        update.message.reply_text(
            "Please choose the trader to set trading mode for.\n(/cancel to cancel)",
            reply_markup=ReplyKeyboardMarkup(
                listtraders,
                one_time_keyboard=True,
                input_field_placeholder="Which Trader?",
            ),
        )
        return PROPTRADER2

    def omode_choosetrader(self, update: Update, context: CallbackContext):
        traderinfo = self.dbobject.get_trader_fromuser(
            update.message.chat_id, update.message.text
        )
        if ("toTrade" not in traderinfo) or (not traderinfo["toTrade"]):
            update.message.reply_text(
                "You did not set copy trade option for this trader. If needed, /delete this trader and /add again."
            )
            return ConversationHandler.END
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        listsymbols = [[x] for x in listsymbols]
        context.user_data["trader"] = traderinfo["uid"]
        update.message.reply_text(
            "Please choose the symbol to set.",
            reply_markup=ReplyKeyboardMarkup(
                listsymbols,
                one_time_keyboard=True,
                input_field_placeholder="Which Symbol?",
            ),
        )
        return PROPSYM2

    def omode_choosesymbol(self, update: Update, context: CallbackContext):
        context.user_data["symbol"] = update.message.text
        listsymbols = self.dbobject.get_user_symbols(update.message.chat_id)
        if update.message.text not in listsymbols:
            listsymbols = [[x] for x in listsymbols]
            update.message.reply_text(
                "Sorry, the symbol is not valid, please choose again.",
                reply_markup=ReplyKeyboardMarkup(
                    listsymbols,
                    one_time_keyboard=True,
                    input_field_placeholder="Which Symbol?",
                ),
            )
            return PROPSYM2
        update.message.reply_text("Please enter the target trading mode.")
        update.message.reply_text(
            "0. MARKET: Once we detected a change in position, you will make an order immediately at the market price. As a result, your entry price might deviate from the trader's entry price (especially when there are significant market movements)."
        )
        update.message.reply_text(
            "1. LIMIT: You will make an limit order at the same price as the trader's estimated entry price. However, due to fluctuating market movements, your order might not be fulfilled."
        )
        update.message.reply_text(
            "2. LIMIT, THEN MARKET: When opening positions, you will make an limit order at the same price as the trader's estimated entry price. When closing positions, you will follow market."
        )
        update.message.reply_text("Please type 0,1 or 2 to indicate your choice.")
        return REALSETPROP3

    def setomodeReal(self, update: Update, context: CallbackContext):
        try:
            tmode = int(update.message.text)
            assert tmode >= 0 and tmode <= 2
        except:
            update.message.reply_text(
                "This is not a valid trading mode, please enter again."
            )
            return REALSETPROP3
        self.dbobject.set_tmode(
            update.message.chat_id,
            context.user_data["trader"],
            context.user_data["symbol"],
            tmode,
        )
        update.message.reply_text("Success!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def set_allomode(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        listtraders = self.dbobject.list_followed_traders(update.message.chat_id)
        if len(listtraders) == 0:
            update.message.reply_text("You are not following any traders.")
            return ConversationHandler.END
        listtraders = self.split(listtraders, len(listtraders) // 2)
        update.message.reply_text(
            "Please choose the trader to set trading mode for.\n(/cancel to cancel)",
            reply_markup=ReplyKeyboardMarkup(
                listtraders,
                one_time_keyboard=True,
                input_field_placeholder="Which Trader?",
            ),
        )
        return LEVTRADER5

    def allomode_choosetrader(self, update: Update, context: CallbackContext):
        traderinfo = self.dbobject.get_trader_fromuser(
            update.message.chat_id, update.message.text
        )
        if ("toTrade" not in traderinfo) or (not traderinfo["toTrade"]):
            update.message.reply_text(
                "You did not set copy trade option for this trader. If needed, /delete this trader and /add again."
            )
            return ConversationHandler.END
        context.user_data["trader"] = traderinfo["uid"]
        update.message.reply_text("Please enter the target trading mode.")
        update.message.reply_text(
            "0. MARKET: Once we detected a change in position, you will make an order immediately at the market price. As a result, your entry price might deviate from the trader's entry price (especially when there are significant market movements)."
        )
        update.message.reply_text(
            "1. LIMIT: You will make an limit order at the same price as the trader's estimated entry price. However, due to fluctuating market movements, your order might not be fulfilled."
        )
        update.message.reply_text(
            "2. LIMIT, THEN MARKET: When opening positions, you will make an limit order at the same price as the trader's estimated entry price. When closing positions, you will follow market."
        )
        update.message.reply_text("Please type 0,1 or 2 to indicate your choice.")
        return REALSETLEV6

    def setallomodeReal(self, update: Update, context: CallbackContext):
        try:
            tmode = int(update.message.text)
            assert tmode >= 0 and tmode <= 2
        except:
            update.message.reply_text(
                "This is not a valid trading mode, please enter again."
            )
            return REALSETLEV6
        self.dbobject.set_all_tmode(
            update.message.chat_id, context.user_data["trader"], tmode
        )
        update.message.reply_text(
            f"Successfully changed trading mode!", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    def change_safetyratio(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        update.message.reply_text("Please enter the safety ratio (between 0 and 1):")
        return LEVTRADER6

    def confirm_changesafety(self, update: Update, context: CallbackContext):
        try:
            safety_ratio = float(update.message.text)
            assert safety_ratio >= 0 and safety_ratio <= 1
        except:
            update.message.reply_text("This is not a valid ratio, please enter again.")
            return LEVTRADER6
        self.dbobject.set_safety(update.message.chat_id, safety_ratio)
        update.message.reply_text("Success!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def change_slippage(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return ConversationHandler.END
        update.message.reply_text("Please enter the slippage (between 0 and 1):")
        return SLIPPAGE

    def confirm_changeslippage(self, update: Update, context: CallbackContext):
        try:
            safety_ratio = float(update.message.text)
            assert safety_ratio >= 0 and safety_ratio <= 1
        except:
            update.message.reply_text("This is not a valid ratio, please enter again.")
            return SLIPPAGE
        self.dbobject.set_slippage(update.message.chat_id, safety_ratio)
        update.message.reply_text("Success!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def change_api(self, update: Update, context: CallbackContext):
        update.message.reply_text("Please provide your API Key from Bybit.")
        update.message.reply_text(
            f"*SECURITY WARNING*\nTo ensure safety of funds, please note the following before providing your API key:\n1. Set up a new key for this program, don't reuse your other API keys.\n2. Restrict access to this IP: *{ip}*\n3. Only allow these API Restrictions: 'Enable Reading' and 'Enable Futures'.",
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        return SEP1

    def change_secret(self, update: Update, context: CallbackContext):
        username = self.dbobject.query_field(update.message.chat_id, "uname")
        logger.info(f"User {username} changing api keys.")
        if not update.message.text.isalnum():
            update.message.reply_text("Your API key is invalid, please enter again.")
            return SEP1
        update.message.reply_text(
            "Please provide your Secret Key.\n*DELETE YOUR MESSAGE IMMEDIATELY AFTERWARDS.*",
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        context.user_data["api_key"] = update.message.text
        return SEP2

    def change_bnall(self, update: Update, context: CallbackContext):
        if not update.message.text.isalnum():
            update.message.reply_text("Your secret key is invalid, please enter again.")
            return SEP2
        self.dbobject.set_api(
            update.message.chat_id, context.user_data["api_key"], update.message.text
        )
        update.message.reply_text("Success!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def check_balance(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return
        self.dbobject.get_balance(update.message.chat_id)
        # update.message.reply_text(f"Your account balance is {balance} USDT.")
        return

    def check_position(self, update: Update, context: CallbackContext):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
        pos = self.dbobject.get_positions(update.message.chat_id)
        # update.message.reply_text(f"Your current position is:\n{pos}")
        return

    def makeitcrash(self, update, context):
        assert False

    def query_setting(self, update, context):
        if not self.dbobject.check_presence(update.message.chat_id):
            update.message.reply_text("Please initalize with /start first.")
            return
        user = self.dbobject.get_user(update.message.chat_id)
        update.message.reply_text(
            f"Your safety ratio is set as {user['safety_ratio']}, and your slippage is {user['slippage']}."
        )
        return

    def error_callback(self, update, context):
        logger.error("Error!!!!!Why!!!")
        # for doc in self.dbobject.getall("usertable"):
        #     chat_id = doc["chat_id"]
        #     self.updater.bot.sendMessage(chat_id=chat_id, text="Automatic reloading...")
        for line in os.popen("ps ax | grep tgb_"):
            fields = line.split()
            pid = fields[0]
            os.kill(int(pid), signal.SIGKILL)
        exit(-1)

    def init_handlers(self):
        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("start", self.start)],
                states={
                    AUTH: [
                        MessageHandler(Filters.text & ~Filters.command, self.auth_check)
                    ],
                    DISCLAIMER: [
                        MessageHandler(Filters.regex("^(yes)$"), self.disclaimer_check)
                    ],
                    APIKEY: [
                        MessageHandler(Filters.text & ~Filters.command, self.check_api)
                    ],
                    APISECRET: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.check_secret
                        )
                    ],
                    TRADERURL: [
                        MessageHandler(Filters.text & ~Filters.command, self.url_check)
                    ],
                    TOTRADE: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.trade_confirm
                        )
                    ],
                    # SL: [
                    #     MessageHandler(
                    #         Filters.text & ~Filters.command, self.tmode_confirm
                    #     )
                    # ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("add", self.add_trader)],
                states={
                    TRADERURL2: [
                        MessageHandler(Filters.text & ~Filters.command, self.url_add)
                    ],
                    TOTRADE: [
                        MessageHandler(Filters.regex("^(yes|no)$"), self.trade_confirm)
                    ],
                    # SL: [
                    #     MessageHandler(Filters.regex("^(0|1|2)$"), self.tmode_confirm)
                    # ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("delete", self.delete_trader)],
                states={
                    TRADERNAME: [
                        MessageHandler(Filters.text & ~Filters.command, self.delTrader)
                    ],
                    CLOSEALL: [
                        MessageHandler(
                            Filters.regex("^(yes|no)$"), self.delete_closePos
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("admin", self.admin)],
                states={
                    # AUTH2: [
                    #     MessageHandler(
                    #         Filters.text & ~Filters.command, self.auth_check2
                    #     )
                    # ],
                    ANNOUNCE: [
                        # MessageHandler(Filters.text & ~Filters.command, self.announce),
                        CommandHandler("addcookie", self.add_cookie),
                        CommandHandler("viewcookie", self.show_cookie),
                    ],
                    COOKIE: [
                        MessageHandler(Filters.text & ~Filters.command, self.add_csrf),
                    ],
                    CSRF: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.add_credential
                        ),
                    ],
                    COOKIELABEL: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.add_cookie_label
                        ),
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("setallleverage", self.set_all_leverage)],
                states={
                    # ALLLEV: [
                    #     MessageHandler(
                    #         Filters.text & ~Filters.command, self.setAllLeverage
                    #     )
                    # ],
                    REALSETLEV: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.setAllLeverageReal
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("setleverage", self.set_leverage)],
                states={
                    # LEVTRADER: [
                    #     MessageHandler(
                    #         Filters.text & ~Filters.command, self.leverage_choosetrader
                    #     )
                    # ],
                    LEVSYM: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.leverage_choosesymbol
                        )
                    ],
                    REALSETLEV2: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.setLeverageReal
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("view", self.view_trader)],
                states={
                    VIEWTRADER: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.view_traderInfo
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("getleverage", self.get_leverage)],
                states={
                    # LEVTRADER2: [
                    #     MessageHandler(
                    #         Filters.text & ~Filters.command,
                    #         self.getleverage_choosetrader,
                    #     )
                    # ],
                    REALSETLEV3: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.getLeverageReal
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[
                    CommandHandler("setallproportion", self.set_all_proportion)
                ],
                states={
                    ALLPROP: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.setAllProportion
                        )
                    ],
                    REALSETPROP: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.setAllProportionReal
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("setproportion", self.set_proportion)],
                states={
                    PROPTRADER: [
                        MessageHandler(
                            Filters.text & ~Filters.command,
                            self.proportion_choosetrader,
                        )
                    ],
                    PROPSYM: [
                        MessageHandler(
                            Filters.text & ~Filters.command,
                            self.proportion_choosesymbol,
                        )
                    ],
                    REALSETPROP2: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.setProportionReal
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("getproportion", self.get_proportion)],
                states={
                    LEVTRADER3: [
                        MessageHandler(
                            Filters.text & ~Filters.command,
                            self.getproportion_choosetrader,
                        )
                    ],
                    REALSETLEV4: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.getproportionReal
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("end", self.end_all)],
                states={
                    COCO: [MessageHandler(Filters.regex("^(yes)$"), self.realEndAll)],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        # dispatcher.add_handler(
        #     ConversationHandler(
        #         entry_points=[CommandHandler("settmode", self.set_omode)],
        #         states={
        #             PROPTRADER2: [
        #                 MessageHandler(
        #                     Filters.text & ~Filters.command, self.omode_choosetrader
        #                 )
        #             ],
        #             PROPSYM2: [
        #                 MessageHandler(
        #                     Filters.text & ~Filters.command, self.omode_choosesymbol
        #                 )
        #             ],
        #             REALSETPROP3: [
        #                 MessageHandler(Filters.regex("^(0|1|2)$"), self.setomodeReal)
        #             ],
        #         },
        #         fallbacks=[CommandHandler("cancel", self.cancel)],
        #     )
        # )
        # dispatcher.add_handler(
        #     ConversationHandler(
        #         entry_points=[CommandHandler("setalltmode", self.set_allomode)],
        #         states={
        #             LEVTRADER5: [
        #                 MessageHandler(
        #                     Filters.text & ~Filters.command, self.allomode_choosetrader
        #                 )
        #             ],
        #             REALSETLEV6: [
        #                 MessageHandler(Filters.regex("^(0|1|2)$"), self.setallomodeReal)
        #             ],
        #         },
        #         fallbacks=[CommandHandler("cancel", self.cancel)],
        #     )
        # )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("changesr", self.change_safetyratio)],
                states={
                    LEVTRADER6: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.confirm_changesafety
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("changeapi", self.change_api)],
                states={
                    SEP1: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.change_secret
                        )
                    ],
                    SEP2: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.change_bnall
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("changeslip", self.change_slippage)],
                states={
                    SLIPPAGE: [
                        MessageHandler(
                            Filters.text & ~Filters.command, self.confirm_changeslippage
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )
        dispatcher.add_handler(CommandHandler("crashit", self.makeitcrash))
        dispatcher.add_handler(CommandHandler("checkbal", self.check_balance))
        dispatcher.add_handler(CommandHandler("checkpos", self.check_position))
        dispatcher.add_handler(CommandHandler("settingquery", self.query_setting))
        dispatcher.add_error_handler(self.error_callback)
