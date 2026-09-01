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
    id=db.Column(db.Integer,primary_key=True); commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True); date=db.Column(db.Date,nullable=False,index=True); nom_client=db.Column(db.String(150),nullable=False); specialite=db.Column(db.String(150),nullable=False); structure=db.Column(db.String(150),nullable=False); telephone=db.Column(db.String(30),nullable=False); profils_prospect=db.Column(db.Text,nullable=True); produits_presentes=db.Column(db.Text,nullable=True); produits_prescrits=db.Column(db.Text,nullable=True)
    establishment=db.Column(db.String(200),nullable=True,index=True)
    client_id=db.Column(db.Integer,db.ForeignKey("crm_client.id",name="fk_prospection_client"),nullable=True,index=True)
    planning_id=db.Column(db.Integer,db.ForeignKey("planning.id",name="fk_prospection_planning"),nullable=True,index=True)

class VisitObjective(db.Model):
    __tablename__="visit_objective"
    id=db.Column(db.Integer,primary_key=True)
    commercial_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True,unique=True)
    target_visits=db.Column(db.Integer,nullable=False,default=10)
    commercial=db.relationship("User",backref=db.backref("visit_objective",uselist=False))
