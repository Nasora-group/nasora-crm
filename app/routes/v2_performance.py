from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models import User, SalesObjective, DIVISION_SUPPLIERS, SUPPLIERS, Prospection, AnimationSale
from app.models_clients import ClientVisit
from app.utils import roles_required

v2_performance_bp = Blueprint("v2_performance", __name__, url_prefix="/v2/performance")

MONTHS={1:"Janvier",2:"Février",3:"Mars",4:"Avril",5:"Mai",6:"Juin",7:"Juillet",8:"Août",9:"Septembre",10:"Octobre",11:"Novembre",12:"Décembre"}

def _period(year, month):
    start=date(year,month,1)
    end=date(year+1,1,1) if month==12 else date(year,month+1,1)
    return start,end

def _revenue(division, start, end):
    total=Decimal("0")
    for slug in DIVISION_SUPPLIERS.get(division,[]):
        model=SUPPLIERS[slug]["sale_model"]
        total += Decimal(str(db.session.query(func.coalesce(func.sum(model.quantity*model.price),0)).filter(model.date>=start,model.date<end,model.project==division).scalar() or 0))
    return total

def _team_row(user, division, start, end):
    pros=Prospection.query.filter(Prospection.commercial_id==user.id,Prospection.date>=start,Prospection.date<end).count()
    visits=ClientVisit.query.filter(ClientVisit.commercial_id==user.id,ClientVisit.date>=start,ClientVisit.date<end,ClientVisit.is_duplicate.is_(False)).count()
    animations=AnimationSale.query.filter(AnimationSale.animateur_id==user.id,AnimationSale.animation_date>=start,AnimationSale.animation_date<end,AnimationSale.project==division).all()
    animation_ca=sum((a.total_amount for a in animations),Decimal("0"))
    sales_ca=_revenue_for_user(user.id,division,start,end)
    return {"user":user,"prospections":pros,"visits":visits,"animation_lines":len(animations),"animation_ca":animation_ca,"sales_ca":sales_ca,"total_ca":sales_ca+animation_ca}

def _revenue_for_user(user_id, division, start, end):
    total=Decimal("0")
    for slug in DIVISION_SUPPLIERS.get(division,[]):
        model=SUPPLIERS[slug]["sale_model"]
        total += Decimal(str(db.session.query(func.coalesce(func.sum(model.quantity*model.price),0)).filter(model.commercial_id==user_id,model.date>=start,model.date<end,model.project==division).scalar() or 0))
    return total

@v2_performance_bp.route("")
@login_required
@roles_required("admin")
def index():
    today=date.today()
    year=request.args.get("year",today.year,type=int)
    month=request.args.get("month",today.month,type=int)
    if month<1 or month>12: month=today.month
    division=(request.args.get("division") or "all").lower()
    start,end=_period(year,month)
    divisions=list(DIVISION_SUPPLIERS) if division=="all" else [division] if division in DIVISION_SUPPLIERS else list(DIVISION_SUPPLIERS)
    division_rows=[]
    for div in divisions:
        target=SalesObjective.query.filter_by(division=div,year=year,month=month).first()
        target_amount=Decimal(str(target.target_amount)) if target else Decimal("0")
        ca=_revenue(div,start,end)
        rate=(ca/target_amount*100) if target_amount else None
        division_rows.append({"division":div,"target":target_amount,"ca":ca,"rate":rate})
    users=User.query.filter(User.role.in_(["commercial","animateur"]),User.project.in_(divisions),User.is_active_account.is_(True)).order_by(User.project,User.username).all()
    team=[_team_row(u,u.project,start,end) for u in users]
    total_target=sum((x["target"] for x in division_rows),Decimal("0"))
    total_ca=sum((x["ca"] for x in division_rows),Decimal("0"))
    total_animation_ca=sum((x["animation_ca"] for x in team),Decimal("0"))
    return render_template("v2/performance.html",year=year,month=month,month_label=MONTHS[month],division=division,division_rows=division_rows,team=team,total_target=total_target,total_ca=total_ca,total_animation_ca=total_animation_ca,total_rate=(total_ca/total_target*100 if total_target else None))

@v2_performance_bp.route("/objectifs")
@login_required
@roles_required("admin")
def objectives():
    year=request.args.get("year",date.today().year,type=int)
    rows=[]
    for div in DIVISION_SUPPLIERS:
        annual=SalesObjective.query.filter_by(division=div,year=year,month=None).first()
        months=[SalesObjective.query.filter_by(division=div,year=year,month=m).first() for m in range(1,13)]
        rows.append({"division":div,"annual":annual.target_amount if annual else 0,"months":[m.target_amount if m else 0 for m in months]})
    return render_template("v2/performance_objectives.html",year=year,rows=rows,months=MONTHS)
