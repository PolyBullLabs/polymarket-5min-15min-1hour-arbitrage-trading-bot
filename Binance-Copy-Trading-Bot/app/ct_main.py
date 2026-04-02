from app.copy_trade_backend.ct_db import ctDatabase
from app.copy_trade_backend.ct_globals import ctGlobal
from app.copy_trade_backend.ct_position import WebScraping
import logging
import threading

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    globals = ctGlobal()
    database = ctDatabase(globals)
    current_stream = WebScraping(globals, database)
    current_stream.start()
    t1 = threading.Thread(target=globals.reload_symbols, args=(database,))
    t1.start()
    t2 = threading.Thread(target=globals.check_noti, args=(database,))
    t2.start()
    t3 = threading.Thread(target=globals.cookie_check, args=(database,))
    t3.start()
    logger.info("The copy trade program has started running.")


if __name__ == "__main__":
    main()
