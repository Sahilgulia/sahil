# SSC Notice Monitor

This repo now includes a ready-to-run Python script to monitor **https://ssc.gov.in/** and alert you whenever a new notice appears.

## File added

- `monitor_ssc_notices.py` — checks notices, stores seen notices locally, sends alerts to Telegram and/or email.

## How it works

1. Downloads the SSC page.
2. Extracts notice links from notice-like sections (with fallback logic).
3. Compares against previously seen notices in a local state file (`.ssc_notice_state.json` by default).
4. Sends notification only for newly found notices.

## 1) First-time setup (baseline)

```bash
python3 monitor_ssc_notices.py --bootstrap
```

This saves existing notices as baseline and sends **no** notification.

## 2) Configure Telegram (optional)

Set env vars:

```bash
export TELEGRAM_BOT_TOKEN="<your_bot_token>"
export TELEGRAM_CHAT_ID="<your_chat_id>"
```

## 3) Configure Email (optional)

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="465"
export SMTP_USER="you@gmail.com"
export SMTP_PASSWORD="<app_password>"
export SMTP_TO="you@gmail.com"
```

> For Gmail, use an app password (not your normal password).

If your provider needs STARTTLS on port `587`, run checks with `--smtp-starttls`.

## 4) Run a check manually

```bash
python3 monitor_ssc_notices.py
```

## 5) Schedule every 15 minutes with cron

```cron
*/15 * * * * cd /workspace/sahil && /usr/bin/python3 monitor_ssc_notices.py >> ssc_monitor.log 2>&1
```

## Useful flags

- `--url` custom URL to monitor
- `--state-file` custom state JSON path
- `--timeout` HTTP timeout (seconds)
- `--bootstrap` set baseline and skip notifications
- `--smtp-starttls` use STARTTLS instead of implicit SSL

## Notes

- If SSC changes its HTML structure, parser fallback may still work, but you should test manually.
- You can configure either Telegram, email, or both.
