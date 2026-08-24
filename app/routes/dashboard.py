import logging
import re
import unicodedata
from datetime import timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.forms import ProspectionForm, CSRFOnlyForm
from app.models import Prospection, Planning, get_active_products_for_division, STRUCTURES
from app.models_clients import Client, ClientVisit
from app.utils import roles_required, decode_planning_slot
from app.routes.revenue import _monthly_revenue_for_division, _objectives_kpis

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)

def _parse_products(raw): return [p.strip() for p in (raw or "").split(",") if p.strip()]
def _set_product_choices(form, division, existing_values=None):
    active_products=get_active_products_for_division(division); choices=[(name,name) for name in active_products]
    if existing_values:
        active_set=set(active_products)
        for value in existing_values:
            if value and value not in active_set: choices.append((value,f"{value} (non disponible)")); active_set.add(value)
    form.produits_presentes.choices=choices; form.produits_prescrits.choices=choices

def _planning_structures_for_date(visit_date):
    if not visit_date:return []
    plannings=Planning.query.filter_by(commercial_id=current_user.id).filter(Planning.date<=visit_date).order_by(Planning.date.desc()).all()
    planning=next((p for p in plannings if p.date<=visit_date<=p.date+timedelta(days=6)),None)
    if planning is None:return []
    jour={"Monday":"lundi","Tuesday":"mardi","Wednesday":"mercredi","Thursday":"jeudi","Friday":"vendredi","Saturday":"samedi","Sunday":"dimanche"}.get(visit_date.strftime("%A"),"")
    return decode_planning_slot(getattr(planning,jour,None)) if jour else []

def _set_prospection_choices(form,visit_date=None,existing_client_id=None):
    structures=_planning_structures_for_date(visit_date); planned_types=[]
    for structure_type,_name in structures:
        if structure_type and structure_type not in planned_types:planned_types.append(structure_type)
    form.structure.choices=[(v,v) for v in (planned_types or [value for value,_label in STRUCTURES])]
    clients=Client.query.filter_by(owner_id=current_user.id).order_by(Client.name.asc()).all(); choices=[(0,"— Nouveau prospect —")]; choices.extend((c.id,f"{c.name} — {c.structure}") for c in clients)
    if existing_client_id and existing_client_id not in [c.id for c in clients]:
        c=Client.query.get(existing_client_id)
        if c:choices.append((c.id,f"{c.name} — {c.structure}"))
    form.prospect_id.choices=choices
    return structures,clients

def _normalize_text(value):
    value=unicodedata.normalize("NFKD",value or "").encode("ascii","ignore").decode("ascii");value=re.sub(r"[^a-z0-9]+"," ",value.lower()).strip();return re.sub(r"\s+"," ",value)
def _normalize_phone(value):return re.sub(r"\D","",value or "")
def _invalid_phone(value):
    raw=(value or "").strip().lower();return raw in {"","na","n/a","nc","non renseigne","non renseigné","0"} or len(_normalize_phone(raw))<6

def _find_client_for_prospection(prospection):
    phone=(prospection.telephone or "").strip();name=(prospection.nom_client or "").strip();normalized_phone=_normalize_phone(phone);normalized_name=_normalize_text(name)
    if normalized_phone and not _invalid_phone(phone):
        for client in Client.query.filter(Client.phone.isnot(None)).all():
            if _normalize_phone(client.phone)==normalized_phone:return client
    if not normalized_name:return None
    same_name=[c for c in Client.query.filter(Client.name.isnot(None)).all() if _normalize_text(c.name)==normalized_name];owned=[c for c in same_name if c.owner_id==current_user.id]
    if owned:return sorted(owned,key=lambda c:c.id)[0]
    if len(same_name)==1:return same_name[0]
    visited=[c for c in same_name if ClientVisit.query.filter_by(client_id=c.id,commercial_id=current_user.id).first() is not None]
    return sorted(visited,key=lambda c:c.id)[0] if visited else None

