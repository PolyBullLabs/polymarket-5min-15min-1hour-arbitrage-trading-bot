import math
import time
import logging
import pandas as pd
import os
import signal
import datetime
import random

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
import threading
from pybit.unified_trading import HTTP


class BybitClient:
    def __init__(
        self, chat_id, uname, safety_ratio, api_key, api_secret, slippage, glb, udb
    ):
        self.client = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret,
        )
        self.globals = glb
        self.userdb = udb
        self.api_key = api_key
        self.chat_id = chat_id
        self.uname = uname
        self.spread = random.choice([i + 5 for i in range(7)])  # 5 - 11
        self.place = random.choice([i - 5 for i in range(6)])  # -5 - 0
        self.sleep = random.choice([i + 5 for i in range(6)])  # 5 - 10
        self.max_slippage = 0.01
        self.stepsize = {}
        self.ticksize = {}
        self.safety_ratio = safety_ratio
        self.isReloaded = False
        res = self.client.get_instruments_info(category="linear")
        for symbol in res["result"]["list"]:
            self.ticksize[symbol["symbol"]] = float(symbol["priceFilter"]["tickSize"])
            self.stepsize[symbol["symbol"]] = round(
                -math.log(float(symbol["lotSizeFilter"]["qtyStep"]), 10)
            )

    def get_latest_price(self, symbol):
        res = self.client.get_tickers(symbol=symbol, category="linear")
        return float(res["result"]["list"][0]["lastPrice"])

    def get_symbols(self):
        symbolList = []
        for symbol in self.stepsize:
            symbolList.append(symbol)
        return symbolList

    def algolimit(
        self, symbol, qty, side, positionIdx, isClose, ref_price, positionKey, uid
    ):
        exec_details = []
        while True:
            try:
                if isClose:
                    tosend = f"Trying to execute the following trade:\nSymbol: {symbol}\nSide: {side}\ntype: MARKET\nquantity: {qty}\n"
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "type": "telegram",
                            "chat_id": self.chat_id,
                            "message": tosend,
                        }
                    )
                    res = self.client.place_order(
                        category="linear",
                        symbol=symbol,
                        side=side,
                        orderType="Market",
                        qty=str(qty),
                        positionIdx=positionIdx,
                        reduceOnly=True,
                        closeOnTrigger=True,
                    )
                else:
                    cur_price = self.get_latest_price(symbol)
                    expected_slip = abs(cur_price - ref_price) / ref_price
                    if expected_slip > self.max_slippage:
                        self.userdb.insert_command(
                            {
                                "cmd": "send_message",
                                "type": "telegram",
                                "chat_id": self.chat_id,
                                "message": f"{positionKey} : Expected Slippage is {expected_slip:.2f}%, trade will not be executed.",
                            }
                        )
                        raise Exception(
                            f"Expected Slippage is {expected_slip:.2f}%, trade will not be executed."
                        )
                    limit_price = (
                        cur_price + (self.place * self.ticksize[symbol])
                        if side == "Buy"
                        else cur_price - (self.place * self.ticksize[symbol])
                    )
                    limit_price = self.round_up(
                        limit_price, round(-math.log(float(self.ticksize[symbol]), 10))
                    )
                    tosend = f"Trying to execute the following trade:\nSymbol: {symbol}\nSide: {side}\ntype: LIMIT\nquantity: {qty}\nprice: {limit_price}"
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "type": "telegram",
                            "chat_id": self.chat_id,
                            "message": tosend,
                        }
                    )
                    res = self.client.place_order(
                        category="linear",
                        symbol=symbol,
                        side=side,
                        orderType="Limit",
                        qty=str(qty),
                        price=str(limit_price),
                        timeInForce="GTC",
                        positionIdx=positionIdx,
                        reduceOnly=False,
                        closeOnTrigger=False,
                    )
            except Exception as e:
                logger.info(f"Cannot place order, error: {e}")
                if "reduce-only" in str(e):
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "type": "telegram",
                            "chat_id": self.chat_id,
                            "message": f"{positionKey}: The trade will not be executed because position is zero.",
                        }
                    )
                    self.userdb.update_positions(self.chat_id, uid, positionKey, 0, 0)
                return
            orderTime = time.time()
            if res["retMsg"] == "OK":
                logger.info(f"{self.uname} Order placed")
            else:
                logger.info(f"{self.uname} - Error in {side} {symbol}: {res['retMsg']}")
                return
            orderId = res["result"]["orderId"]
            replace_order = False
            # Check result and replace
            while True:
                time.sleep(0.3)
                res = self.client.get_open_orders(
                    category="linear", symbol=symbol, orderId=orderId
                )
                if res["retMsg"] != "OK":
                    print("Error in trade query")
                    return
                res = res["result"]["list"][0]
                if res["orderStatus"] == "Filled":
                    logger.info(f"{self.uname} Order filled")
                    if res["avgPrice"] != "" and res["cumExecQty"] != "":
                        exec_details.append((res["avgPrice"], res["cumExecQty"]))
                    break
                elif res["orderStatus"] in [
                    "Cancelled",
                    "Rejected",
                    "PartiallyFilled",
                    "New",
                ]:
                    if isClose:
                        continue
                    pricediff = abs(self.get_latest_price(symbol) - limit_price)
                    if (
                        pricediff > (self.spread * self.ticksize[symbol])
                        and time.time() - orderTime > self.sleep
                    ):
                        logger.info(f"Price diff: {pricediff}, Replacing order")
                        replace_order = True
                        break
            if replace_order:
                # Cancel old order
                self.client.cancel_order(
                    category="linear", symbol=symbol, orderId=orderId
                )
                # query and add pricediff
                res = self.client.get_open_orders(
                    category="linear", symbol=symbol, orderId=orderId
                )
                res = res["result"]["list"][0]
                if res["avgPrice"] != "" and res["cumExecQty"] != "":
                    exec_details.append((res["avgPrice"], res["cumExecQty"]))
                # Update params and Try again
                qty = float(qty) - float(res["cumExecQty"])
                continue
            else:
                break

        # Update slippage
        total_qty = sum([float(x[1]) for x in exec_details])
        total_paid = sum([float(x[0]) * float(x[1]) for x in exec_details])
        exec_price = total_paid / total_qty
        slippage = (exec_price - ref_price) / ref_price * 100
        self.userdb.insert_command(
            {
                "cmd": "send_message",
                "type": "telegram",
                "chat_id": self.chat_id,
                "message": f"{self.uname}: Order ID {orderId} ({positionKey}) fulfilled successfully. The slippage is {slippage:.2f}%.",
            }
        )
        # Query and update position
        resultqty = total_qty
        resultqty = resultqty if positionKey[-4:].upper() == "LONG" else -resultqty
        if not isClose:
            self.userdb.update_positions(self.chat_id, uid, positionKey, resultqty, 1)
        else:
            self.userdb.update_positions(self.chat_id, uid, positionKey, resultqty, 2)
        return

    def check_uta(self):
        try:
            res = self.client.get_account_info()
            res = res["result"]["unifiedMarginStatus"]
            if res == 3 or res == 4:
                return True
            return False
        except Exception as e:
            logger.error(f"Check UTA {e}")
        return False

    def open_trade(
        self, df, uid, proportion, leverage, tmodes, positions, slippage, todelete=False
    ):
        # logger.info("DEBUGx\n" + df.to_string())
        df = df.values
        i = -1
        for tradeinfo in df:
            i += 1
            isOpen = False
            types = tradeinfo[0].upper()
            balance, collateral, coin = 0, 0, ""
            if not tradeinfo[1] in proportion:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"This trade will not be executed since {tradeinfo[1]} is not a valid symbol.",
                    }
                )
                continue
            try:
                coin = "USDT"
                if self.check_uta():
                    res = self.client.get_wallet_balance(accountType="UNIFIED")[
                        "result"
                    ]["list"][0]
                    balance = res["totalEquity"]
                else:
                    res = self.client.get_wallet_balance(
                        accountType="CONTRACT", coin=coin
                    )["result"]["list"][0]["coin"][0]
                    balance = res["availableToWithdraw"]
            except Exception as e:
                coin = "USDT"
                balance = "0"
                logger.error(f"Cannot retrieve balance. {e}")
            balance = float(balance)
            if types[:4] == "OPEN":
                isOpen = True
                positionSide = types[4:]
                if positionSide == "LONG":
                    side = "Buy"
                else:
                    side = "Sell"
                try:
                    self.client.set_leverage(
                        category="linear",
                        symbol=tradeinfo[1],
                        buyLeverage=str(leverage[tradeinfo[1]]),
                        sellLeverage=str(leverage[tradeinfo[1]]),
                    )
                except Exception as e:
                    logger.error(f"Leverage error {str(e)}")
                    pass
            else:
                positionSide = types[5:]
                if positionSide == "LONG":
                    side = "Sell"
                else:
                    side = "Buy"
            try:
                res = self.client.switch_position_mode(
                    category="linear", coin="USDT", mode=3
                )
                logger.info(f"Check position moode {res}")
            except:
                logger.error(f"error in position mode switch!!!! Check {self.api_key}")
            checkKey = tradeinfo[1] + positionSide
            quant = abs(float(tradeinfo[2])) * proportion[tradeinfo[1]]
            if not isOpen and (
                (checkKey not in positions) or (positions[checkKey] == 0)
            ):
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"Close {checkKey}: This trade will not be executed because your opened positions with this strategy is 0.",
                    }
                )
                continue
            if quant == 0:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"{side} {checkKey}: This trade will not be executed because size = 0. Adjust proportion if you want to follow.",
                    }
                )
                continue
            latest_price = self.globals.get_latest_price(tradeinfo[1])
            if isinstance(tradeinfo[3], str):
                exec_price = float(tradeinfo[3].replace(",", ""))
            else:
                exec_price = float(tradeinfo[3])
            if abs(latest_price - exec_price) / exec_price > slippage and isOpen:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"The execute price of {tradeinfo[1]} is {exec_price}, but the current price is {latest_price}, which is over the preset slippage of {slippage}. The trade will not be executed.",
                    }
                )
                continue
            reqstepsize = self.stepsize[tradeinfo[1]]
            if not isOpen and tradeinfo[4]:
                if abs(positions[checkKey]) > abs(quant):
                    quant = abs(positions[checkKey])
            else:
                quant = max(quant, 5 / latest_price)
            collateral = (latest_price * quant) / leverage[tradeinfo[1]]
            newquant = self.round_up(quant, reqstepsize)
            # if (newquant - quant) / quant > 1:
            #     self.userdb.insert_command(
            #         {
            #             "cmd": "send_message",
            #             "chat_id": self.chat_id,
            #             "message": f"{side} {checkKey}: This trade will not be executed because the quantity is too small. Adjust proportion if you want to follow.",
            #         }
            #     )
            #     continue
            quant = str(newquant)
            if isOpen:
                self.userdb.insert_command(
                    {
                        "cmd": "send_message",
                        "chat_id": self.chat_id,
                        "message": f"For the following trade, you will need {collateral:.3f}{coin} as collateral.",
                    }
                )
                if collateral >= balance * self.safety_ratio:
                    self.userdb.insert_command(
                        {
                            "cmd": "send_message",
                            "chat_id": self.chat_id,
                            "message": f"WARNING: this trade will take up more than {self.safety_ratio} of your available balance. It will NOT be executed. Manage your risks accordingly and reduce proportion if necessary.",
                        }
                    )
                    continue
            ref_price = float(tradeinfo[3])
            try:
                t = threading.Thread(
                    target=self.algolimit,
                    args=(
                        tradeinfo[1],
                        quant,
                        side,
                        self.globals.getIdx(side, isOpen),
                        not isOpen,
                        ref_price,
                        checkKey,
                        uid,
                    ),
                )
                t.start()
            except Exception as e:
                logger.error(f"Error in processing request during trade opening. {e}")
        time.sleep(random.choice([0.1 * i for i in range(1, 10)]))

    def get_positions(self):
        try:
            havenext = True
            npc = None
            allpos = []
            while havenext:
                havenext = False
                try:
                    if npc is None:
                        result2 = self.client.get_positions(
                            category="linear", settleCoin="USDT"
                        )["result"]
                    else:
                        result2 = self.client.get_positions(
                            category="linear", settleCoin="USDT", cursor=npc
                        )["result"]
                    allpos.extend(result2["list"])
                except:
                    logger.error("Other errors")
                    return -1
                if "nextPageCursor" in result2 and result2["nextPageCursor"] != "":
                    npc = result2["nextPageCursor"]
                    havenext = True
        except Exception as e:
            if str(e).find("Invalid") != -1:
                logger.error(str(e))
                return -1
            for line in os.popen("ps ax | grep tg_"):
                fields = line.split()
                pid = fields[0]
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except:
                    pass
            exit(-1)
        symbol = []
        size = []
        EnPrice = []
        MarkPrice = []
        PNL = []
        margin = []
        # if self.time_in_danger():
        #     logger.info("Skipping checking during unstable time.")
        #     continue
        for pos in allpos:
            try:
                pos = pos["data"]
            except:
                logger.error("Error! but no worries.")
                break
            if float(pos["size"]) != 0:
                symbol.append(pos["symbol"])
                tsize = pos["size"]
                tsize = tsize if pos["side"] == "Buy" else -tsize
                size.append(tsize)
                EnPrice.append(pos["entry_price"])
                try:
                    mp = self.get_latest_price(pos["symbol"])
                except:
                    mp = 0
                MarkPrice.append(mp)
                PNL.append(pos["unrealised_pnl"])
                margin.append(pos["leverage"])
        return pd.DataFrame(
            {
                "symbol": symbol,
                "size": size,
                "Entry Price": EnPrice,
                "Mark Price": MarkPrice,
                "PNL": PNL,
                "leverage": margin,
            }
        )

    def round_up(self, n, decimals=0):
        multiplier = 10**decimals
        return math.ceil(n * multiplier) / multiplier
