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
├── config/         # Configuration Django
├── accounts/       # Authentification
├── clients/        # Gestion clients (à venir)
├── services/       # Catalogue prestations (à venir)
├── quotes/         # Devis (à venir)
├── invoices/       # Factures (à venir)
└── docker-compose.yml
```