def _sync_professional_from_prospection(prospection):
    phone=(prospection.telephone or "").strip();client=_find_client_for_prospection(prospection);valid_phone=not _invalid_phone(phone)
    if client is None:
        client=Client(name=(prospection.nom_client or "").strip(),specialty=(prospection.specialite or "").strip() or None,structure=(prospection.structure or "").strip(),phone=phone if valid_phone else None,potential=3,owner_id=current_user.id,last_visit=prospection.date);db.session.add(client);db.session.flush()
    else:
        client.specialty=(prospection.specialite or "").strip() or client.specialty;client.structure=(prospection.structure or "").strip() or client.structure
        if valid_phone:client.phone=phone
        if client.owner_id is None:client.owner_id=current_user.id
        if not client.last_visit or prospection.date>client.last_visit:client.last_visit=prospection.date
    pp=prospection.produits_presentes or None;pr=prospection.produits_prescrits or None;report=prospection.profils_prospect or None
    visit=ClientVisit.query.filter_by(client_id=client.id,commercial_id=current_user.id,date=prospection.date,products_presented=pp,products_prescribed=pr,report=report,is_duplicate=False).order_by(ClientVisit.id.desc()).first()
    if visit is None:visit=ClientVisit(client_id=client.id,commercial_id=current_user.id,date=prospection.date,products_presented=pp,products_prescribed=pr,report=report);db.session.add(visit);db.session.flush()
    return client,visit

def _sync_professional_from_existing_prospection(prospection):
    client=_find_client_for_prospection(prospection);phone=(prospection.telephone or "").strip();valid_phone=not _invalid_phone(phone)
    if client is None:
        client=Client(name=(prospection.nom_client or "").strip(),specialty=(prospection.specialite or "").strip() or None,structure=(prospection.structure or "").strip(),phone=phone if valid_phone else None,potential=3,owner_id=prospection.commercial_id,last_visit=prospection.date);db.session.add(client);db.session.flush()
    else:
        if valid_phone:client.phone=phone
        if client.owner_id is None:client.owner_id=prospection.commercial_id
        if not client.last_visit or prospection.date>client.last_visit:client.last_visit=prospection.date
    if not ClientVisit.query.filter_by(client_id=client.id,commercial_id=prospection.commercial_id,date=prospection.date,products_presented=prospection.produits_presentes or None,products_prescribed=prospection.produits_prescrits or None,report=prospection.profils_prospect or None,is_duplicate=False).first():db.session.add(ClientVisit(client_id=client.id,commercial_id=prospection.commercial_id,date=prospection.date,products_presented=prospection.produits_presentes or None,products_prescribed=prospection.produits_prescrits or None,report=prospection.profils_prospect or None))

def _delete_linked_records_for_prospection(prospection):
    client=_find_client_for_prospection(prospection)
    if client is None:return None,False
    visit=ClientVisit.query.filter_by(client_id=client.id,commercial_id=prospection.commercial_id,date=prospection.date,products_presented=prospection.produits_presentes or None,products_prescribed=prospection.produits_prescrits or None,report=prospection.profils_prospect or None).order_by(ClientVisit.id.desc()).first() or ClientVisit.query.filter_by(client_id=client.id,commercial_id=prospection.commercial_id,date=prospection.date).order_by(ClientVisit.id.desc()).first()
    if visit is not None:db.session.delete(visit);db.session.flush()
    deleted=False
    if ClientVisit.query.filter_by(client_id=client.id).count()==0:db.session.delete(client);db.session.flush();deleted=True
    return client.id,deleted

def _render_dashboard(form,planned_structures=None,clients=None):
    labels,totals,_=_monthly_revenue_for_division(current_user.project);sales_kpis=_objectives_kpis(current_user.project,labels,totals)
    if planned_structures is None:planned_structures=_planning_structures_for_date(form.date.data)
    if clients is None:clients=Client.query.filter_by(owner_id=current_user.id).order_by(Client.name.asc()).all()
    prospect_data={str(c.id):{"name":c.name,"phone":c.phone or "","specialty":c.specialty or "","structure":c.structure or ""} for c in clients}
    return render_template("dashboard.html",form=form,sales_kpis=sales_kpis,planned_structures=planned_structures,prospect_data=prospect_data)

def _prospection_planning_status(prospection):
    planned=_planning_structures_for_date(prospection.date)
    planned_types={structure_type for structure_type,_name in planned}
    return ("Planifiée" if prospection.structure in planned_types else "Ajoutée hors planning"),planned

