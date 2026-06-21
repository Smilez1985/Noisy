#!/usr/bin/env python3
"""
Noisy Auth - Admin-Login fuer das Web-UI

Ein Admin-Benutzer, ein Passwort. Bewusst schlank, weil Noisy ein
dediziertes LAN-Geraet ohne Port nach aussen ist - die Auth ist ein
Riegel, kein Tresor.

Speicher: auth.json auf der SD (ueberlebt Reboot).
  {
    "secret":     <hex>,   # Flask-Session-Secret (immer vorhanden)
    "salt":       <hex>,   # nur wenn Passwort gesetzt
    "hash":       <hex>,
    "iterations": <int>,
    "created":    <ts>
  }

Passwort-Hash: PBKDF2-HMAC-SHA256 mit zufaelligem Salt (stdlib, keine
externe Abhaengigkeit). Vergleich konstantzeitlich (hmac.compare_digest).

Passwort-Reset ("Passwort vergessen"): loescht NUR das Passwort-Material
(salt/hash/iterations). Das Session-Secret bleibt, Personality/Config/
Modelle werden nicht angefasst. Danach erzwingt das Web-UI den
First-Login-Flow (neues Passwort setzen).
"""

import os
import time
import json
import hmac
import hashlib
import secrets
import threading

from noisy_config import (
    AUTH_FILE,
    PASSWORD_RESET_PHRASES,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_LOCKOUT_SECONDS,
)

PBKDF2_ITERATIONS = 200000          # auf Pi Zero 2 vertretbar, fuer Login (selten)
MIN_PASSWORD_LENGTH = 4


def is_reset_phrase(text):
    """True, wenn text einer der Reset-Phrasen entspricht (case-insensitive)."""
    if not text:
        return False
    norm = ' '.join(str(text).strip().lower().split())
    for phrase in PASSWORD_RESET_PHRASES:
        if norm == ' '.join(phrase.strip().lower().split()):
            return True
    return False


class AuthManager:
    """Verwaltet Admin-Passwort, Session-Secret und Login-Rate-Limit."""

    def __init__(self, path=AUTH_FILE):
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()
        # Session-Secret muss immer existieren (auch vor First-Login)
        if not self._data.get('secret'):
            self._data['secret'] = secrets.token_hex(32)
            self._save()
        # Rate-Limit (in-memory, pro IP) - bewusst nicht persistent
        self._attempts = {}   # ip -> {'fails': int, 'until': ts}

    # ----------------------------------------------------------
    # Laden / Speichern (atomar, 0600)
    # ----------------------------------------------------------
    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save(self):
        tmp = self.path + '.tmp'
        try:
            with open(tmp, 'w') as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    # ----------------------------------------------------------
    # Session-Secret
    # ----------------------------------------------------------
    def get_secret(self):
        """Gibt das Flask-Session-Secret als bytes zurueck."""
        with self._lock:
            return self._data['secret'].encode('utf-8')

    # ----------------------------------------------------------
    # Passwort
    # ----------------------------------------------------------
    def is_password_set(self):
        with self._lock:
            return bool(self._data.get('hash'))

    @staticmethod
    def _hash(password, salt, iterations):
        return hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt, iterations
        )

    def set_password(self, password):
        """
        Setzt ein neues Passwort. Gibt (ok, message) zurueck.
        Reset-Phrasen sind als Passwort verboten (sonst sperrt man sich aus).
        """
        if password is None:
            return False, "Kein Passwort angegeben."
        if is_reset_phrase(password):
            return False, "Dieses Passwort ist reserviert. Bitte ein anderes waehlen."
        if len(password) < MIN_PASSWORD_LENGTH:
            return False, ("Passwort zu kurz (min. %d Zeichen)." % MIN_PASSWORD_LENGTH)
        with self._lock:
            salt = secrets.token_bytes(16)
            digest = self._hash(password, salt, PBKDF2_ITERATIONS)
            self._data['salt'] = salt.hex()
            self._data['hash'] = digest.hex()
            self._data['iterations'] = PBKDF2_ITERATIONS
            self._data['created'] = time.time()
            self._save()
        return True, "Passwort gesetzt."

    def verify_password(self, password):
        """Konstantzeitlicher Vergleich. False, wenn kein Passwort gesetzt ist."""
        if not password:
            return False
        with self._lock:
            if not self._data.get('hash'):
                return False
            salt = bytes.fromhex(self._data['salt'])
            iterations = int(self._data.get('iterations', PBKDF2_ITERATIONS))
            expected = bytes.fromhex(self._data['hash'])
        digest = self._hash(password, salt, iterations)
        return hmac.compare_digest(digest, expected)

    def reset_password(self):
        """
        Loescht NUR das Passwort-Material. Session-Secret bleibt erhalten,
        alles andere (Personality, Config, Modelle) bleibt unangetastet.
        """
        with self._lock:
            self._data.pop('salt', None)
            self._data.pop('hash', None)
            self._data.pop('iterations', None)
            self._data.pop('created', None)
            self._save()
        return True

    # ----------------------------------------------------------
    # Rate-Limit / Lockout (Brute-Force-Bremse, pro IP)
    # ----------------------------------------------------------
    def is_locked(self, ip):
        with self._lock:
            rec = self._attempts.get(ip)
            if not rec:
                return False
            if rec['until'] and time.time() < rec['until']:
                return True
            # Sperre abgelaufen -> zuruecksetzen
            if rec['until'] and time.time() >= rec['until']:
                self._attempts.pop(ip, None)
            return False

    def seconds_until_unlock(self, ip):
        with self._lock:
            rec = self._attempts.get(ip)
            if rec and rec['until']:
                return max(0, int(rec['until'] - time.time()))
            return 0

    def register_failure(self, ip):
        """Zaehlt einen Fehlversuch. Sperrt die IP bei Ueberschreitung."""
        with self._lock:
            rec = self._attempts.setdefault(ip, {'fails': 0, 'until': 0})
            rec['fails'] += 1
            if rec['fails'] >= LOGIN_MAX_ATTEMPTS:
                rec['until'] = time.time() + LOGIN_LOCKOUT_SECONDS
                rec['fails'] = 0

    def register_success(self, ip):
        with self._lock:
            self._attempts.pop(ip, None)
