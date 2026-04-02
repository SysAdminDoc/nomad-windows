"""Logging utilities for NOMAD Field Desk — log scrubbing filter."""

import logging
import re


class SensitiveDataFilter(logging.Filter):
    """Scrub sensitive data (emails, IPs, tokens, passwords) from log messages."""

    _patterns = [
        # Passwords in URLs / query strings
        (re.compile(r'(password|passwd|pwd)=([^\s&]+)', re.IGNORECASE), r'\1=***'),
        # Email addresses
        (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), '***@***.***'),
        # IP addresses (preserve localhost / loopback)
        (re.compile(
            r'(?<!\d)'
            r'(?!127\.0\.0\.1|0\.0\.0\.0)'
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?!\d)'),
         '***.***.***.***'),
        # Long hex or base64 strings (likely API keys / tokens, >20 chars)
        (re.compile(r'(?<=[=\s:"\'])[A-Za-z0-9+/=_-]{21,}(?=[\s&"\',;]|$)'), '[REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        # Only format+scrub once per record to avoid double-formatting
        if not getattr(record, '_scrubbed', False):
            msg = record.getMessage()
            for pattern, replacement in self._patterns:
                msg = pattern.sub(replacement, msg)
            record.msg = msg
            record.args = None  # args already merged into msg
            record._scrubbed = True
        return True


def install_scrubbing_filter():
    """Attach SensitiveDataFilter to all current root-logger handlers."""
    scrub = SensitiveDataFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(scrub)
    return scrub
