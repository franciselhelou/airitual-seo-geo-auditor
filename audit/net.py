"""Bounded public HTTP requests with redirect, port and DNS safety checks."""
import ipaddress
import socket
from urllib.parse import urlparse, urljoin, urldefrag
import requests

AGENT = "AIRitualSiteAudit/1.0 (+https://airitual.com; respectful public web audit)"
MAX_BYTES = 1_250_000
ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "application/xml", "text/xml")


class UnsafeURL(ValueError):
    pass


def checked_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise UnsafeURL("Only HTTP(S) URLs are accepted")
    if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
        raise UnsafeURL("Credentials and nonstandard ports are not allowed")
    host = parsed.hostname.strip(".").lower()
    if host in ("localhost",) or host.endswith((".local", ".localhost", ".internal", ".test")):
        raise UnsafeURL("Local/internal hostname is not allowed")
    if "." not in host:
        raise UnsafeURL("A public domain is required")
    try:
        ipaddress.ip_address(host)
        raise UnsafeURL("IP literals are not allowed")
    except ValueError as ex:
        if isinstance(ex, UnsafeURL):
            raise
    try:
        resolutions = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL(f"Hostname DNS lookup failed: {exc}") from exc
    if not resolutions:
        raise UnsafeURL("Hostname has no DNS records")
    for entry in resolutions:
        ip = ipaddress.ip_address(entry[4][0])
        if not ip.is_global:
            raise UnsafeURL("Hostname resolves to a private, reserved, or restricted address")
    return urldefrag(raw)[0]


def fetch(url: str, *, max_bytes=MAX_BYTES, timeout=(6, 11), max_redirects=4, allow_url=None):
    """Do not automatically follow redirects. Revalidate all URLs and DNS targets.

    Protects against basic SSRF. Public deployment still benefits from an egress firewall
    because a DNS rebinding attack is possible between validation and socket connection.
    """
    session = requests.Session()
    session.trust_env = False  # avoid untrusted proxy configuration on runners
    headers = {"User-Agent": AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.8,*/*;q=0.5"}
    current = url
    for _ in range(max_redirects + 1):
        checked_url(current)
        if allow_url is not None and not allow_url(current):
            return {"url": current, "status": 0, "text": "", "type": "", "error": "Blocked by robots policy"}
        with session.get(current, headers=headers, timeout=timeout, allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    return {"url": current, "status": response.status_code, "text": "", "type": "", "error": "Redirect without location"}
                current = urljoin(current, location)
                continue
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type not in ALLOWED_TYPES:
                return {"url": current, "status": response.status_code, "text": "", "type": content_type, "error": "Non-HTML/XML content"}
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=32768):
                size += len(chunk)
                if size > max_bytes:
                    return {"url": current, "status": response.status_code, "text": "", "type": content_type, "error": "Response exceeded byte limit"}
                chunks.append(chunk)
            # Decode bytes already buffered, without rereading a streamed response.
            data = b"".join(chunks)
            charset = response.encoding
            if not charset or charset.lower() == "iso-8859-1":
                charset = "utf-8"
            try:
                decoded = data.decode(charset, errors="replace")
            except LookupError:
                decoded = data.decode("utf-8", errors="replace")
            return {"url": current, "status": response.status_code, "text": decoded, "type": content_type, "error": ""}
    return {"url": current, "status": 0, "text": "", "type": "", "error": "Too many redirects"}
