"""SSRF guard for server-initiated outbound HTTP (alert webhooks, etc.).

Validates that a user-supplied URL points at a public host before the server connects, so an
attacker cannot aim outbound requests at loopback, private, link-local (cloud metadata) or
reserved addresses. Also provides an opener that does not follow redirects (a redirect could
otherwise bounce a validated public URL to an internal one).
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.request
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401, ANN001
        return None  # never follow redirects


def no_redirect_opener() -> urllib.request.OpenerDirector:
    """An opener that refuses to follow HTTP redirects."""
    return urllib.request.build_opener(_NoRedirect())
