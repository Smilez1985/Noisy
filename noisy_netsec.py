#!/usr/bin/env python3
"""
Noisy Netsec - Netzwerk-Sicherheit fuer das Web-UI

Zwei Aufgaben, bewusst Flask-frei gehalten (rein testbar):

1. Sicherer Modell-Download (/download):
     - nur http/https + .tar.bz2
     - Host-Allowlist (editierbar in noisy_config.py)
     - IP-Sperre: URLs, die auf private/loopback/link-local/reservierte
       Adressen aufloesen, werden IMMER abgelehnt -> kein SSRF ins LAN
     - Redirects werden NICHT automatisch gefolgt, sondern Hop fuer Hop
       neu validiert (sonst koennte ein 302 die Allowlist umgehen)
     - Groessen-Limit + Pruefung auf freien Speicher
     - Entpacken mit tar-Filter 'data' -> keine Symlinks/Hardlinks/
       absolute Pfade entkommen dem Zielverzeichnis

2. Self-Signed-TLS-Zertifikat (HTTPS-Toggle):
     - via 'cryptography' wenn vorhanden, sonst 'openssl'-Fallback
     - macht das Dashboard portabel verschluesselbar, ganz ohne
       Reverse-Proxy (Caddy o. ae. ist optional, nicht noetig)
"""

import os
import shutil
import socket
import logging
import tarfile
import ipaddress
import subprocess
import urllib.request
import urllib.error
from urllib.parse import urlparse, urljoin

from noisy_config import (
    MODEL_DOWNLOAD_ALLOWLIST,
    MODEL_DOWNLOAD_MAX_BYTES,
    MODEL_DOWNLOAD_MIN_FREE_BYTES,
    MODEL_DOWNLOAD_MAX_REDIRECTS,
    MODEL_DOWNLOAD_TIMEOUT,
)

log = logging.getLogger('noisy-netsec')


class SecurityError(Exception):
    """Wird geworfen, wenn eine URL/ein Archiv eine Sicherheitsregel verletzt."""
    pass


# ============================================================
# URL- / IP-Validierung (SSRF-Schutz)
# ============================================================
def host_allowed(host):
    """True, wenn host exakt auf der Allowlist steht oder Subdomain davon ist."""
    if not host:
        return False
    host = host.lower().rstrip('.')
    for allowed in MODEL_DOWNLOAD_ALLOWLIST:
        a = allowed.lower()
        if host == a or host.endswith('.' + a):
            return True
    return False


def _ip_is_public(ip_str):
    """False fuer private/loopback/link-local/reservierte/multicast Adressen."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def resolve_host_public(host):
    """
    Loest host auf und stellt sicher, dass JEDE aufgeloeste Adresse
    oeffentlich ist. Gibt die Liste der IPs zurueck oder wirft SecurityError.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise SecurityError("Host nicht aufloesbar: %s (%s)" % (host, e))

    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise SecurityError("Host loest auf keine Adresse auf: %s" % host)

    for ip in ips:
        if not _ip_is_public(ip):
            raise SecurityError(
                "Host '%s' zeigt auf nicht-oeffentliche Adresse %s "
                "(SSRF-Schutz)" % (host, ip)
            )
    return ips


def validate_download_url(url):
    """
    Prueft Schema, Endung, Host-Allowlist und IP-Aufloesung.
    Gibt das geparste URL-Objekt zurueck oder wirft SecurityError.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise SecurityError("Nur http/https-URLs sind erlaubt.")
    if not parsed.hostname:
        raise SecurityError("URL ohne Host.")
    if not host_allowed(parsed.hostname):
        raise SecurityError(
            "Host '%s' steht nicht auf der Allowlist." % parsed.hostname
        )
    resolve_host_public(parsed.hostname)
    return parsed


# ============================================================
# Sicherer Download (manuelles, geprueftes Redirect-Following)
# ============================================================
class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    """Verhindert automatisches Redirect-Following - wir pruefen jeden Hop selbst."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoAutoRedirect)


