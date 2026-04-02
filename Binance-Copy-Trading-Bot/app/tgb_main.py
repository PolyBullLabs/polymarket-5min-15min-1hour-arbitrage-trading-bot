import threading
from app.telegram_frontend.tgb_db import dbOperations
from app.telegram_frontend.tgb_handlers import tgHandlers
from app.telegram_frontend.tgb_globals import tgGlobals
from app.data.credentials import bot_token, auth_code, admin_code
from telegram.ext import Updater
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    tostop = threading.Event()
    updater = Updater(bot_token)
    globals = tgGlobals(updater)
    database = dbOperations(globals, updater)
    handlers = tgHandlers(updater, database, auth_code, admin_code, globals)
    handlers.init_handlers()
    t1 = threading.Thread(target=globals.retrieve_command, args=(database, tostop))
    t1.start()
    try:
        updater.start_polling()
        updater.idle()
        tostop.set()
    except:
        exit(-1)


if __name__ == "__main__":
    main()
