from datetime import datetime
from decimal import Decimal
from flask_login import UserMixin
from app.extensions import db

DIVISIONS=("nasderm","nasmedic"); ROLES=("admin","commercial"); WHOLESALERS=("duopharm","ubipharm","laborex","sodipharm")
STRUCTURES=[("HOPITAL","HOPITAL"),("POSTE DE SANTE","POSTE DE SANTE"),("CENTRE DE SANTE","CENTRE DE SANTE"),("CLINIQUE","CLINIQUE"),("SAPEUR POMPIER","SAPEUR POMPIER"),("GENDARMERIE","GENDARMERIE"),("PHARMACIES","PHARMACIES")]
STRUCTURE_SLUGS={value:value.replace(" ","_") for value,_ in STRUCTURES}; STRUCTURE_BY_SLUG={slug:value for value,slug in STRUCTURE_SLUGS.items()}; STRUCTURE_COLORS={"HOPITAL":"#4a6741","POSTE DE SANTE":"#8faf6d","CENTRE DE SANTE":"#2b6cb0","CLINIQUE":"#8e5fd1","SAPEUR POMPIER":"#c0392b","GENDARMERIE":"#5b6b5e","PHARMACIES":"#c98a2c"}
JOURS=["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]; JOURS_LABELS={"lundi":"Lundi","mardi":"Mardi","mercredi":"Mercredi","jeudi":"Jeudi","vendredi":"Vendredi","samedi":"Samedi","dimanche":"Dimanche"}

class User(UserMixin,db.Model):
    id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(150),unique=True,nullable=False,index=True); password=db.Column(db.String(255),nullable=False); role=db.Column(db.String(50),nullable=False); zone=db.Column(db.String(100),nullable=True); project=db.Column(db.String(50),nullable=False); is_active_account=db.Column(db.Boolean,default=True,nullable=False)
    def __repr__(self): return f"<User {self.username} ({self.role}/{self.project})>"

class Prospection(db.Model):
    id=db.Column(db.Integer,primary_key=True); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True); date=db.Column(db.Date,nullable=False,index=True); nom_client=db.Column(db.String(150),nullable=False); specialite=db.Column(db.String(150),nullable=False); structure=db.Column(db.String(150),nullable=False); telephone=db.Column(db.String(30),nullable=False); profils_prospect=db.Column(db.Text,nullable=True); produits_presentes=db.Column(db.Text,nullable=True); produits_prescrits=db.Column(db.Text,nullable=True); client_id=db.Column(db.Integer,db.ForeignKey("crm_client.id"),nullable=True,index=True); planning_id=db.Column(db.Integer,db.ForeignKey("planning.id"),nullable=True,index=True); planning_day=db.Column(db.String(20),nullable=True)
    commercial=db.relationship("User",backref=db.backref("prospections",lazy="dynamic")); client=db.relationship("Client",foreign_keys=[client_id]); planning=db.relationship("Planning",foreign_keys=[planning_id])

class Planning(db.Model):
    id=db.Column(db.Integer,primary_key=True); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True); date=db.Column(db.Date,nullable=False); lundi=db.Column(db.Text,nullable=True); mardi=db.Column(db.Text,nullable=True); mercredi=db.Column(db.Text,nullable=True); jeudi=db.Column(db.Text,nullable=True); vendredi=db.Column(db.Text,nullable=True); samedi=db.Column(db.Text,nullable=True); dimanche=db.Column(db.Text,nullable=True)
    commercial=db.relationship("User",backref=db.backref("plannings",lazy="dynamic")); prospections=db.relationship("Prospection",back_populates="planning")

class ProductMixin:
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(200),nullable=False); reference=db.Column(db.String(100),nullable=True); default_price=db.Column(db.Numeric(12,2),nullable=False,default=Decimal("0.00")); is_active=db.Column(db.Boolean,default=True,nullable=False); stock_duopharm=db.Column(db.Integer,default=0,nullable=False); stock_ubipharm=db.Column(db.Integer,default=0,nullable=False); stock_laborex=db.Column(db.Integer,default=0,nullable=False); stock_sodipharm=db.Column(db.Integer,default=0,nullable=False)
class SaleMixin:
    id=db.Column(db.Integer,primary_key=True); quantity=db.Column(db.Integer,nullable=False); price=db.Column(db.Numeric(12,2),nullable=False); date=db.Column(db.Date,nullable=False,index=True); project=db.Column(db.String(50),nullable=False)
