# Keep-Alive Setup for Render Free Tier

## Problem
Render's free tier puts services to sleep after 15 minutes of inactivity, which would stop your trading bot.

## Solution: UptimeRobot

UptimeRobot is a free service that will ping your bot every 5 minutes to keep it awake 24/7.

### Setup Steps

1. **Create UptimeRobot Account**
   - Go to [uptimerobot.com](https://uptimerobot.com)
   - Sign up for a free account

2. **Add New Monitor**
   - Click "Add New Monitor"
   - Fill in the details:
     - **Monitor Type:** HTTP(s)
     - **Friendly Name:** Scalper Bot
     - **URL:** `https://scalper-pewp.onrender.com/health`
     - **Monitoring Interval:** 5 minutes
   - Click "Create Monitor"

3. **Verify Setup**
   - Wait 5-10 minutes
   - Check UptimeRobot dashboard - should show "Up"
   - Check Render logs - should see regular health check requests

### Alternative: Cron-Job.org

If you prefer, you can also use [cron-job.org](https://cron-job.org):
- Create free account
- Add new cron job
- URL: `https://scalper-pewp.onrender.com/health`
- Schedule: Every 5 minutes
- Enable the job

## Verification

Your bot should now stay active 24/7. You can verify by:
- Checking Render logs for continuous activity
- Monitoring UptimeRobot dashboard
- Visiting your bot URL - should always respond quickly

## Cost

Both UptimeRobot and Cron-Job.org offer free tiers that are sufficient for keeping one service alive.
