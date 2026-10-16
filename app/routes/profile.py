from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from io import BytesIO

from app.audit_log import audit
from app.extensions import db
from app.models import UserProfile

profile_bp = Blueprint("profile", __name__)
MAX_PHOTO_BYTES = 2 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}


def _profile_for_current_user():
    profile = current_user.profile
    if profile is None:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.flush()
    return profile


@profile_bp.route("/mon-profil", methods=["GET", "POST"])
@login_required
def my_profile():
    profile = _profile_for_current_user()
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        job_title = request.form.get("job_title", "").strip()
        city = request.form.get("city", "").strip()

        limits = {
            "Prénom": (first_name, 100),
            "Nom": (last_name, 100),
            "E-mail": (email, 254),
            "Téléphone": (phone, 40),
            "Fonction": (job_title, 120),
            "Ville": (city, 120),
        }
        invalid = next((label for label, (value, limit) in limits.items() if len(value) > limit), None)
        if invalid:
            flash(f"Le champ « {invalid} » dépasse la longueur autorisée.", "error")
            return render_template("profile.html", profile=profile)

        if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
            flash("Saisis une adresse e-mail valide.", "error")
            return render_template("profile.html", profile=profile)

        photo = request.files.get("photo")
        photo_bytes = photo.read(MAX_PHOTO_BYTES + 1) if photo and photo.filename else b""
        if photo_bytes:
            if len(photo_bytes) > MAX_PHOTO_BYTES:
                flash("La photo ne doit pas dépasser 2 Mo.", "error")
                return render_template("profile.html", profile=profile)
            mime_type = (photo.mimetype or "").lower()
            signature_check = ALLOWED_PHOTO_TYPES.get(mime_type)
            if not signature_check or not signature_check(photo_bytes):
                flash("Format de photo non accepté. Utilise une image JPEG, PNG ou WebP.", "error")
                return render_template("profile.html", profile=profile)
            profile.photo_data = photo_bytes
            profile.photo_mime_type = mime_type

        if request.form.get("remove_photo") == "1":
            profile.photo_data = None
            profile.photo_mime_type = None

        profile.first_name = first_name or None
        profile.last_name = last_name or None
        profile.email = email or None
        profile.phone = phone or None
        profile.job_title = job_title or None
        profile.city = city or None

        try:
            db.session.commit()
            audit("profile.update", target=current_user.username, details="personal profile updated")
            flash("Ton profil a été enregistré.", "success")
            return redirect(url_for("profile.my_profile"))
        except Exception:
            db.session.rollback()
            current_profile = _profile_for_current_user()
            flash("Impossible d'enregistrer le profil pour le moment. Réessaie.", "error")
            return render_template("profile.html", profile=current_profile), 500

    db.session.commit()
    return render_template("profile.html", profile=profile)


@profile_bp.route("/mon-profil/photo")
@login_required
def profile_photo():
    profile = current_user.profile
    if not profile or not profile.photo_data or profile.photo_mime_type not in ALLOWED_PHOTO_TYPES:
        abort(404)
    response = send_file(
        BytesIO(profile.photo_data),
        mimetype=profile.photo_mime_type,
        download_name="nasora-profile",
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