class NovaPharmaProduct(ProductMixin,db.Model): __tablename__="nova_pharma_product"
class GilbertProduct(ProductMixin,db.Model): __tablename__="gilbert_product"
class EricFavreProduct(ProductMixin,db.Model): __tablename__="eric_favre_product"
class TroisCheneProduct(ProductMixin,db.Model): __tablename__="trois_chene_product"
class NovaPharmaSale(SaleMixin,db.Model):
    __tablename__="nova_pharma_sale"; product_id=db.Column(db.Integer,db.ForeignKey("nova_pharma_product.id"),nullable=False); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False); product=db.relationship("NovaPharmaProduct"); commercial=db.relationship("User")
class GilbertSale(SaleMixin,db.Model):
    __tablename__="gilbert_sale"; product_id=db.Column(db.Integer,db.ForeignKey("gilbert_product.id"),nullable=False); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False); product=db.relationship("GilbertProduct"); commercial=db.relationship("User")
class EricFavreSale(SaleMixin,db.Model):
    __tablename__="eric_favre_sale"; product_id=db.Column(db.Integer,db.ForeignKey("eric_favre_product.id"),nullable=False); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False); product=db.relationship("EricFavreProduct"); commercial=db.relationship("User")
class TroisCheneSale(SaleMixin,db.Model):
    __tablename__="trois_chene_sale"; product_id=db.Column(db.Integer,db.ForeignKey("trois_chene_product.id"),nullable=False); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False); product=db.relationship("TroisCheneProduct"); commercial=db.relationship("User")
SUPPLIERS={"nova_pharma":{"label":"Nova Pharma","division":"nasderm","product_model":NovaPharmaProduct,"sale_model":NovaPharmaSale,"archived":True},"gilbert":{"label":"Gilbert","division":"nasderm","product_model":GilbertProduct,"sale_model":GilbertSale,"archived":False},"eric_favre":{"label":"Eric Favre","division":"nasmedic","product_model":EricFavreProduct,"sale_model":EricFavreSale,"archived":False},"trois_chene":{"label":"3 Chênes Pharma","division":"nasmedic","product_model":TroisCheneProduct,"sale_model":TroisCheneSale,"archived":False}}
DIVISION_SUPPLIERS={"nasderm":[slug for slug,s in SUPPLIERS.items() if s["division"]=="nasderm" and not s["archived"]],"nasmedic":[slug for slug,s in SUPPLIERS.items() if s["division"]=="nasmedic" and not s["archived"]]}
class SalesObjective(db.Model):
    __tablename__="sales_objective"; id=db.Column(db.Integer,primary_key=True); division=db.Column(db.String(50),nullable=False); year=db.Column(db.Integer,nullable=False); month=db.Column(db.Integer,nullable=True); target_amount=db.Column(db.Numeric(12,2),nullable=False,default=Decimal("0.00")); __table_args__=(db.UniqueConstraint("division","year","month",name="uq_objective_division_year_month"),)
def get_active_products_for_division(division):
    names=set()
    for slug in DIVISION_SUPPLIERS.get(division,[]):
        model=SUPPLIERS[slug]["product_model"]
        for (name,) in model.query.filter_by(is_active=True).with_entities(model.name).all(): names.add(name)
    return sorted(names)