def download_to_file(url, dest_path):
    """
    Laedt url nach dest_path. Folgt Redirects manuell und validiert
    jeden Ziel-Host (Allowlist + oeffentliche IP) erneut. Erzwingt
    Groessen-Limit und prueft freien Speicher. Wirft SecurityError /
    Exception bei Problemen.
    """
    # Freier Speicher?
    free = shutil.disk_usage(os.path.dirname(dest_path) or '.').free
    if free < MODEL_DOWNLOAD_MIN_FREE_BYTES:
        raise SecurityError(
            "Zu wenig freier Speicher (%d MB frei, %d MB noetig)."
            % (free // (1024 * 1024),
               MODEL_DOWNLOAD_MIN_FREE_BYTES // (1024 * 1024))
        )

    current = url
    for _hop in range(MODEL_DOWNLOAD_MAX_REDIRECTS + 1):
        validate_download_url(current)  # jeder Hop neu geprueft
        req = urllib.request.Request(current, headers={'User-Agent': 'Noisy'})
        resp = _opener.open(req, timeout=MODEL_DOWNLOAD_TIMEOUT)

        code = getattr(resp, 'status', resp.getcode())
        if code in (301, 302, 303, 307, 308):
            location = resp.headers.get('Location')
            resp.close()
            if not location:
                raise SecurityError("Redirect ohne Ziel (Location fehlt).")
            current = urljoin(current, location)
            continue

        # Optional: vorab gemeldete Groesse pruefen
        clen = resp.headers.get('Content-Length')
        if clen and clen.isdigit() and int(clen) > MODEL_DOWNLOAD_MAX_BYTES:
            resp.close()
            raise SecurityError(
                "Datei groesser als erlaubt (%d MB)."
                % (MODEL_DOWNLOAD_MAX_BYTES // (1024 * 1024))
            )

        # Streamen mit hartem Limit
        downloaded = 0
        with resp, open(dest_path, 'wb') as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > MODEL_DOWNLOAD_MAX_BYTES:
                    raise SecurityError(
                        "Datei groesser als erlaubt (%d MB)."
                        % (MODEL_DOWNLOAD_MAX_BYTES // (1024 * 1024))
                    )
                f.write(chunk)
        return dest_path

    raise SecurityError("Zu viele Redirects (max. %d)." % MODEL_DOWNLOAD_MAX_REDIRECTS)


# ============================================================
# Sicheres Entpacken (Symlink-/Traversal-fest)
# ============================================================
def _manual_safe_extract(tar, dest):
    """Fallback fuer Python < 3.12: kein Symlink/Hardlink/Traversal."""
    dest_abs = os.path.abspath(dest)
    safe_members = []
    for m in tar.getmembers():
        if m.issym() or m.islnk():
            raise SecurityError("Sym-/Hardlink im Archiv abgelehnt: %s" % m.name)
        if m.isdev():
            raise SecurityError("Geraetedatei im Archiv abgelehnt: %s" % m.name)
        target = os.path.abspath(os.path.join(dest, m.name))
        if target != dest_abs and not target.startswith(dest_abs + os.sep):
            raise SecurityError("Unsicherer Pfad im Archiv: %s" % m.name)
        safe_members.append(m)
    tar.extractall(dest, members=safe_members)


def safe_extract_bz2(archive_path, dest):
    """
    Entpackt ein .tar.bz2 sicher nach dest. Nutzt den eingebauten
    tar-Filter 'data' (Python 3.12+), der Symlinks/Hardlinks/absolute
    Pfade/Geraetedateien strippt. Aeltere Python-Versionen: manueller
    Fallback. Normale Sherpa-Modelle (nur Dateien) entpacken normal.
    """
    with tarfile.open(archive_path, 'r:bz2') as tar:
        try:
            tar.extractall(dest, filter='data')   # Python 3.12+
        except TypeError:
            _manual_safe_extract(tar, dest)


# ============================================================
# Self-Signed TLS Zertifikat
# ============================================================
def _gen_cert_cryptography(cert_path, key_path):
    """Erzeugt ein Self-Signed-Zertifikat via 'cryptography'-Lib."""
    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"Noisy")])
    san = x509.SubjectAlternativeName([
        x509.DNSName(u"noisy.local"),
        x509.DNSName(u"gamepi13.local"),
        x509.DNSName(u"localhost"),
    ])
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(key_path, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass


def _gen_cert_openssl(cert_path, key_path):
    """Fallback: Self-Signed-Zertifikat via openssl-CLI."""
    subprocess.run(
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
         '-keyout', key_path, '-out', cert_path, '-days', '3650',
         '-subj', '/CN=Noisy'],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass


def ensure_self_signed_cert(cert_path, key_path):
    """
    Stellt sicher, dass Cert + Key existieren. Erzeugt sie bei Bedarf.
    Gibt True zurueck, wenn am Ende beide Dateien vorhanden sind.
    """
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return True
    for generator in (_gen_cert_cryptography, _gen_cert_openssl):
        try:
            generator(cert_path, key_path)
            if os.path.exists(cert_path) and os.path.exists(key_path):
                log.info("Self-Signed-Zertifikat erstellt (%s)", generator.__name__)
                return True
        except Exception as e:
            log.warning("Zertifikat-Erzeugung via %s fehlgeschlagen: %s",
                        generator.__name__, e)
    return False
