"""SSRF guard for server-initiated outbound HTTP (alert webhooks, etc.).

Validates that a user-supplied URL points at a public host before the server connects, so an
attacker cannot aim outbound requests at loopback, private, link-local (cloud metadata) or
reserved addresses. Also provides an opener that does not follow redirects (a redirect could
otherwise bounce a validated public URL to an internal one).
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlparse


def _ip_is_internal(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # not a parseable IP -> treat as unsafe
    # Unwrap IPv4-mapped/6to4 IPv6 so an internal IPv4 can't hide inside an IPv6 literal.
    v6 = getattr(addr, "version", 4) == 6
    if v6:
        mapped = getattr(addr, "ipv4_mapped", None) or getattr(addr, "sixtofour", None)
        if mapped is not None:
            addr = mapped
        elif addr in ipaddress.ip_network("2002::/16"):  # 6to4 wrapper
            return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_public_http_url(url: str, *, allow_internal: bool = False) -> None:
    """Raise ValueError unless ``url`` is an http(s) URL whose every resolved IP is public."""
    p = urlparse((url or "").strip())
    if p.scheme not in ("http", "https"):
        raise ValueError("A URL deve usar http:// ou https://.")
    host = p.hostname
    if not host:
        raise ValueError("URL sem host válido.")
    if allow_internal:
        return
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError("Host da URL não pôde ser resolvido.") from exc
    ips = {info[4][0] for info in infos}
    if not ips:
        raise ValueError("Host da URL sem endereço.")
    for ip in ips:
        if _ip_is_internal(ip):
            raise ValueError("Destino interno/privado não é permitido (proteção SSRF).")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port, pinned_ip, timeout):  # noqa: ANN001
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self):  # connect to the validated IP, not a fresh DNS lookup
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, pinned_ip, timeout, context):  # noqa: ANN001
        super().__init__(host, port, timeout=timeout, context=context)
        self._pinned_ip = pinned_ip

    def connect(self):  # connect to the pinned IP but keep TLS SNI/cert check on the real host
        sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def safe_post(url: str, data: bytes, headers: dict, timeout: int = 10, *, allow_internal: bool = False) -> int:
    """POST to a user-supplied URL with the connection PINNED to a validated public IP.

    Resolves the host once, verifies every resolved IP is public, then opens the socket to that
    exact IP (preserving Host header + TLS SNI on the original hostname). This closes the
    DNS-rebinding / TOCTOU gap where a second DNS lookup at connect time could point at an
    internal address. Redirects are not followed. Returns the HTTP status code.
    """
    p = urlparse((url or "").strip())
    if p.scheme not in ("http", "https"):
        raise ValueError("A URL deve usar http:// ou https://.")
    host = p.hostname
    if not host:
        raise ValueError("URL sem host válido.")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError("Host da URL não pôde ser resolvido.") from exc
    ips = [info[4][0] for info in infos]
    if not ips:
        raise ValueError("Host da URL sem endereço.")
    if not allow_internal:
        for ip in ips:
            if _ip_is_internal(ip):
                raise ValueError("Destino interno/privado não é permitido (proteção SSRF).")
    pinned = ips[0]
    path = p.path or "/"
    if p.query:
        path += "?" + p.query

    if p.scheme == "https":
        conn = _PinnedHTTPSConnection(host, port, pinned, timeout, ssl.create_default_context())
    else:
        conn = _PinnedHTTPConnection(host, port, pinned, timeout)
    try:
        conn.request("POST", path, body=data, headers=headers)
        resp = conn.getresponse()
        status = resp.status
        resp.read()  # drain
        return status
    finally:
        conn.close()
