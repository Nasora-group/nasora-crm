from functools import wraps
import json

from flask import flash, redirect, url_for
from flask_login import current_user


def roles_required(*roles):
    """Restreint l'accès à une route aux rôles listés.
    Usage : @roles_required('admin') ou @roles_required('admin', 'commercial')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                flash("Accès non autorisé.", "error")
                return redirect(url_for("auth.home"))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def division_matches(user, division):
    """Un commercial ne doit voir/agir que sur les données de sa propre division."""
    return user.role == "admin" or user.project == division


def encode_planning_slot(entries):
    """entries : liste de tuples (type_structure, nom_precis) -> chaîne JSON,
    ou None si la liste est vide (créneau non renseigné)."""
    cleaned = [(t, (n or "").strip()) for t, n in entries if t]
    if not cleaned:
        return None
    return json.dumps([{"type": t, "nom": n} for t, n in cleaned], ensure_ascii=False)


def decode_planning_slot(raw):
    """Chaîne JSON -> liste de tuples (type_structure, nom_precis).
    Reste compatible avec l'ancien format ('HOPITAL, CLINIQUE') pour ne pas
    perdre les plannings déjà saisis avant cette évolution."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [(item.get("type", ""), item.get("nom", "")) for item in data]
    except (ValueError, TypeError):
        return [(value.strip(), "") for value in raw.split(",") if value.strip()]


def format_planning_slot(raw):
    """Représentation lisible d'un créneau pour l'affichage dans les templates."""
    entries = decode_planning_slot(raw)
    if not entries:
        return ""
    parts = []
    for structure_type, nom in entries:
        parts.append(f"{structure_type} ({nom})" if nom else structure_type)
    return ", ".join(parts)


def planning_entries(raw):
    """Comme decode_planning_slot, mais exposé en filtre Jinja pour construire
    un affichage riche (badges colorés) plutôt qu'une simple chaîne de texte."""
    return decode_planning_slot(raw)
