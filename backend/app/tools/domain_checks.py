"""Bounded, provenance-aware domain, website and TLS checks.

RDAP discovery follows the IANA bootstrap registry (RFC 9224). Website requests
are restricted to public DNS/IP destinations and redirects are validated one by
one to reduce server-side request forgery (SSRF) risk.
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx


IANA_RDAP_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost", ".local")
BOOTSTRAP_TTL_SECONDS = 24 * 60 * 60
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}

_bootstrap_lock = threading.Lock()
_bootstrap_cache: dict[str, Any] | None = None
_bootstrap_cached_at = 0.0


class DomainCheckError(Exception):
    """Expected failure while performing an external verification check."""


class UnsafeTargetError(DomainCheckError):
    """A URL resolves to a local/private/non-public network destination."""


def normalize_domain(value: str | None) -> str | None:
    """Normalize a hostname or URL to an IDNA ASCII hostname."""
    if not value or not value.strip():
        return None
    raw = value.strip()
    if "@" in raw and "://" not in raw:
        return None
    candidate = raw if "://" in raw else f"https://{raw}"
    try:
        parsed = urlsplit(candidate)
        host = parsed.hostname
        if not host or parsed.username or parsed.password:
            return None
        if parsed.port not in (None, 80, 443):
            return None
        host = host.rstrip(".").lower()
        if not host:
            return None
        try:
            ipaddress.ip_address(host)
            return host
        except ValueError:
            pass
        ascii_host = host.encode("idna").decode("ascii")
        if len(ascii_host) > 253 or "." not in ascii_host:
            return None
        labels = ascii_host.split(".")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not all(ch.isalnum() or ch == "-" for ch in label)
            for label in labels
        ):
            return None
        return ascii_host
    except (ValueError, UnicodeError):
        return None


def is_reserved_domain(domain: str) -> bool:
    value = domain.lower().rstrip(".")
    return any(value == suffix[1:] or value.endswith(suffix) for suffix in RESERVED_SUFFIXES)


def _get_rdap_bootstrap(client: httpx.Client) -> dict[str, Any]:
    """Return cached IANA DNS RDAP bootstrap data, refreshing at most daily."""
    global _bootstrap_cache, _bootstrap_cached_at
    now = time.monotonic()
    if _bootstrap_cache is not None and now - _bootstrap_cached_at < BOOTSTRAP_TTL_SECONDS:
        return _bootstrap_cache
    with _bootstrap_lock:
        now = time.monotonic()
        if _bootstrap_cache is not None and now - _bootstrap_cached_at < BOOTSTRAP_TTL_SECONDS:
            return _bootstrap_cache
        response = client.get(IANA_RDAP_BOOTSTRAP_URL)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("services"), list):
            raise DomainCheckError("IANA RDAP bootstrap response had an unexpected format.")
        _bootstrap_cache = payload
        _bootstrap_cached_at = now
        return payload


def _rdap_base_url(domain: str, bootstrap: dict[str, Any]) -> str | None:
    """Find the longest matching TLD suffix per RFC 9224."""
    matches: list[tuple[int, str]] = []
    for service in bootstrap.get("services", []):
        if not isinstance(service, list) or len(service) != 2:
            continue
        entries, urls = service
        if not isinstance(entries, list) or not isinstance(urls, list):
            continue
        for entry in entries:
            if not isinstance(entry, str):
                continue
            suffix = entry.lower().lstrip(".")
            if domain == suffix or domain.endswith("." + suffix):
                for base in urls:
                    if isinstance(base, str) and base.startswith("https://"):
                        matches.append((len(suffix), base))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def _parse_rdap_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _rdap_domain_candidates(hostname: str) -> list[str]:
    """Return progressively less-specific hostnames for RDAP lookup.

    RDAP registries store registered domain objects, not arbitrary hostnames.
    For example, ``www.wikipedia.org`` is normally looked up as
    ``wikipedia.org``. If a registry rejects a hostname with 400/404, retry
    its parent; stop at two labels so a top-level domain is never queried as
    a domain object. The first successful registry object is authoritative.
    """
    labels = hostname.rstrip(".").lower().split(".")
    return [".".join(labels[index:]) for index in range(max(1, len(labels) - 1))]


def lookup_domain_registration(domain: str, timeout_seconds: float) -> dict[str, Any]:
    """Look up RDAP registration data, resolving hosts to registered domains."""
    input_domain = normalize_domain(domain) or ""
    if not input_domain or ":" in input_domain:
        raise DomainCheckError("The supplied domain is not a valid hostname.")
    try:
        ipaddress.ip_address(input_domain)
    except ValueError:
        pass
    else:
        raise DomainCheckError("RDAP registration age is not applicable to an IP address.")
    if is_reserved_domain(input_domain):
        raise DomainCheckError("Reserved documentation/test domains do not have live registration records.")

    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 4.0))
    headers = {"Accept": "application/rdap+json, application/json"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        bootstrap = _get_rdap_bootstrap(client)
        payload: Any = None
        selected_domain: str | None = None
        lookup_url: str | None = None
        last_not_found: str | None = None

        for candidate in _rdap_domain_candidates(input_domain):
            base_url = _rdap_base_url(candidate, bootstrap)
            if not base_url:
                raise DomainCheckError("IANA has no RDAP service entry for this top-level domain.")
            candidate_url = base_url.rstrip("/") + "/domain/" + quote(candidate, safe=".-")
            response = client.get(candidate_url)
            # Registries commonly return 400 (rather than 404) for a hostname
            # such as www.wikipedia.org. Retry only not-found/invalid-name
            # responses. A 429 or 5xx must remain an unavailable result.
            if response.status_code in {400, 404}:
                last_not_found = f"HTTP {response.status_code} for {candidate}"
                continue
            response.raise_for_status()
            candidate_payload = response.json()
            if not isinstance(candidate_payload, dict):
                raise DomainCheckError("The RDAP registry returned an unexpected record format.")
            selected_domain = candidate
            lookup_url = candidate_url
            payload = candidate_payload
            break

        if payload is None or selected_domain is None or lookup_url is None:
            detail = last_not_found or "No registered domain object was found."
            raise DomainCheckError(f"RDAP did not return a registered domain object ({detail}).")

    if not isinstance(payload, dict):
        raise DomainCheckError("The RDAP registry returned an unexpected record format.")
    events = payload.get("events", [])
    registration_date = None
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            action = str(event.get("eventAction", "")).casefold()
            if action in {"registration", "registered", "registration of domain name"}:
                registration_date = _parse_rdap_datetime(event.get("eventDate"))
                if registration_date:
                    break
    if registration_date is None:
        registration_date = _parse_rdap_datetime(payload.get("registrationDate"))
    if registration_date is None:
        raise DomainCheckError("The RDAP record did not contain a usable registration date.")

    now = datetime.now(timezone.utc)
    if registration_date > now:
        raise DomainCheckError("The RDAP registration date is in the future; age could not be calculated.")
    age_days = (now - registration_date).days
    return {
        "domain": selected_domain,
        "input_domain": input_domain,
        "registration_date": registration_date.isoformat(),
        "age_days": age_days,
        "rdap_url": lookup_url,
        "handle": payload.get("handle"),
        "ldh_name": payload.get("ldhName"),
    }


def _resolve_public_host(host: str, port: int) -> list[str]:
    """Resolve a hostname and fail closed unless every result is a public IP."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise UnsafeTargetError("The website target is not a public IP address.")
        return [str(literal)]

    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DomainCheckError("DNS resolution failed for the submitted domain.") from exc
    addresses = sorted({record[4][0] for record in records})
    if not addresses:
        raise DomainCheckError("The submitted domain did not resolve to an IP address.")
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as exc:
            raise DomainCheckError("DNS returned an invalid IP address.") from exc
        if not parsed.is_global:
            raise UnsafeTargetError("The domain resolves to a non-public IP address; the request was blocked.")
    return addresses


