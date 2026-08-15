from flask_login import UserMixin
from app.extensions import db

DIVISIONS = ("nasderm", "nasmedic")
ROLES = ("admin", "commercial")

WHOLESALERS = ("duopharm", "ubipharm", "laborex", "sodipharm")

STRUCTURES = [
    ("HOPITAL", "HOPITAL"),
    ("POSTE DE SANTE", "POSTE DE SANTE"),
    ("CENTRE DE SANTE", "CENTRE DE SANTE"),
    ("CLINIQUE", "CLINIQUE"),
    ("SAPEUR POMPIER", "SAPEUR POMPIER"),
    ("GENDARMERIE", "GENDARMERIE"),
    ("PHARMACIES", "PHARMACIES"),
]

STRUCTURE_SLUGS = {value: value.replace(" ", "_") for value, _ in STRUCTURES}
STRUCTURE_BY_SLUG = {slug: value for value, slug in STRUCTURE_SLUGS.items()}

JOURS = [
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'admin' | 'commercial'
    zone = db.Column(db.String(100), nullable=True)
    project = db.Column(db.String(50), nullable=False)  # 'nasderm' | 'nasmedic'
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<User {self.username} ({self.role}/{self.project})>"


class Prospection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    commercial_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    nom_client = db.Column(db.String(150), nullable=False)
    specialite = db.Column(db.String(150), nullable=False)
    structure = db.Column(db.String(150), nullable=False)
    telephone = db.Column(db.String(30), nullable=False)
    profils_prospect = db.Column(db.Text, nullable=True)
    produits_presentes = db.Column(db.Text, nullable=True)
    produits_prescrits = db.Column(db.Text, nullable=True)

    commercial = db.relationship("User", backref=db.backref("prospections", lazy="dynamic"))


class Planning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    commercial_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)  # Date de début de la semaine

    lundi_matin = db.Column(db.Text, nullable=True)
    lundi_soir = db.Column(db.Text, nullable=True)
    mardi_matin = db.Column(db.Text, nullable=True)
    mardi_soir = db.Column(db.Text, nullable=True)
    mercredi_matin = db.Column(db.Text, nullable=True)
    mercredi_soir = db.Column(db.Text, nullable=True)
    jeudi_matin = db.Column(db.Text, nullable=True)
    jeudi_soir = db.Column(db.Text, nullable=True)
    vendredi_matin = db.Column(db.Text, nullable=True)
    vendredi_soir = db.Column(db.Text, nullable=True)
    samedi_matin = db.Column(db.Text, nullable=True)
    samedi_soir = db.Column(db.Text, nullable=True)
    dimanche_matin = db.Column(db.Text, nullable=True)
    dimanche_soir = db.Column(db.Text, nullable=True)

    commercial = db.relationship("User", backref=db.backref("plannings", lazy="dynamic"))


class ProductMixin:
    """Colonnes communes à tous les produits fournisseurs."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    reference = db.Column(db.String(100), nullable=True)
    default_price = db.Column(db.Float, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    stock_duopharm = db.Column(db.Integer, default=0, nullable=False)
    stock_ubipharm = db.Column(db.Integer, default=0, nullable=False)
    stock_laborex = db.Column(db.Integer, default=0, nullable=False)
    stock_sodipharm = db.Column(db.Integer, default=0, nullable=False)


class SaleMixin:
    """Colonnes communes à toutes les ventes fournisseurs."""
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    project = db.Column(db.String(50), nullable=False)


class NovaPharmaProduct(ProductMixin, db.Model):
    __tablename__ = "nova_pharma_product"


class GilbertProduct(ProductMixin, db.Model):
    __tablename__ = "gilbert_product"


class EricFavreProduct(ProductMixin, db.Model):
    __tablename__ = "eric_favre_product"


class TroisCheneProduct(ProductMixin, db.Model):
    __tablename__ = "trois_chene_product"


class NovaPharmaSale(SaleMixin, db.Model):
    __tablename__ = "nova_pharma_sale"
    product_id = db.Column(db.Integer, db.ForeignKey("nova_pharma_product.id"), nullable=False)
    commercial_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product = db.relationship("NovaPharmaProduct")
    commercial = db.relationship("User")


class GilbertSale(SaleMixin, db.Model):
    __tablename__ = "gilbert_sale"
    product_id = db.Column(db.Integer, db.ForeignKey("gilbert_product.id"), nullable=False)
    commercial_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product = db.relationship("GilbertProduct")
    commercial = db.relationship("User")


class EricFavreSale(SaleMixin, db.Model):
    __tablename__ = "eric_favre_sale"
    product_id = db.Column(db.Integer, db.ForeignKey("eric_favre_product.id"), nullable=False)
    commercial_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product = db.relationship("EricFavreProduct")
    commercial = db.relationship("User")


class TroisCheneSale(SaleMixin, db.Model):
    __tablename__ = "trois_chene_sale"
    product_id = db.Column(db.Integer, db.ForeignKey("trois_chene_product.id"), nullable=False)
    commercial_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product = db.relationship("TroisCheneProduct")
    commercial = db.relationship("User")


SUPPLIERS = {
    "nova_pharma": {
        "label": "Nova Pharma",
        "division": "nasderm",
        "product_model": NovaPharmaProduct,
        "sale_model": NovaPharmaSale,
        "archived": True,  # ne fait plus partie de NASDERM (retiré le 2026-08)
    },
    "gilbert": {
        "label": "Gilbert",
        "division": "nasderm",
        "product_model": GilbertProduct,
        "sale_model": GilbertSale,
        "archived": False,
    },
    "eric_favre": {
        "label": "Eric Favre",
        "division": "nasmedic",
        "product_model": EricFavreProduct,
        "sale_model": EricFavreSale,
        "archived": False,
    },
    "trois_chene": {
        "label": "3 Chênes Pharma",
        "division": "nasmedic",
        "product_model": TroisCheneProduct,
        "sale_model": TroisCheneSale,
        "archived": False,
    },
}

# Dérivé automatiquement de SUPPLIERS : pour ajouter un nouveau laboratoire à une
# division, il suffit de l'ajouter ci-dessus avec archived=False, il apparaîtra
# alors partout (navigation, saisie des ventes, fiches produits, CA) sans autre
# modification. Un laboratoire archivé (archived=True) disparaît de partout,
# y compris des rapports de CA passés, mais ses données restent en base.
DIVISION_SUPPLIERS = {
    "nasderm": [slug for slug, s in SUPPLIERS.items() if s["division"] == "nasderm" and not s["archived"]],
    "nasmedic": [slug for slug, s in SUPPLIERS.items() if s["division"] == "nasmedic" and not s["archived"]],
}
