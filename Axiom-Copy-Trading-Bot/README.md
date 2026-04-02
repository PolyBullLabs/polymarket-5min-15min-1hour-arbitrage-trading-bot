# Axiom Copy Trader

Part of [copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub).

Axiom Copy Trader is a simple Python bot that enables copy trading of wallets using the Axiom.trade WebSocket. It listens for buy/sell signals and automatically trades Solana memecoins/tokens accordingly.

## Disclaimer

- This project is **not affiliated with Axiom.trade**, and they do not endorse or support it in any way.
- This is **not an official product** of Axiom.trade.
- The bot has **not been extensively tested**; **use at your own risk** and the authors are not responsible for any losses.
- **Do not risk funds you cannot afford to lose.**
- The Raydium **BUY** transaction is disabled by default because it has not been tested yet. See below for enabling it.

## Installation

1. Clone the hub and enter this bot folder:
   ```sh
   git clone https://github.com/sinusflow/copy-trading-bot-hub.git
   cd copy-trading-bot-hub/Axiom-Copy-Trading-Bot
   ```

2. Install required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Set up your environment variables by creating a `.env` file with the following format:
   ```ini
   RPC_URL_PUMP_FUN=https://api.mainnet-beta.solana.com
   RPC_URL_RAYDIUM=https://api.mainnet-beta.solana.com
   WALLET_PUBLIC_KEY=your_public_key_here
   WALLET_PRIVATE_KEY=your_private_key_here
   TRACK_WALLETS=4ugZWiyAYH7auVajf3axVykxTLsc13cx9oHCzETUjc21
   SOL_IN=0.01
   MAX_SOL_SPEND=0.1
   MAX_SLIPPAGE=35
   ALLOW_REBUY=false
   MAX_BUY_ATTEMPTS=1
   DEBUG=false
   ```

### Environment Variables Explanation

- **RPC_URL_PUMP_FUN**: The RPC URL used for transactions on Pump.fun.
- **RPC_URL_RAYDIUM**: The RPC URL used for transactions on Raydium.
- **WALLET_PUBLIC_KEY**: Your Solana wallet public key.
- **WALLET_PRIVATE_KEY**: Your private key in **Base58 format** (can be extracted from Phantom Wallet - [Guide](https://help.phantom.com/hc/en-us/articles/28355165637011-Exporting-Your-Private-Key)).
- **TRACK_WALLETS**: Wallets to track for copy trading. Multiple wallets can be separated using `|` (e.g., `wallet1|wallet2|wallet3`).
- **SOL_IN**: The fixed amount of SOL to use for each buy order.
- **MAX_SOL_SPEND**: The maximum amount of SOL that can be spent while the bot is running. If set to `0`, there is no limit.
- **MAX_SLIPPAGE**: The maximum slippage allowed for transactions before they fail.
- **ALLOW_REBUY**: Defines whether the bot is allowed to rebuy the same token (`true` or `false`).
- **MAX_BUY_ATTEMPTS**: The maximum number of times the bot will retry a failed buy transaction before giving up.
- **DEBUG**: If set to `true`, it enables detailed logs, including packet logs from WebSockets, for debugging purposes.

4. Obtain your authentication token:
   You can obtain the authentication token by opening the Axiom.trade website in Google Chrome, going to the **Network** tab in Developer Tools (F12 or Ctrl+Shift+I), and finding the first request that returns the token.

5. Add your authentication token to `cookie.txt`:
   ```
   auth-refresh-token=your_refresh_token_here; auth-access-token=your_access_token_here;
   ```

## Enabling Raydium Buy Transactions (Experimental)

By default, buy transactions for tokens on Raydium are **disabled** because they have **not been tested deeply**. If you want to enable it, uncomment the following line in the code at **line 433**:

```python
# 'buy': lambda: sell_token('ra', token_name, token_address, max_slippage),
```

## Usage

Run the bot with:
```sh
python main.py
```

## Credits

This project was made possible thanks to **AL-THE-BOT-FATHER**’s **pump_fun_py** and **raydium_py** libraries for Pump.fun and Raydium contract interaction.