EVALUATION_SECTIONS=[("1. Performance commerciale & objectifs",40,[("score_ca","Atteinte de l'objectif de Chiffre d'Affaires (CA)",20,["< 60%","60-75%","75-90%","> 90%"]),("score_gamme_asthe","Gamme stratégique — Asthe 1000",2,["0 pt","0.5 pt","1 pt","2 pts"]),("score_gamme_myocalm","Gamme stratégique — Myocalm",2,["0 pt","0.5 pt","1 pt","2 pts"]),("score_gamme_bumbum","Gamme stratégique — Bum Bum",1,["0 pt","0.25 pt","0.5 pt","1 pt"]),("score_gamme_flatupklexin","Gamme stratégique — Flatupklexin",2,["0 pt","0.5 pt","1 pt","2 pts"]),("score_gamme_somniplex","Gamme stratégique — Somniplex",1,["0 pt","0.25 pt","0.5 pt","1 pt"]),("score_gamme_ostheophytum","Gamme stratégique — Ostheophytum",1,["0 pt","0.25 pt","0.5 pt","1 pt"]),("score_gamme_specialkid","Gamme stratégique — Spécial Kid",1,["0 pt","0.25 pt","0.5 pt","1 pt"]),("score_reporting","Qualité des visites & reporting",10,["< 50%","50-70%","70-85%","> 85%"])],),("2. Qualité des visites et exécution terrain",35,[("score_plan_visite","Respect du plan de visite & ciblage",10,["Irrégulier","Partiel","Bon","Parfait"]),("score_argumentaire","Qualité de l'argumentaire scientifique",10,["Faible","Moyen","Maîtrisé","Persuasif"]),("score_prescriptions","Capacité à générer des prescriptions",10,["Faible","Moyen","Fort","Excellent"]),("score_organisation","Organisation, discipline & gestion matériel",5,["À revoir","Acceptable","Soigné","Irréprochable"])],),("3. Comportement professionnel",25,[("score_ponctualite","Ponctualité, assiduité et présence",10,["> 3 retards","1-2 retards","Régulier","Exemplaire"]),("score_consignes","Respect des consignes & directives",10,["Non-respect","Partiel","Conforme","Exemplaire"]),("score_esprit_equipe","Esprit d'équipe, proactivité & attitude",5,["Passif","Correct","Actif","Moteur"])],)]
EVALUATION_FIELDS=[item for _,_,items in EVALUATION_SECTIONS for item in items]; EVALUATION_MAX_TOTAL=sum(max_pts for _,_,max_pts,_ in EVALUATION_FIELDS)
class Evaluation(db.Model):
    id=db.Column(db.Integer,primary_key=True); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True); evaluator_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=True); year=db.Column(db.Integer,nullable=False); month=db.Column(db.Integer,nullable=False); score_ca=db.Column(db.Float,nullable=False,default=0); score_gamme_asthe=db.Column(db.Float,nullable=False,default=0); score_gamme_myocalm=db.Column(db.Float,nullable=False,default=0); score_gamme_bumbum=db.Column(db.Float,nullable=False,default=0); score_gamme_flatupklexin=db.Column(db.Float,nullable=False,default=0); score_gamme_somniplex=db.Column(db.Float,nullable=False,default=0); score_gamme_ostheophytum=db.Column(db.Float,nullable=False,default=0); score_gamme_specialkid=db.Column(db.Float,nullable=False,default=0); score_reporting=db.Column(db.Float,nullable=False,default=0); score_plan_visite=db.Column(db.Float,nullable=False,default=0); score_argumentaire=db.Column(db.Float,nullable=False,default=0); score_prescriptions=db.Column(db.Float,nullable=False,default=0); score_organisation=db.Column(db.Float,nullable=False,default=0); score_ponctualite=db.Column(db.Float,nullable=False,default=0); score_consignes=db.Column(db.Float,nullable=False,default=0); score_esprit_equipe=db.Column(db.Float,nullable=False,default=0); points_forts=db.Column(db.Text,nullable=True); axes_amelioration=db.Column(db.Text,nullable=True); objectifs_quantitatifs=db.Column(db.Text,nullable=True); objectifs_qualitatifs=db.Column(db.Text,nullable=True); created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False); updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,nullable=False)
    commercial=db.relationship("User",foreign_keys=[commercial_id]); evaluator=db.relationship("User",foreign_keys=[evaluator_id]); __table_args__=(db.UniqueConstraint("commercial_id","year","month",name="uq_evaluation_commercial_year_month"),)
    @property
    def total_score(self): return sum(getattr(self,field_name) or 0 for field_name,*_ in EVALUATION_FIELDS)
    @property
    def niveau(self):
        total=self.total_score
        if total>=90:return "Excellent"
        if total>=75:return "Bon"
        if total>=60:return "Moyen"
        return "Insuffisant"