@dashboard_bp.route("/dashboard",methods=["GET","POST"])
@login_required
@roles_required("commercial")
def index():
    form=ProspectionForm();planned_structures,clients=_set_prospection_choices(form,form.date.data);_set_product_choices(form,current_user.project)
    if form.is_submitted():
        planned_structures,clients=_set_prospection_choices(form,form.date.data,form.prospect_id.data);_set_product_choices(form,current_user.project)
        if not form.validate():flash("Veuillez corriger les champs indiqués.","error");return _render_dashboard(form,planned_structures,clients)
        try:
            client=Client.query.filter_by(id=form.prospect_id.data,owner_id=current_user.id).first() if form.prospect_id.data else None
            if client:form.nom_client.data=client.name;form.telephone.data=client.phone or form.telephone.data;form.specialite.data=client.specialty or form.specialite.data
            if form.structure.data not in {v for v,_l in form.structure.choices}:flash("Cette structure n'est pas disponible pour cette date.","error");return _render_dashboard(form,planned_structures,clients)
            prospection=Prospection(commercial_id=current_user.id,date=form.date.data,nom_client=form.nom_client.data.strip(),specialite=form.specialite.data.strip(),structure=form.structure.data.strip(),telephone=form.telephone.data.strip(),profils_prospect=(form.profils_prospect.data or "").strip(),produits_presentes=", ".join(form.produits_presentes.data or []),produits_prescrits=", ".join(form.produits_prescrits.data or []));db.session.add(prospection);db.session.flush();_sync_professional_from_prospection(prospection);db.session.commit();flash("Prospection enregistrée avec succès.","success");return redirect(url_for("dashboard.index"))
        except Exception:db.session.rollback();logger.exception("Erreur lors de l'enregistrement d'une prospection");flash("Impossible d'enregistrer la prospection. Vérifiez les données et réessayez.","error");return _render_dashboard(form,planned_structures,clients)
    return _render_dashboard(form,planned_structures,clients)

@dashboard_bp.route("/dashboard/prospections",methods=["GET"])
@login_required
@roles_required("commercial")
def prospections():
    rows=Prospection.query.filter_by(commercial_id=current_user.id).order_by(Prospection.date.desc(),Prospection.id.desc()).all();statuses={}
    for p in rows:statuses[p.id]=_prospection_planning_status(p)[0]
    return render_template("dashboard_prospections.html",prospections=rows,planning_statuses=statuses)

@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/modifier",methods=["GET","POST"])
@login_required
@roles_required("commercial")
def edit_prospection(prospection_id):
    prospection=Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id!=current_user.id:flash("Accès non autorisé : cette prospection ne t'appartient pas.","error");return render_template("403.html"),403
    existing_presentes=_parse_products(prospection.produits_presentes);existing_prescrits=_parse_products(prospection.produits_prescrits);form=ProspectionForm(obj=prospection);planned_structures,clients=_set_prospection_choices(form,prospection.date);_set_product_choices(form,current_user.project,existing_values=set(existing_presentes)|set(existing_prescrits))
    if not form.is_submitted():form.produits_presentes.data=existing_presentes;form.produits_prescrits.data=existing_prescrits
    if form.validate_on_submit():
        try:
            prospection.date=form.date.data;prospection.nom_client=form.nom_client.data.strip();prospection.specialite=form.specialite.data.strip();prospection.structure=form.structure.data.strip();prospection.telephone=form.telephone.data.strip();prospection.profils_prospect=(form.profils_prospect.data or "").strip();prospection.produits_presentes=", ".join(form.produits_presentes.data or []);prospection.produits_prescrits=", ".join(form.produits_prescrits.data or []);_sync_professional_from_existing_prospection(prospection);db.session.commit();flash("Prospection mise à jour avec succès.","success");return redirect(url_for("dashboard.prospections"))
        except Exception:db.session.rollback();logger.exception("Erreur lors de la modification de la prospection #%s",prospection_id);flash("Erreur lors de la mise à jour.","error")
    return render_template("edit_prospection.html",form=form,prospection=prospection,planned_structures=planned_structures)

@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/supprimer",methods=["POST"])
@login_required
@roles_required("commercial")
def delete_prospection(prospection_id):
    form=CSRFOnlyForm();prospection=Prospection.query.get_or_404(prospection_id)
    if prospection.commercial_id!=current_user.id:flash("Accès non autorisé : cette prospection ne t'appartient pas.","error");return redirect(url_for("dashboard.prospections"))
    if form.validate_on_submit():
        try:_delete_linked_records_for_prospection(prospection);db.session.delete(prospection);db.session.commit();flash("Prospection supprimée avec succès.","success")
        except Exception:db.session.rollback();logger.exception("Erreur lors de la suppression de la prospection #%s",prospection_id);flash("Impossible de supprimer la prospection. Aucun changement n'a été appliqué.","error")
    return redirect(url_for("dashboard.prospections"))
