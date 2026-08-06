# CRM NASORA-GROUP

Application de gestion commerciale pour les deux divisions du groupe NASORA :
- **NASDERM** (dermatologie) — fournisseurs Nova Pharma, Gilbert
- **NASMEDIC** (médecine générale) — fournisseurs Eric Favre, 3 Chênes Pharma

Refonte complète (juillet 2026) : architecture modulaire (blueprints Flask),
configuration par variables d'environnement, correctifs de bugs, et
préparation au déploiement sur PaaS (Render / Railway / Heroku-like).

## Structure du projet

```
nasora-crm/
├── app/
│   ├── __init__.py        # application factory (create_app)
│   ├── config.py          # configuration via variables d'environnement
│   ├── extensions.py      # instances Flask-SQLAlchemy, Login, Migrate, CSRF, Cache
│   ├── models.py          # modèles SQLAlchemy
│   ├── forms.py           # formulaires WTForms
│   ├── utils.py           # décorateur roles_required
│   ├── routes/
│   │   ├── auth.py        # accueil, connexion, déconnexion
│   │   ├── dashboard.py   # tableau de bord commercial + saisie prospection
│   │   ├── planning.py    # plannings hebdomadaires (commercial + admin)
│   │   ├── sales.py       # saisie des ventes (4 fournisseurs, route générique)
│   │   ├── revenue.py     # CA mensuel par division et par fournisseur
│   │   └── admin.py       # tableau de bord admin, fiche commercial, exports
│   ├── templates/
│   └── static/
│       ├── css/styles.css
│       └── images/logo.svg
├── migrations/             # migrations Alembic (Flask-Migrate)
├── seed.py                 # création des comptes et du catalogue produit
├── wsgi.py                 # point d'entrée production (gunicorn)
├── run.py                  # point d'entrée développement local
├── requirements.txt
├── Procfile                 # déploiement PaaS (Render/Railway/Heroku)
├── .env.example
└── .gitignore
```

## Ce qui a changé par rapport à la version initiale

- **Config via environnement** : plus de `SECRET_KEY` ni de mots de passe en
  dur dans le code. `DATABASE_URL` bascule automatiquement entre SQLite (dev)
  et PostgreSQL (prod), avec correction du préfixe `postgres://` → `postgresql://`.
- **Blueprints** au lieu d'un seul fichier `app.py` de ~1000 lignes.
- **Bug corrigé** : le CA mensuel affiché sur les tableaux de bord NASDERM et
  NASMEDIC ne prenait en compte qu'un seul des deux fournisseurs de la
  division (Nova Pharma seul, ou Eric Favre seul). Il combine maintenant les
  deux fournisseurs de chaque division.
- **Bug corrigé** : les champs de stock par grossiste (DUOPHARM, UBIPHARM,
  LABOREX, SODIPHARM) affichés dans les formulaires de vente n'étaient
  jamais enregistrés en base. Ils le sont désormais.
- **Bug corrigé** : les messages `flash()` (succès/erreur) n'étaient affichés
  dans aucun template. Ajoutés dans `base.html`.
- **4 templates de vente dupliqués** (Nova Pharma / Gilbert / Eric Favre / 3
  Chênes, strictement identiques) fusionnés en un seul `supplier_sales.html`.
- **Colonnes de base de données renommées** en ASCII (`produits_presentes`
  au lieu de `produits_presentés`) pour plus de portabilité.
- **Séparation des rôles renforcée** : un commercial ne peut saisir des
  ventes que pour sa propre division, ni consulter la fiche d'un autre
  commercial (403 sinon).
- **Pagination** ajoutée sur les tableaux (25 lignes/page) pour l'admin et
  la fiche commercial.
- **Mots de passe** : le script `seed.py` génère des mots de passe aléatoires
  (ou les lit depuis l'environnement) au lieu de valeurs codées en dur, et
  les écrit une seule fois dans `instance/seed_credentials.txt`
  (fichier ignoré par git — à distribuer puis supprimer).

## Installation locale

Prérequis : Python 3.11+

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Édite .env : mets une vraie SECRET_KEY et des mots de passe de seed

export FLASK_APP=wsgi.py           # Windows (PowerShell) : $env:FLASK_APP="wsgi.py"
flask db upgrade                   # crée les tables via les migrations
python seed.py                     # crée les comptes + catalogue produit

python run.py                      # démarre sur http://127.0.0.1:5000
```

Les identifiants générés apparaissent dans
`instance/seed_credentials.txt` — à consulter puis supprimer.

## Déploiement sur un PaaS (Render / Railway)

Ces plateformes détectent `requirements.txt` et `Procfile` automatiquement.

### 1. Base de données
Crée une base **PostgreSQL** managée sur la plateforme (Render : "New +" →
"PostgreSQL" ; Railway : "New" → "Database" → "PostgreSQL"). Elle fournit
automatiquement la variable d'environnement `DATABASE_URL` à ton service web
si tu les relies (sur Render : ajoute la base comme ressource liée au
service ; sur Railway, les deux services du même projet partagent les
variables automatiquement si tu ajoutes une référence).

### 2. Variables d'environnement à définir sur le service web
| Variable | Valeur |
|---|---|
| `SECRET_KEY` | générée avec `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_ENV` | `production` |
| `DATABASE_URL` | fournie automatiquement par le service Postgres |
| `SEED_ADMIN_PASSWORD` | mot de passe choisi pour le compte admin (à ne définir que le temps du premier déploiement) |
| `SEED_DEFAULT_COMMERCIAL_PASSWORD` | optionnel — sinon mots de passe aléatoires générés individuellement |

### 3. Build & Start
- **Build command** : `pip install -r requirements.txt`
- **Start command** (déjà dans `Procfile`) : `gunicorn wsgi:app --workers 2 --threads 4 --timeout 60`
- Le `Procfile` déclenche aussi `flask db upgrade` avant chaque déploiement
  (phase `release`), pour appliquer les migrations automatiquement.

### 4. Premier peuplement de la base
Une fois le premier déploiement terminé, exécute une seule fois (Render :
"Shell" dans le dashboard du service ; Railway : `railway run`) :

```bash
python seed.py
```

Récupère les identifiants dans `instance/seed_credentials.txt` sur le
serveur (ou redirige la sortie), distribue-les à l'équipe, puis supprime le
fichier.

### 5. Vérifications post-déploiement
- `SECRET_KEY` est bien définie (l'app refuse de démarrer en production sans elle)
- `DATABASE_URL` pointe vers Postgres, pas SQLite (le stockage disque des
  PaaS est éphémère — une base SQLite locale serait effacée à chaque
  redéploiement)
- Le trafic est bien en HTTPS (les cookies de session sont marqués `secure`
  en production, donc invisibles en HTTP)

## Comptes créés par le seed

Le seed crée automatiquement :
- 1 compte administrateur (`Anna Diallo`)
- 8 commerciaux NASMEDIC (Eric Favre / 3 Chênes Pharma)
- 9 commerciaux NASDERM (Nova Pharma / Gilbert)

Tous les mots de passe sont générés aléatoirement (ou lus depuis les
variables d'environnement de seed) — voir `instance/seed_credentials.txt`
après exécution.

## Prochaines améliorations possibles

- Forcer le changement de mot de passe à la première connexion
- Notifications par email pour les nouvelles prospections
- Export CSV/Excel des plannings et du CA
- Tableau de bord enrichi (comparatif zones, tendances)
- Limitation du taux de connexion (Flask-Limiter) contre le brute-force
