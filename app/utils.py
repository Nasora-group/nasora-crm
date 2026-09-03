import json

from app.permissions import division_matches, authorize_role

# Backward-compatible alias: existing routes can keep @roles_required while
# authorization is now implemented centrally in app.permissions.
roles_required = authorize_role


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
    """Comme decode_planning_slot, mais exposé comme filtre Jinja pour construire
    un affichage riche (badges colorés) plutôt qu'une simple chaîne de texte."""
    return decode_planning_slot(raw)
