"""Protection temporaire contre les tentatives de connexion abusives.

Principes :

* Le compteur d'échecs est propre au COUPLE (adresse IP, identifiant). Une
  personne qui se trompe ne bloque donc que sa propre adresse : un tiers ne
  peut plus verrouiller le compte d'un collègue (par exemple l'administrateur)
  en envoyant de faux mots de passe depuis une autre adresse.
* Le délai de blocage double à chaque échec supplémentaire après le seuil
  (30 s, 1 min, 2 min... plafonné à 15 min) au lieu d'un blocage fixe.
* Un second compteur, par adresse IP seule, ralentit le « password spraying »
  (un même attaquant qui essaie beaucoup d'identifiants différents).
* Une connexion réussie ne remet à zéro que le compteur du couple, jamais celui
  de l'adresse IP : un attaquant qui possède un compte valide ne peut pas
  s'en servir pour effacer ses échecs sur les autres comptes.

Les compteurs vivent dans le backend Flask-Caching. Il doit être PARTAGÉ entre
les workers gunicorn : Redis si ``CACHE_REDIS_URL`` est défini, sinon un cache
fichier dans ``instance/cache`` (voir ``app/config.py``). Aucune colonne ni
migration n'est nécessaire.

L'adresse IP vient de ``request.remote_addr``. Derrière le proxy de
l'hébergeur, elle n'est correcte que si ``TRUSTED_PROXY_COUNT`` (ProxyFix, voir
``app/__init__.py``) correspond au nombre réel de proxys.
"""
import hashlib
import time

from flask import has_request_context, request

from app.extensions import cache

# Couple (IP, identifiant)
FAILED_LIMIT = 5                 # échecs tolérés avant le premier blocage
FAILED_WINDOW_SECONDS = 10 * 60  # fenêtre de comptage
BACKOFF_BASE_SECONDS = 30        # premier blocage ; doublé à chaque échec suivant
MAX_LOCKOUT_SECONDS = 15 * 60    # plafond du blocage

# Adresse IP seule (tous identifiants confondus)
IP_LIMIT = 50
IP_WINDOW_SECONDS = 10 * 60
IP_LOCKOUT_SECONDS = 15 * 60


def _now():
    return time.time()


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def client_ip():
    """Adresse du client, ou valeur stable hors requête HTTP."""
    if not has_request_context():
        return "no-request-context"
    return request.remote_addr or "unknown"


def _key(prefix, value):
    return f"nasora:login:{prefix}:{_digest(value)}"


def _pair_key(username):
    username_key = username.strip().lower()
    return _key("pair", f"{client_ip()}|{username_key}")


def _ip_key():
    return _key("ip", client_ip())


def _get_state(key):
    state = cache.get(key)
    return state if isinstance(state, dict) else None


def _pair_lockout_seconds(count):
    """Durée de blocage après ``count`` échecs (0 tant que le seuil n'est pas atteint)."""
    if count < FAILED_LIMIT:
        return 0
    return min(MAX_LOCKOUT_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (count - FAILED_LIMIT)))


def is_blocked(username):
    now = _now()
    states = (_get_state(_pair_key(username)), _get_state(_ip_key()))
    return any(state and float(state.get("blocked_until", 0)) > now for state in states)


def _bump(key, window, lockout_for_count):
    now = _now()
    state = _get_state(key) or {"count": 0, "window_started": now, "blocked_until": 0}
    if now - float(state.get("window_started", now)) >= window:
        state = {"count": 0, "window_started": now, "blocked_until": 0}
    state["count"] = int(state.get("count", 0)) + 1
    lockout = lockout_for_count(state["count"])
    if lockout:
        state["blocked_until"] = now + lockout
    ttl = int(max(window, lockout, MAX_LOCKOUT_SECONDS, IP_LOCKOUT_SECONDS)) + 5
    cache.set(key, state, timeout=ttl)


def record_failure(username):
    _bump(_pair_key(username), FAILED_WINDOW_SECONDS, _pair_lockout_seconds)
    _bump(
        _ip_key(),
        IP_WINDOW_SECONDS,
        lambda count: IP_LOCKOUT_SECONDS if count >= IP_LIMIT else 0,
    )


def clear_failures(username):
    """Remet à zéro le compteur du couple (IP, identifiant) uniquement."""
    cache.delete(_pair_key(username))


def retry_after(username):
    now = _now()
    states = (_get_state(_pair_key(username)), _get_state(_ip_key()))
    remaining = [float(s.get("blocked_until", 0)) - now for s in states if s]
    return max(0, int(max(remaining, default=0)))
