# Binance copy trade bot

Part of [copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub).

## Running the bot on your own

This program uses web scraping to monitor the positions opened by traders sharing their positions on Binance Futures Leaderboard. We then mimic the trade in your account using the Bybit api. MongoDB is the database used in this software. **Bot updated and working (Feb 2024)**

### Environment setup (Recommended)

#### Using Conda

At your target directory, execute the following:

```bash
conda create -n trading python=3.9 -y
conda activate trading
git clone https://github.com/sinusflow/copy-trading-bot-hub.git
cd copy-trading-bot-hub/Binance-Copy-Trading-Bot
pip install -r requirements.txt
```

### Database Setup

Follow the instructions in https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/ to set up MongoDB on the same host where the program is run.  
Follow https://www.digitalocean.com/community/tutorials/how-to-secure-mongodb-on-ubuntu-20-04 to set up username and password.  

### Software setup 

1. Setup a telegram bot using `Botfather` (details on telegram official site) and mark the access token.
2. Setup a discord channel for urgent/alert messages, and get a webhook url. (Reason is to avoid mixing them into the telegram channel and missing out on them.)
3. Fill in the required fields in  `app/data/credentials.py`
4. Run `python -m  app.ct_main` and `python -m app.tgb_main`. It is suggested to set both up as a systemctl service, with restart=always and a MaxRunTime so that the program is automatically restarted from time to time.
5. Call `/addcookie` to add credentials required for api end-points every 2-3 days. I will not teach you how to do so here, but you can find the information on the internet.

### Using the software

After the python programs are up and running, go to your telegram bot and type /start, then follow the instructions.  
It should be rather straightforward; if you encounter issues, open an issue on the [repository](https://github.com/sinusflow/copy-trading-bot-hub).  
Refer to the file telegram-commands.txt for a list of commands you can use.  
I personally suggest you go to the binance leaderboard, pick a longer timespan (e.g. monthly or all-time) and choose the top traders sharing their positions.  

### Disclaimer

- Users are solely responsible for their own trading decisions and account management. This software is not financial advice. Conduct your own due diligence and consider independent professional advice where appropriate.
- The authors accept no liability for loss or damage from reliance on this bot. Trading financial markets involves risk; uptime and data accuracy are not guaranteed.
- By using this software you accept that you use it at your own risk and are responsible for any profits or losses.
- Trading can cause losses exceeding your initial stake. Do not trade with capital you cannot afford to lose.
