# LBank Futures 1H Doji Scanner

This project scans LBank USDT-margined perpetual Futures, selects the 20 contracts with the largest negative 24-hour move, checks their most recently completed 1-hour candle, and sends a Telegram message when the candle qualifies as a Doji.

Doji rule:
body <= 10% of candle range

The bot never places trades and does not require an LBank trading API key.

## GitHub setup

1. Upload these files to your GitHub repository.
2. Go to Settings -> Secrets and variables -> Actions.
3. Add a repository secret:
   - Name: TELEGRAM_BOT_TOKEN
   - Value: your NEW Telegram bot token
4. The Telegram chat ID is already set in the workflow.
5. Go to Actions -> LBank Futures Doji Scanner -> Run workflow to test it manually.

The scheduled GitHub Action runs at 3 minutes past each hour. GitHub Actions schedules are not guaranteed to run at exactly the scheduled second, so the alert may be delayed.

## Important

The LBank Futures API documents public contract market data and the Futures WebSocket endpoint. The exact WebSocket kbar request format is not described in the current Futures documentation as clearly as the older LBank market-data WebSocket documentation. The scanner therefore includes strict error handling; if LBank changes/rejects the kbar request, the Action log will show the response instead of silently sending incorrect alerts.
