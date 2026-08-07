"""
Script de seed : crée les comptes utilisateurs et le catalogue produit initial.

Ce script est SANS DANGER à relancer plusieurs fois (idempotent) : il ne
recrée jamais un compte ou un produit qui existe déjà. C'est pourquoi il est
appelé automatiquement à chaque déploiement (voir Procfile, phase "release").

Les mots de passe des commerciaux ne sont pas codés en dur : ils sont soit
lus depuis les variables d'environnement, soit générés aléatoirement puis :
  1) écrits dans instance/seed_credentials.txt (accessible via le Shell Render)
  2) ET affichés directement dans les LOGS de déploiement (onglet "Logs" sur
     Render), pour rester accessibles même sans les Shell.

IMPORTANT : ces identifiants ne sont affichés/écrits qu'UNE SEULE FOIS, lors
de la création des comptes. Les déploiements suivants ne les réafficheront
pas (les comptes existent déjà). Copie-les dès la première fois.
"""
import os
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    User, NovaPharmaProduct, GilbertProduct, EricFavreProduct, TroisCheneProduct,
)

app = create_app()

CREDENTIALS_FILE = os.path.join(app.instance_path, "seed_credentials.txt")


def _generate_password():
    return secrets.token_urlsafe(9)


def create_initial_users(credentials_log):
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD") or _generate_password()
    if not User.query.filter_by(username="Anna Diallo").first():
        db.session.add(User(
            username="Anna Diallo",
            password=generate_password_hash(admin_password, method="pbkdf2:sha256"),
            role="admin", zone=None, project="nasmedic",
        ))
        credentials_log.append(("Anna Diallo (admin)", admin_password))

    default_password = os.environ.get("SEED_DEFAULT_COMMERCIAL_PASSWORD")

    commerciaux_nasmedic = [
        ("KHALIFA DIOP", "CENTRE VILLE", "nasmedic"),
        ("AMADOU DEME", "Banlieue 1", "nasmedic"),
        ("MBAYE NDOYE", "THIES", "nasmedic"),
        ("MEDINA K NDIAYE", "ZONES INTERMEDIAIRE 2", "nasmedic"),
        ("MARIE LOUISE", "MBOUR", "nasmedic"),
        ("FATOU COLLETTE DRAME", "ZONES INTERMEDIAIRE 1", "nasmedic"),
        ("MASSAMBA MBAYE", "Banlieue 2", "nasmedic"),
        ("LAMINE THIOUB", "REGION DE DIOURBEL", "nasmedic"),
    ]
    commerciaux_nasderm = [
        ("FAMA DIOP", "CENTRE VILLE", "nasderm"),
        ("MARIE JEANNE DIOUF", "Banlieue 1", "nasderm"),
        ("ASTOU MANA MBENGUE", "THIES", "nasderm"),
        ("HONORINE", "ZONES INTERMEDIAIRE 2", "nasderm"),
        ("MIJO", "MBOUR", "nasderm"),
        ("HELENE FAYE", "ZONES INTERMEDIAIRE 1", "nasderm"),
        ("ADJARA CISSÉ", "Banlieue 2", "nasderm"),
        ("KHAR FALL", "REGION DE DIOURBEL", "nasderm"),
        ("KHADY SOW", "REGION DE DIOURBEL", "nasderm"),
    ]

    for username, zone, project in commerciaux_nasmedic + commerciaux_nasderm:
        if User.query.filter_by(username=username).first():
            continue
        password = default_password or _generate_password()
        db.session.add(User(
            username=username,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
            role="commercial", zone=zone, project=project,
        ))
        credentials_log.append((username, password))

    db.session.commit()


