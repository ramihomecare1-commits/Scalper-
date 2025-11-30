# Telegram Bot Setup Guide

## Step 1: Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat and send `/newbot`
3. Follow the prompts:
   - Choose a name for your bot (e.g., "My Trading Bot")
   - Choose a username (must end in 'bot', e.g., "my_scalper_bot")
4. **Save the bot token** - you'll need this later

Example token: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

## Step 2: Get Your Chat ID

1. Start a chat with your new bot (click the link BotFather provides)
2. Send any message to your bot (e.g., "Hello")
3. Open this URL in your browser (replace `<YOUR_BOT_TOKEN>` with your actual token):
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Look for `"chat":{"id":` in the response
5. **Save your chat ID** (it's a number, e.g., `123456789`)

Example response:
```json
{
  "ok": true,
  "result": [{
    "message": {
      "chat": {
        "id": 123456789,  <-- This is your chat ID
        "first_name": "Your Name"
      }
    }
  }]
}
```

## Step 3: Add to Render Environment Variables

1. Go to your Render dashboard
2. Select your scalper bot service
3. Go to "Environment" tab
4. Add these two variables:
   - **Key:** `TELEGRAM_BOT_TOKEN`
     **Value:** Your bot token from Step 1
   - **Key:** `TELEGRAM_CHAT_ID`
     **Value:** Your chat ID from Step 2
5. Click "Save Changes"

## Step 4: Test

After the bot redeploys:
1. Wait for a trade signal (or trigger one manually)
2. You should receive a Telegram message with trade details!

## Notification Examples

**When a trade opens:**
```
🚀 TRADE OPENED

Pair: BTC-USDT
Side: LONG 📈
Entry: $95,234.50
Stop Loss: $94,500.00
Take Profit: $96,500.00
Size: 0.05 BTC
Risk/Reward: 1.5:1
Confidence: 82%

Reasoning: Strong bullish momentum across 5m and 15m timeframes
```

**When a trade closes:**
```
✅ TRADE CLOSED - PROFIT

Pair: BTC-USDT
Side: LONG
Entry: $95,234.50
Exit: $96,100.00
P&L: +$43.25 (+0.91%)
Duration: 23 minutes

Total Trades: 15
Win Rate: 73.3%
```

## Troubleshooting

**Not receiving messages?**
- Verify bot token and chat ID are correct
- Make sure you've sent at least one message to your bot
- Check Render logs for Telegram errors
- Try sending a test message via the Telegram API

**Messages not formatted correctly?**
- Ensure you're using the latest version of the code
- Check that HTML parse mode is supported by your bot

## Privacy & Security

- Your bot token is like a password - keep it secret
- Only share your chat ID with trusted services
- You can revoke and regenerate your bot token anytime via @BotFather
