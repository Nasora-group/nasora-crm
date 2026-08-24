import logging,re,unicodedata
from datetime import timedelta
from flask import Blueprint,render_template,redirect,url_for,flash,request,jsonify
from flask_login import login_required,current_user
from app.extensions import db
from app.forms import ProspectionForm,CSRFOnlyForm
from app.models import Prospection,Planning,get_active_products_for_division,STRUCTURES
from app.models_clients import Client,ClientVisit
from app.utils import roles_required,decode_planning_slot
from app.routes.revenue import _monthly_revenue_for_division,_objectives_kpis
logger=logging.getLogger(__name__);dashboard_bp=Blueprint("dashboard",__name__)
def _parse_products(raw):return [p.strip() for p in (raw or "").split(",") if p.strip()]
def _set_product_choices(form,division,existing_values=None):
 active=get_active_products_for_division(division);choices=[(n,n) for n in active]
 if existing_values:
  aset=set(active)
  for v in existing_values:
   if v and v not in aset:choices.append((v,f"{v} (non disponible)"));aset.add(v)
 form.produits_presentes.choices=choices;form.produits_prescrits.choices=choices
def _planning_for_date(visit_date):
 if not visit_date:return None
 ps=Planning.query.filter_by(commercial_id=current_user.id).filter(Planning.date<=visit_date).order_by(Planning.date.desc()).all()
 return next((p for p in ps if p.date<=visit_date<=p.date+timedelta(days=6)),None)
def _planning_structures_for_date(visit_date):
 p=_planning_for_date(visit_date)
 if not p:return []
 jour={"Monday":"lundi","Tuesday":"mardi","Wednesday":"mercredi","Thursday":"jeudi","Friday":"vendredi","Saturday":"samedi","Sunday":"dimanche"}.get(visit_date.strftime("%A"),"")
 return decode_planning_slot(getattr(p,jour,None)) if jour else []
def _set_prospection_choices(form,visit_date=None,existing_client_id=None):
 planned=_planning_structures_for_date(visit_date);types=[];est=[]
 for typ,name in planned:
  if typ and typ not in types:types.append(typ)
  if name and name not in est:est.append(name)
 form.structure.choices=[(v,v) for v in (types or [v for v,_ in STRUCTURES])]
 form.establishment.choices=[(v,v) for v in (est or ["Hors planning / nouvel établissement"])]
 clients=Client.query.filter_by(owner_id=current_user.id).order_by(Client.name.asc()).all();choices=[(0,"— Nouveau prospect —")]
 choices.extend((c.id,f"{c.name} — {c.establishment or c.structure}") for c in clients)
 if existing_client_id and existing_client_id not in [c.id for c in clients]:
  c=Client.query.get(existing_client_id)
  if c:choices.append((c.id,f"{c.name} — {c.establishment or c.structure}"))
 form.prospect_id.choices=choices
 return planned,clients
def _normalize_text(v):
 v=unicodedata.normalize("NFKD",v or "").encode("ascii","ignore").decode("ascii");v=re.sub(r"[^a-z0-9]+"," ",v.lower()).strip();return re.sub(r"\s+"," ",v)
def _normalize_phone(v):return re.sub(r"\D","",v or "")
def _invalid_phone(v):return (v or "").strip().lower() in {"","na","n/a","nc","non renseigne","non renseigné","0"} or len(_normalize_phone(v))<6
def _find_client_for_prospection(p):
 phone=(p.telephone or "").strip();name=(p.nom_client or "").strip();np=_normalize_phone(phone);nn=_normalize_text(name)
 if np and not _invalid_phone(phone):
  for c in Client.query.filter(Client.phone.isnot(None)).all():
   if _normalize_phone(c.phone)==np:return c
 same=[c for c in Client.query.filter(Client.name.isnot(None)).all() if _normalize_text(c.name)==nn]
 owned=[c for c in same if c.owner_id==p.commercial_id]
 return sorted(owned,key=lambda c:c.id)[0] if owned else (same[0] if len(same)==1 else None)
