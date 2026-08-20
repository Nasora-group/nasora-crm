from flask_wtf import FlaskForm
from wtforms import (
    StringField, DateField, TextAreaField, SubmitField, PasswordField,
    SelectMultipleField, SelectField, BooleanField, FloatField, IntegerField,
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError, NumberRange

from app.models import STRUCTURES


class LoginForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(max=150)])
    password = PasswordField("Mot de passe", validators=[DataRequired()])
    submit = SubmitField("Se connecter")


class DownloadExcelForm(FlaskForm):
    submit = SubmitField("Télécharger en Excel")


class ProspectionForm(FlaskForm):
    date = DateField("Date", validators=[DataRequired()])
    nom_client = StringField("Nom du client", validators=[DataRequired(), Length(max=150)])
    specialite = StringField("Spécialité", validators=[DataRequired(), Length(max=150)])
    structure = StringField("Structure", validators=[DataRequired(), Length(max=150)])
    telephone = StringField("Téléphone", validators=[DataRequired(), Length(max=30)])
    profils_prospect = TextAreaField("Profils prospect")
    # Choix renseignés dynamiquement dans la route selon la division du commercial
    # (catalogue produits NASDERM ou NASMEDIC) — voir app/routes/dashboard.py.
    produits_presentes = SelectMultipleField("Produits présentés", choices=[], validators=[Optional()])
    produits_prescrits = SelectMultipleField("Produits prescrits", choices=[], validators=[Optional()])
    submit = SubmitField("Enregistrer")


class PlanningForm(FlaskForm):
    date = DateField("Date de début de la semaine", validators=[DataRequired()])

    lundi = SelectMultipleField("Lundi", choices=STRUCTURES)
    mardi = SelectMultipleField("Mardi", choices=STRUCTURES)
    mercredi = SelectMultipleField("Mercredi", choices=STRUCTURES)
    jeudi = SelectMultipleField("Jeudi", choices=STRUCTURES)
    vendredi = SelectMultipleField("Vendredi", choices=STRUCTURES)
    samedi = SelectMultipleField("Samedi", choices=STRUCTURES)
    dimanche = SelectMultipleField("Dimanche", choices=STRUCTURES)

    submit = SubmitField("Valider le planning")


class SupplierSalesForm(FlaskForm):
    """Formulaire générique utilisé pour les 4 fournisseurs (CSRF uniquement,
    les lignes produits sont générées dynamiquement dans le template)."""
    sale_date = DateField("Date de saisie", validators=[DataRequired()])
    submit = SubmitField("Enregistrer les ventes")


class CSRFOnlyForm(FlaskForm):
    """Formulaire minimal utilisé pour les boutons d'action (activer/désactiver...)
    qui n'ont besoin que d'une protection CSRF, sans autre champ."""
    pass


class UserForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(max=150)])
    role = SelectField(
        "Rôle",
        choices=[("commercial", "Commercial"), ("admin", "Administrateur")],
        validators=[DataRequired()],
    )
    project = SelectField(
        "Division",
        choices=[("nasderm", "NASDERM"), ("nasmedic", "NASMEDIC")],
        validators=[DataRequired()],
    )
    zone = StringField("Zone", validators=[Optional(), Length(max=100)])
    password = PasswordField(
        "Mot de passe",
        validators=[Optional(), Length(min=8, message="8 caractères minimum.")],
    )
    is_active_account = BooleanField("Compte actif", default=True)
    submit = SubmitField("Enregistrer")


class ProductForm(FlaskForm):
    name = StringField("Nom du produit", validators=[DataRequired(), Length(max=200)])
    reference = StringField("Référence / code produit", validators=[Optional(), Length(max=100)])
    default_price = FloatField("Prix HT par défaut (€)", validators=[DataRequired()])
    is_active = BooleanField("Référence active", default=True)
    submit = SubmitField("Enregistrer")


class SaleEditForm(FlaskForm):
    date = DateField("Date de vente", validators=[DataRequired()])
    quantity = IntegerField("Quantité vendue", validators=[DataRequired(), NumberRange(min=1, message="La quantité doit être supérieure à 0.")])
    price = FloatField("Prix HT unitaire (€)", validators=[DataRequired(), NumberRange(min=0, message="Le prix ne peut pas être négatif.")])
    submit = SubmitField("Enregistrer")


class ObjectiveForm(FlaskForm):
    annual_target = FloatField("Objectif annuel (€)", validators=[Optional(), NumberRange(min=0)])
    jan = FloatField("Janvier (€)", validators=[Optional(), NumberRange(min=0)])
    feb = FloatField("Février (€)", validators=[Optional(), NumberRange(min=0)])
    mar = FloatField("Mars (€)", validators=[Optional(), NumberRange(min=0)])
    apr = FloatField("Avril (€)", validators=[Optional(), NumberRange(min=0)])
    may = FloatField("Mai (€)", validators=[Optional(), NumberRange(min=0)])
    jun = FloatField("Juin (€)", validators=[Optional(), NumberRange(min=0)])
    jul = FloatField("Juillet (€)", validators=[Optional(), NumberRange(min=0)])
    aug = FloatField("Août (€)", validators=[Optional(), NumberRange(min=0)])
    sep = FloatField("Septembre (€)", validators=[Optional(), NumberRange(min=0)])
    oct = FloatField("Octobre (€)", validators=[Optional(), NumberRange(min=0)])
    nov = FloatField("Novembre (€)", validators=[Optional(), NumberRange(min=0)])
    dec = FloatField("Décembre (€)", validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField("Enregistrer les objectifs")