def create_initial_products():
    nova_pharma_products = [
        ("HYFAC GEL NETTOYANT FLC 150ML", 3.5), ("HYFAC GEL NETTOYANT TB 300ML", 3.5),
        ("HYFAC PAIN NETTOYANT 100G SOUS ETUI", 3.5), ("HYFAC MOUSSE NETTOYANTE FLC150ML", 3.5),
        ("HYFAC SOIN GLOBAL FLC40ML/ETUI", 3.5), ("HYFAC ETUI 2X15 PATCHS IMPERFECTIONS", 3.5),
        ("HYFAC MOUSSE A RASER SENSITIVE FLC150ML", 3.5), ("HYFAC SUN SPF 50+ INV TB 40ML SS ETUI", 3.5),
        ("CLARIFAC Soin anti-taches 40ML", 3.5), ("HYFAC WOMAN SOIN GLOBAL TB 40ML/ETUI", 3.5),
        ("HYFAC WOMAN LOTION VISAGE FL 200 ML", 3.5), ("HYFAC WOMAN ACTIVE MASK 15*5ML", 3.5),
        ("HYDRAFAC CREME HYDRA LEGERE TUBE40 ML", 3.5),
    ]
    for name, price in nova_pharma_products:
        if not NovaPharmaProduct.query.filter_by(name=name).first():
            db.session.add(NovaPharmaProduct(name=name, default_price=price))

    gilbert_products = [
        ("ELLE TEST BTE DE 1 TEST GROSSESSE", 3.5),
        ("MOUSTIDOSE SPRAY REPULSIF ZONE INFESTEES IR3535 +12M  100ML", 3.5),
        ("MOUSTIDOSE SPRAY REPULSIF ACTIF VÉGÉTAL +6M 100ML", 3.5),
        ("MOUSTIDOSE SPRAY REPULSIF ZONE TRES INFESTEES ICARIDINE  +24M 100ML", 3.5),
        ("MOUSTIDOSE CREME SOIN CALMANT  40ML", 3.5),
        ("WATERWIPES LINGETTES BD BB 4X60", 3.5), ("WATERWIPES LINGETTES BD BB X60", 3.5),
        ("WATERWIPES LINGETTES BD BB X28", 3.5),
        ("NEUTRADERM BAUME RELIPIDANT 400ML RELIPID +", 3.5),
        ("NEUTRADERM BAUME RELIPIDANT 200ML RELIPID +", 3.5),
        ("LAINO GEL CREME  HYDRATANTE ANTI OXYDANT 40ML REPACK", 3.5),
        ("LAINO CREME NOURRISSANTE ANTI OXYDANT 40ML REPACK", 3.5),
    ]
    for name, price in gilbert_products:
        if not GilbertProduct.query.filter_by(name=name).first():
            db.session.add(GilbertProduct(name=name, default_price=price))

    eric_favre_products = [
        ("Chronoerect", 3.58), ("Special Kid calcium", 2.65), ("Special Kid Fer", 2.65),
        ("Special kid immunite", 3.00), ("Special Kid multivit", 2.65),
        ("Special Kid nez et gorge", 2.65), ("Special kid nutri+", 2.65),
        ("Special kid probiotiques", 8.56), ("Special kid rehydratation", 2.65),
        ("Special kid sol spray nasal F/50ML", 2.65), ("Special Kid sommeil", 2.65),
        ("Special kid Soulage doux", 2.65), ("Special kid Zinc", 2.65),
        ("Time Sex Control", 6.90), ("Appetit Plus", 2.34),
    ]
    for name, price in eric_favre_products:
        if not EricFavreProduct.query.filter_by(name=name).first():
            db.session.add(EricFavreProduct(name=name, default_price=price))

    trois_chene_products = [
        ("ASTHE 1000", 6.05), ("BOIS BANDE", 3.45), ("CARBOLINE CPR B/30", 2.40),
        ("DIARILIUM ENFANT SOL BUV", 1.95), ("DIARILIUM SOL BV UNICADOSE", 2.64),
        ("DYSMECALM CPR B/15", 2.90), ("EASY MOM GROSSESSE GEL B/30", 3.70),
        ("EFIRUB CPR B/30", 3.50), ("EFIRUB PDRE SOL BUV SACH B/8", 3.45),
        ("FLATUPLEXIN", 4.80), ("MYOCALM", 3.55), ("OSTEOPHYTUM CP", 7.50),
        ("OSTEOPHYTUM GEL 100ML", 4.75), ("OSTEOPHYTUM PATCH/14", 2.55),
        ("SEDABUCCIL", 3.60), ("SOMNIPLEX MELATONINE CPR", 5.20),
        ("VAGALINE SPRAY BUCCAL F/25ML", 3.75), ("VAGALINE CPR B/15", 2.45),
        ("SPRAY NASAL", 3.75), ("MYOCALM ROLL ON 50ML", 4.20),
        ("MYOCALM SPRAY 100ML", 4.25), ("INFLAKIN/30", 8.95), ("INFLAKIN/10", 5.15),
    ]
    for name, price in trois_chene_products:
        if not TroisCheneProduct.query.filter_by(name=name).first():
            db.session.add(TroisCheneProduct(name=name, default_price=price))

    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        credentials_log = []
        create_initial_users(credentials_log)
        create_initial_products()

        if credentials_log:
            os.makedirs(app.instance_path, exist_ok=True)
            with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
                f.write("Identifiants générés au premier démarrage - à distribuer puis SUPPRIMER ce fichier.\n\n")
                for username, password in credentials_log:
                    f.write(f"{username} : {password}\n")
            print(f"[seed] {len(credentials_log)} compte(s) créé(s).")
            print(f"[seed] Identifiants écrits dans : {CREDENTIALS_FILE}")
            print("[seed] Distribue-les puis SUPPRIME ce fichier du serveur.")
            print("[seed] ---- IDENTIFIANTS (visibles ici dans les logs si tu n'as pas accès au Shell) ----")
            for username, password in credentials_log:
                print(f"[seed-credentials] {username} : {password}")
            print("[seed] ---- FIN DES IDENTIFIANTS ----")
            print("[seed] IMPORTANT : copie-les MAINTENANT, ils ne seront plus jamais réaffichés "
                  "(les prochains déploiements ne recréent pas les comptes déjà existants).")
        else:
            print("[seed] Rien à faire : les comptes existent déjà.")
