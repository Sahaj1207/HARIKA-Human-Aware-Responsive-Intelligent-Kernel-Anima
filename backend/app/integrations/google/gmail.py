"""Gmail: list and read messages, find a person's address from past mail, and send.

Message content is untrusted text from other people. It is returned as data for
HARIKA to show or summarize; nothing in it is ever acted on.
"""
import base64
import re
import urllib.parse
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

from app.integrations.google.account import GoogleAccount, google_account

_API = "https://gmail.googleapis.com/gmail/v1/users/me"
_BODY_CHARS = 4000


@dataclass
class Mail:
    id: str
    thread_id: str
    sender: str            # "Priya Sharma <priya@example.com>"
    subject: str
    snippet: str = ""
    date: str = ""
    to: str = ""
    message_id: str = ""   # RFC 822 Message-ID, for threading replies
    references: str = ""
    body: str = ""
    labels: List[str] = field(default_factory=list)

    @property
    def sender_name(self) -> str:
        name, address = parseaddr(self.sender)
        return name or address

    @property
    def sender_address(self) -> str:
        return parseaddr(self.sender)[1]

    @property
    def link(self) -> str:
        return f"https://mail.google.com/mail/u/0/#all/{self.thread_id}"


def _headers(payload: Dict[str, Any]) -> Dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def body_text(payload: Dict[str, Any]) -> str:
    """The readable text of a message: its plain-text part, or its HTML part as text."""
    plain, html = [], []

    def walk(part: Dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html.append(_decode(data))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    if plain:
        text = "\n".join(plain)
    elif html:
        from app.tools.web.sources import plain as strip_html
        text = strip_html(re.sub(r"<(script|style)\b.*?</\1>", " ", "\n".join(html), flags=re.S | re.I))
    else:
        text = ""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:_BODY_CHARS]


def to_mail(item: Dict[str, Any], with_body: bool = False) -> Mail:
    payload = item.get("payload", {})
    headers = _headers(payload)
    try:
        when = parsedate_to_datetime(headers.get("date", "")).astimezone().isoformat(timespec="minutes")
    except (TypeError, ValueError):
        when = ""
    return Mail(
        id=item["id"], thread_id=item.get("threadId", item["id"]),
        sender=headers.get("from", ""), subject=headers.get("subject", "") or "(no subject)",
        snippet=item.get("snippet", ""), date=when, to=headers.get("to", ""),
        message_id=headers.get("message-id", ""), references=headers.get("references", ""),
        body=body_text(payload) if with_body else "", labels=item.get("labelIds", []),
    )


class Gmail:
    def __init__(self, account: GoogleAccount = google_account):
        self.account = account

    async def search(self, query: str, limit: int = 5) -> List[Mail]:
        self.account.require("email_read")
        params = urllib.parse.urlencode({"q": query, "maxResults": str(limit)})
        listing = await self.account.request("GET", f"{_API}/messages?{params}")
        ids = [m["id"] for m in (listing or {}).get("messages", [])]
        metadata = "format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date&metadataHeaders=To"
        items = await self.account.gather("GET", [f"{_API}/messages/{i}?{metadata}" for i in ids])
        return [to_mail(item) for item in items if item]

    async def unread(self, limit: int = 5) -> List[Mail]:
        return await self.search("is:unread in:inbox category:primary", limit)

    async def read(self, message_id: str) -> Mail:
        self.account.require("email_read")
        return to_mail(await self.account.request("GET", f"{_API}/messages/{message_id}?format=full"), with_body=True)

    async def find_addresses(self, name: str) -> List[Tuple[str, str]]:
        """(display name, address) of people matching `name` in recent mail, most frequent first."""
        self.account.require("email_read")
        words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 1]
        if not words:
            return []
        params = urllib.parse.urlencode({"q": f"from:({name}) OR to:({name})", "maxResults": "25"})
        listing = await self.account.request("GET", f"{_API}/messages?{params}")
        ids = [m["id"] for m in (listing or {}).get("messages", [])]
        metadata = "format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Cc"
        items = await self.account.gather("GET", [f"{_API}/messages/{i}?{metadata}" for i in ids])
        mine = (self.account.status().get("email") or "").lower()
        counts: Dict[str, Tuple[str, int]] = {}
        for item in items:
            headers = _headers(item.get("payload", {}))
            for display, address in getaddresses([headers.get(k, "") for k in ("from", "to", "cc")]):
                address = address.lower()
                haystack = f"{display} {address.split('@')[0]}".lower()
                if not address or address == mine or not all(w in haystack for w in words):
                    continue
                best_name, count = counts.get(address, (display, 0))
                counts[address] = (best_name or display, count + 1)
        ranked = sorted(counts.items(), key=lambda kv: -kv[1][1])
        return [(display or address, address) for address, (display, _) in ranked]

    async def send(self, to: str, subject: str, body: str, reply_to: Optional[Mail] = None) -> Dict[str, Any]:
        self.account.require("email_send")
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        payload: Dict[str, Any] = {}
        if reply_to is not None:
            if reply_to.message_id:
                message["In-Reply-To"] = reply_to.message_id
                message["References"] = f"{reply_to.references} {reply_to.message_id}".strip()
            payload["threadId"] = reply_to.thread_id
        message.set_content(body)
        payload["raw"] = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return await self.account.request("POST", f"{_API}/messages/send", json=payload)

    async def is_sent(self, message_id: str) -> bool:
        item = await self.account.request("GET", f"{_API}/messages/{message_id}?format=minimal")
        return "SENT" in (item or {}).get("labelIds", [])


gmail = Gmail()