def _validated_url(url: str) -> tuple[str, str, int]:
    candidate = url.strip()
    if not candidate:
        raise DomainCheckError("No company website was present in the submitted material.")
    if "://" not in candidate:
        candidate = "https://" + candidate
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeTargetError("Only HTTP and HTTPS website URLs are supported.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeTargetError("The submitted website URL is malformed or contains credentials.")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    if port not in {80, 443}:
        raise UnsafeTargetError("Non-standard website ports are not checked for safety.")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    netloc = f"{host}:{port}" if parsed.port is not None else host
    normalized = parsed._replace(netloc=netloc, fragment="").geturl()
    return normalized, host, port


def check_website_availability(url: str, timeout_seconds: float, max_redirects: int = 3) -> dict[str, Any]:
    """Check whether an explicitly supplied public website responds to HTTP."""
    current_url = url
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 4.0))
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for redirect_count in range(max_redirects + 1):
            normalized, host, port = _validated_url(current_url)
            _resolve_public_host(host, port)
            with client.stream("HEAD", normalized) as response:
                status = response.status_code
                headers = response.headers
            if status in {405, 501}:
                with client.stream("GET", normalized) as response:
                    status = response.status_code
                    headers = response.headers
            if status in _REDIRECT_STATUSES:
                location = headers.get("location")
                if not location:
                    return {"url": normalized, "http_status": status, "reachable": True, "redirects": redirect_count}
                if redirect_count >= max_redirects:
                    raise DomainCheckError("The website exceeded the allowed redirect limit.")
                current_url = urljoin(normalized, location)
                continue
            return {
                "url": normalized,
                "final_url": normalized,
                "http_status": status,
                "reachable": True,
                "redirects": redirect_count,
                "content_type": headers.get("content-type"),
            }
    raise DomainCheckError("The website could not be reached within the redirect limit.")


def check_ssl_certificate(domain: str, timeout_seconds: float) -> dict[str, Any]:
    """Validate the HTTPS certificate chain and hostname using the system CA store."""
    host = normalize_domain(domain)
    if not host:
        raise DomainCheckError("No valid domain was available for TLS verification.")
    if is_reserved_domain(host):
        raise DomainCheckError("Reserved documentation/test domains do not have live TLS certificates.")
    _resolve_public_host(host, 443)
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=timeout_seconds) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:
                certificate = tls_socket.getpeercert()
                not_after = certificate.get("notAfter")
                expiry = None
                days_remaining = None
                if not_after:
                    expiry_timestamp = ssl.cert_time_to_seconds(not_after)
                    expiry = datetime.fromtimestamp(expiry_timestamp, timezone.utc)
                    days_remaining = (expiry - datetime.now(timezone.utc)).days
                subject = certificate.get("subject", ())
                issuer = certificate.get("issuer", ())
                return {
                    "domain": host,
                    "valid": True,
                    "not_after": expiry.isoformat() if expiry else None,
                    "days_remaining": days_remaining,
                    "subject": subject,
                    "issuer": issuer,
                    "tls_version": tls_socket.version(),
                }
    except ssl.SSLCertVerificationError as exc:
        raise DomainCheckError(f"TLS certificate validation failed: {exc.verify_message or 'certificate verification error'}") from exc
    except (OSError, ssl.SSLError, TimeoutError) as exc:
        raise DomainCheckError(f"TLS connection could not be completed: {type(exc).__name__}.") from exc
