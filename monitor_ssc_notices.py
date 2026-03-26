#!/usr/bin/env python3
"""Monitor SSC website notice board and send alerts on new notices.

Supports Telegram and email notifications.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import ssl
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib import parse, request

SSC_HOME = "https://ssc.gov.in/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) SSC-Notice-Monitor/1.0"


@dataclass(frozen=True)
class Notice:
    title: str
    url: str

    @property
    def key(self) -> str:
        return f"{self.title.strip()}||{self.url.strip()}"


class NoticeParser(HTMLParser):
    """Extract links from HTML, prioritizing sections likely to be notice boards."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._tag_stack: list[dict[str, str]] = []
        self._active_anchor: dict[str, str] | None = None
        self._inside_notice_depth = 0
        self.notice_links: list[Notice] = []
        self.other_links: list[Notice] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        self._tag_stack.append(attrs_dict)

        if self._is_notice_container(attrs_dict):
            self._inside_notice_depth += 1

        if tag.lower() == "a":
            href = attrs_dict.get("href", "").strip()
            if href:
                self._active_anchor = {"href": href, "text": ""}

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._active_anchor:
            href = self._active_anchor["href"]
            text = _normalize_text(self._active_anchor["text"])
            if text:
                url = parse.urljoin(self.base_url, href)
                notice = Notice(title=text, url=url)
                if self._inside_notice_depth > 0:
                    self.notice_links.append(notice)
                else:
                    self.other_links.append(notice)
            self._active_anchor = None

        if self._tag_stack:
            attrs_dict = self._tag_stack.pop()
            if self._is_notice_container(attrs_dict) and self._inside_notice_depth > 0:
                self._inside_notice_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._active_anchor is not None:
            self._active_anchor["text"] += data

    @staticmethod
    def _is_notice_container(attrs: dict[str, str]) -> bool:
        text = " ".join([attrs.get("id", ""), attrs.get("class", ""), attrs.get("aria-label", "")]).lower()
        return any(word in text for word in ("notice", "latest-news", "news", "announcement"))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def fetch_html(url: str, timeout: int) -> str:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    with request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_notices(html: str, base_url: str) -> list[Notice]:
    parser = NoticeParser(base_url)
    parser.feed(html)

    candidates = parser.notice_links if parser.notice_links else parser.other_links

    filtered: list[Notice] = []
    for item in candidates:
        hay = f"{item.title} {item.url}".lower()
        if any(token in hay for token in ("notice", "pdf", "uploads", "cgl", "exam", "constable", "stenographer")):
            filtered.append(item)

    final = filtered if filtered else candidates
    dedup: dict[str, Notice] = {}
    for notice in final:
        dedup[notice.key] = notice
    return list(dedup.values())


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("seen_keys", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(path: Path, keys: Iterable[str]) -> None:
    payload = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seen_keys": sorted(set(keys)),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def send_telegram(bot_token: str, chat_id: str, message: str) -> None:
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = parse.urlencode({"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}).encode()
    req = request.Request(endpoint, data=body, method="POST")
    with request.urlopen(req, timeout=20) as response:
        _ = response.read()


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
    subject: str,
    body: str,
    use_starttls: bool,
) -> None:
    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if use_starttls:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30, context=ssl.create_default_context()) as smtp:
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)


def env_or_value(value: str | None, env_key: str, default: str | None = None) -> str | None:
    if value:
        return value
    return os.getenv(env_key, default)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor SSC notice board for new notices.")
    parser.add_argument("--url", default=SSC_HOME, help="SSC page URL to monitor")
    parser.add_argument("--state-file", default=".ssc_notice_state.json", help="Local JSON file to persist seen notices")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout in seconds")
    parser.add_argument("--bootstrap", action="store_true", help="Store current notices as baseline and skip notifications")

    parser.add_argument("--telegram-bot-token", default=None)
    parser.add_argument("--telegram-chat-id", default=None)

    parser.add_argument("--smtp-host", default=None)
    parser.add_argument("--smtp-port", type=int, default=None)
    parser.add_argument("--smtp-user", default=None)
    parser.add_argument("--smtp-password", default=None)
    parser.add_argument("--smtp-to", default=None)
    parser.add_argument("--smtp-starttls", action="store_true", help="Use SMTP + STARTTLS instead of SMTPS")

    args = parser.parse_args()

    tg_token = env_or_value(args.telegram_bot_token, "TELEGRAM_BOT_TOKEN")
    tg_chat_id = env_or_value(args.telegram_chat_id, "TELEGRAM_CHAT_ID")

    smtp_host = env_or_value(args.smtp_host, "SMTP_HOST")
    smtp_port = int(env_or_value(str(args.smtp_port) if args.smtp_port else None, "SMTP_PORT", "465"))
    smtp_user = env_or_value(args.smtp_user, "SMTP_USER")
    smtp_password = env_or_value(args.smtp_password, "SMTP_PASSWORD")
    smtp_to = env_or_value(args.smtp_to, "SMTP_TO")

    state_path = Path(args.state_file)

    try:
        html = fetch_html(args.url, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to fetch page: {exc}", file=sys.stderr)
        return 1

    notices = extract_notices(html, base_url=args.url)
    if not notices:
        print("[WARN] No notices extracted. HTML structure may have changed.")

    current_keys = {n.key for n in notices}
    previous_keys = load_state(state_path)

    if args.bootstrap or not previous_keys:
        save_state(state_path, current_keys)
        print(f"[INFO] Baseline saved with {len(current_keys)} notices. No alerts sent.")
        return 0

    new_notices = [n for n in notices if n.key not in previous_keys]

    if not new_notices:
        print("[INFO] No new notices found.")
        save_state(state_path, current_keys)
        return 0

    lines = [
        f"New SSC notice(s): {len(new_notices)}",
        f"Checked at (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for idx, notice in enumerate(new_notices, start=1):
        lines.append(f"{idx}. {notice.title}")
        lines.append(f"   {notice.url}")
    message = "\n".join(lines)

    failures: list[str] = []

    if tg_token and tg_chat_id:
        try:
            send_telegram(tg_token, tg_chat_id, message)
            print("[INFO] Telegram alert sent.")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Telegram failed: {exc}")
    else:
        print("[INFO] Telegram not configured.")

    if all((smtp_host, smtp_user, smtp_password, smtp_to)):
        try:
            send_email(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                to_email=smtp_to,
                subject=f"SSC Notice Alert ({len(new_notices)} new)",
                body=message,
                use_starttls=args.smtp_starttls,
            )
            print("[INFO] Email alert sent.")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Email failed: {exc}")
    else:
        print("[INFO] Email not fully configured.")

    save_state(state_path, current_keys)

    if failures:
        for item in failures:
            print(f"[ERROR] {item}", file=sys.stderr)
        return 2

    print("[INFO] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
