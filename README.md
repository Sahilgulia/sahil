# SSC Notice Monitor (Free Setup)

This project monitors **https://ssc.gov.in/** notice updates and sends alerts on Telegram and/or email.

The monitor script is:
- `monitor_ssc_notices.py`

## How it works

1. Downloads SSC page.
2. Extracts notice links.
3. Compares with previous state (`state file`).
4. Sends alert only for new notices.

---

## 100% Free Option (Recommended): GitHub Actions

You said you do not want to spend any money. Use GitHub Actions scheduled workflow (already added in this repo):
- `.github/workflows/ssc-monitor.yml`

This runs every 30 minutes for free (within GitHub free limits), so your laptop can stay off.

### Step-by-step (non-coder friendly)

1. Create a free GitHub account.
2. Create a new repository (public is usually easiest for free usage).
3. Upload these files:
   - `monitor_ssc_notices.py`
   - `.github/workflows/ssc-monitor.yml`
   - `README.md`
4. In GitHub repo, open **Settings → Secrets and variables → Actions → New repository secret**.
5. Add Telegram secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
6. (Optional) Add email secrets:
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TO`
7. Go to **Actions** tab, select **SSC Notice Monitor**, click **Run workflow** once.
8. First run auto-bootstraps state and won’t send old notices.
9. After that, it checks every 30 minutes and alerts on new notices.

### Telegram quick setup

1. Open Telegram and message `@BotFather`.
2. Run `/newbot` and copy bot token.
3. Send one message to your bot.
4. Open:
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Copy `chat.id` value.

---

## Local run (optional)

If you still want to test from your computer once:

```bash
python3 monitor_ssc_notices.py --bootstrap
python3 monitor_ssc_notices.py
```

---

## Environment variables used

- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TO`

---

## Notes

- If SSC site layout changes, parser may need updates.
- You can use Telegram only (completely free).
