"""SMTP delivery for notification emails.

The password is decrypted only inside the caller; it is never logged. Sending
runs in a worker thread because :mod:`smtplib` is blocking.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MIMEMessage
from email.utils import formataddr


class EmailError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    from_address: str
    to_address: str | None = None
    from_name: str | None = None
    username: str | None = None
    password: str | None = None
    use_tls: bool = True
    use_ssl: bool = False


@dataclass(frozen=True)
class OutboundEmail:
    to: str
    subject: str
    text: str
    html: str | None = None


def _send_sync(config: EmailConfig, message: OutboundEmail) -> None:
    mime = MIMEMessage()
    mime["Subject"] = message.subject
    mime["From"] = formataddr((config.from_name or "Thesium", config.from_address))
    mime["To"] = message.to
    mime.set_content(message.text)
    if message.html:
        mime.add_alternative(message.html, subtype="html")

    context = ssl.create_default_context()
    smtp: smtplib.SMTP
    try:
        if config.use_ssl:
            smtp = smtplib.SMTP_SSL(
                config.host,
                config.port,
                local_hostname="localhost",
                timeout=20,
                context=context,
            )
        else:
            smtp = smtplib.SMTP(
                config.host, config.port, local_hostname="localhost", timeout=20
            )
        with smtp:
            smtp.ehlo()
            if config.use_tls and not config.use_ssl:
                smtp.starttls(context=context)
                smtp.ehlo()
            if config.username:
                smtp.login(config.username, config.password or "")
            smtp.send_message(mime)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailError("EMAIL_AUTH", "SMTP authentication failed") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise EmailError("EMAIL_RECIPIENT", "SMTP rejected the recipient") from exc
    except smtplib.SMTPSenderRefused as exc:
        raise EmailError("EMAIL_SENDER", "SMTP rejected the sender address") from exc
    except smtplib.SMTPException as exc:
        raise EmailError("EMAIL_SMTP", f"SMTP error: {exc}") from exc
    except (OSError, TimeoutError) as exc:
        raise EmailError("EMAIL_CONNECT", f"cannot connect to SMTP server: {exc}") from exc


async def send_email(config: EmailConfig, message: OutboundEmail) -> None:
    if not config.host or not config.from_address:
        raise EmailError("EMAIL_NOT_CONFIGURED", "SMTP host and from address are required")
    await asyncio.to_thread(_send_sync, config, message)