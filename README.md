# Gestion Devis & Factures - API REST

Application Django REST API pour la gestion de devis et factures pour auto-entrepreneurs.

## Technologies

- Django 5.0 + Django REST Framework
- PostgreSQL 15
- JWT Authentication
- Docker

## Installation
```bash
# Cloner le projet
git clone https://github.com/KohakuC/back-pfr.git
cd gestion-devis-factures

# Lancer avec Docker
docker compose up -d --build

# Migrations
docker compose exec web python manage.py migrate

# Créer un superuser
docker compose exec web python manage.py createsuperuser
```

**Accès** : http://localhost:8000

## API Endpoints

### Authentification

- `POST /api/auth/register/` - Inscription
- `POST /api/auth/login/` - Connexion (JWT)
- `POST /api/auth/token/refresh/` - Rafraîchir token
- `POST /api/auth/logout/` - Déconnexion
- `GET /api/auth/me/` - Profil utilisateur
- `PUT /api/auth/profile/` - Modifier profil

### Dashboard

- `GET /api/dashboard/stats/` - Statistiques agrégées (CA mensuel, en attente, échéances à venir, dernières transactions)

### Administration (RGPD — admin uniquement, `is_staff=True`)

- `GET /api/admin/users/` - Liste des utilisateurs avec compteurs (clients, devis, factures)
- `DELETE /api/admin/users/<id>/` - Effacement définitif des données (droit à l'oubli, art. 17 RGPD)
- `GET /api/admin/users/<id>/export/` - Export ZIP/CSV des données (droit à la portabilité, art. 20 RGPD)

Voir [docs/08_administration.md](docs/08_administration.md) pour le détail.

## Exemples

### Inscription
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "user",
    "password": "password123",
    "password_confirm": "password123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### Connexion
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

### Requête authentifiée
```bash
curl -X GET http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Export RGPD d'un utilisateur (admin)
```bash
curl -X GET http://localhost:8000/api/admin/users/12/export/ \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  --output export_user_12.zip
```

### Effacement RGPD d'un utilisateur (admin)
```bash
curl -X DELETE http://localhost:8000/api/admin/users/12/ \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

## Commandes utiles
```bash
# Démarrer
docker compose up -d

# Arrêter
docker compose down

# Logs
docker compose logs -f web

# Shell Django
docker compose exec web python manage.py shell

# Migrations
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Create SuperUser
python manage.py createsuperuser
Username: admin
Email address: admin@example.com
Password: **********
Password (again): *********

Superuser created successfully.
```

## Configuration

**Base de données**
- Host: `db`
- Database: `devis_factures_db`
- User: `django_user_admin`
- Password: `qwerty12345`

**JWT**
- Access Token: 1h
- Refresh Token: 7 jours

## Structure
```
gestion-devis-factures/
├── config/           # Configuration Django
├── accounts/         # Authentification, profil, configuration utilisateur
├── clients/          # Gestion clients & adresses
├── services/         # Catalogue prestations
├── quotes/           # Devis
├── invoices/         # Factures + génération PDF
├── dashboard/        # Statistiques agrégées (lecture seule)
├── administration/   # Endpoints admin RGPD (effacement, export CSV)
└── docker-compose.yml
```


## Tests

Chaque module possède sa propre suite de tests Django. Lancer les tests d'un module :

```bash
docker compose exec web python manage.py test <module> -v 2
```

Modules testés :

| Module | Commande |
|---|---|
| accounts | `docker compose exec web python manage.py test accounts -v 2` |
| clients | `docker compose exec web python manage.py test clients -v 2` |
| services | `docker compose exec web python manage.py test services -v 2` |
| quotes | `docker compose exec web python manage.py test quotes -v 2` |
| invoices | `docker compose exec web python manage.py test invoices -v 2` |
| dashboard | `docker compose exec web python manage.py test dashboard -v 2` |
| administration | `docker compose exec web python manage.py test administration -v 2` |

Lancer toute la suite :

```bash
docker compose exec web python manage.py test -v 2
```

En cas d'échec lié aux migrations, régénérer et appliquer avant de relancer :

```bash
docker compose exec web python manage.py makemigrations <module>
docker compose exec web python manage.py migrate
```