def _sync_professional_from_prospection(p):
 c=_find_client_for_prospection(p);valid=not _invalid_phone(p.telephone)
 if c is None:
  c=Client(name=p.nom_client.strip(),specialty=p.specialite.strip() or None,structure=p.structure.strip(),establishment=p.establishment.strip() or None,phone=p.telephone.strip() if valid else None,potential=3,owner_id=p.commercial_id,last_visit=p.date);db.session.add(c);db.session.flush()
 else:
  c.specialty=p.specialite.strip() or c.specialty;c.structure=p.structure.strip() or c.structure;c.establishment=p.establishment.strip() or c.establishment
  if valid:c.phone=p.telephone.strip()
  if c.owner_id is None:c.owner_id=p.commercial_id
  if not c.last_visit or p.date>c.last_visit:c.last_visit=p.date
 pp=p.produits_presentes or None;pr=p.produits_prescrits or None;report=p.profils_prospect or None
 if not ClientVisit.query.filter_by(client_id=c.id,commercial_id=p.commercial_id,date=p.date,products_presented=pp,products_prescribed=pr,report=report,is_duplicate=False).first():db.session.add(ClientVisit(client_id=c.id,commercial_id=p.commercial_id,date=p.date,products_presented=pp,products_prescribed=pr,report=report))
 return c
def _render_dashboard(form,planned=None,clients=None):
 labels,totals,_=_monthly_revenue_for_division(current_user.project);sales_kpis=_objectives_kpis(current_user.project,labels,totals)
 planned=planned if planned is not None else _planning_structures_for_date(form.date.data);clients=clients if clients is not None else Client.query.filter_by(owner_id=current_user.id).order_by(Client.name.asc()).all()
 prospect_data={str(c.id):{"name":c.name,"phone":c.phone or "","specialty":c.specialty or "","structure":c.structure or "","establishment":c.establishment or ""} for c in clients}
 return render_template("dashboard.html",form=form,sales_kpis=sales_kpis,planned_structures=planned,prospect_data=prospect_data)
def _prospection_planning_status(p):
 planned=_planning_structures_for_date(p.date);planned_names={n for _t,n in planned if n};return ("Planifiée" if p.establishment and p.establishment in planned_names else "Ajoutée hors planning"),planned
@dashboard_bp.route("/dashboard",methods=["GET","POST"])
@login_required
@roles_required("commercial")
def index():
 form=ProspectionForm();planned,clients=_set_prospection_choices(form,form.date.data);_set_product_choices(form,current_user.project)
 if form.is_submitted():
  planned,clients=_set_prospection_choices(form,form.date.data,form.prospect_id.data);_set_product_choices(form,current_user.project)
  if not form.validate():flash("Veuillez corriger les champs indiqués.","error");return _render_dashboard(form,planned,clients)
  try:
   c=Client.query.filter_by(id=form.prospect_id.data,owner_id=current_user.id).first() if form.prospect_id.data else None
   if c:form.nom_client.data=c.name;form.telephone.data=c.phone or form.telephone.data;form.specialite.data=c.specialty or form.specialite.data;form.structure.data=c.structure or form.structure.data;form.establishment.data=c.establishment or form.establishment.data
   planned_names={n for _t,n in planned if n}
   if planned and form.establishment.data not in planned_names and form.establishment.data!="Hors planning / nouvel établissement":flash("Choisissez un établissement du planning pour cette date.","error");return _render_dashboard(form,planned,clients)
   p=Prospection(commercial_id=current_user.id,date=form.date.data,nom_client=form.nom_client.data.strip(),specialite=form.specialite.data.strip(),structure=form.structure.data.strip(),establishment=form.establishment.data.strip(),telephone=form.telephone.data.strip(),profils_prospect=(form.profils_prospect.data or "").strip(),produits_presentes=", ".join(form.produits_presentes.data or []),produits_prescrits=", ".join(form.produits_prescrits.data or []),planning_id=_planning_for_date(form.date.data).id if _planning_for_date(form.date.data) and form.establishment.data in planned_names else None,planning_day=form.date.data.strftime("%A").lower());db.session.add(p);db.session.flush();_sync_professional_from_prospection(p);db.session.commit();flash("Prospection enregistrée avec succès.","success");return redirect(url_for("dashboard.index"))
  except Exception:db.session.rollback();logger.exception("Erreur lors de l'enregistrement d'une prospection");flash("Impossible d'enregistrer la prospection. Vérifiez les données et réessayez.","error");return _render_dashboard(form,planned,clients)
 return _render_dashboard(form,planned,clients)
@dashboard_bp.route("/dashboard/prospections",methods=["GET"])
@login_required
@roles_required("commercial")
def prospections():
 rows=Prospection.query.filter_by(commercial_id=current_user.id).order_by(Prospection.date.desc(),Prospection.id.desc()).all();statuses={p.id:_prospection_planning_status(p)[0] for p in rows};return render_template("dashboard_prospections.html",prospections=rows,planning_statuses=statuses)
@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/modifier",methods=["GET","POST"])
@login_required
@roles_required("commercial")
def edit_prospection(prospection_id):
 p=Prospection.query.get_or_404(prospection_id)
 if p.commercial_id!=current_user.id:return render_template("403.html"),403
 ep=_parse_products(p.produits_presentes);er=_parse_products(p.produits_prescrits);form=ProspectionForm(obj=p);planned,clients=_set_prospection_choices(form,p.date);_set_product_choices(form,current_user.project,set(ep)|set(er))
 if not form.is_submitted():form.produits_presentes.data=ep;form.produits_prescrits.data=er
 if form.validate_on_submit():
  try:
   p.date=form.date.data;p.nom_client=form.nom_client.data.strip();p.specialite=form.specialite.data.strip();p.structure=form.structure.data.strip();p.establishment=form.establishment.data.strip();p.telephone=form.telephone.data.strip();p.profils_prospect=(form.profils_prospect.data or "").strip();p.produits_presentes=", ".join(form.produits_presentes.data or []);p.produits_prescrits=", ".join(form.produits_prescrits.data or []);p.planning_id=_planning_for_date(p.date).id if _planning_for_date(p.date) and p.establishment in {n for _t,n in _planning_structures_for_date(p.date) if n} else None;_sync_professional_from_prospection(p);db.session.commit();flash("Prospection mise à jour avec succès.","success");return redirect(url_for("dashboard.prospections"))
  except Exception:db.session.rollback();flash("Erreur lors de la mise à jour.","error")
 return render_template("edit_prospection.html",form=form,prospection=p,planned_structures=planned)
@dashboard_bp.route("/dashboard/prospection/<int:prospection_id>/supprimer",methods=["POST"])
@login_required
@roles_required("commercial")
def delete_prospection(prospection_id):
 form=CSRFOnlyForm();p=Prospection.query.get_or_404(prospection_id)
 if p.commercial_id!=current_user.id:return redirect(url_for("dashboard.prospections"))
 if form.validate_on_submit():
  try:
   c=_find_client_for_prospection(p)
   if c:
    v=ClientVisit.query.filter_by(client_id=c.id,commercial_id=p.commercial_id,date=p.date).order_by(ClientVisit.id.desc()).first()
    if v:db.session.delete(v)
    if ClientVisit.query.filter_by(client_id=c.id).count()==0:db.session.delete(c)
   db.session.delete(p);db.session.commit();flash("Prospection supprimée avec succès.","success")
  except Exception:db.session.rollback();flash("Impossible de supprimer la prospection.","error")
 return redirect(url_for("dashboard.prospections"))