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








# Module Devis (Quotes)

## Description

Le module Devis permet de créer, modifier et suivre des devis clients. Chaque devis est composé d'une ou plusieurs lignes de prestation et dispose d'un historique complet des changements de statut. Le numéro de devis est généré automatiquement à partir de la configuration utilisateur au format `PREFIXE-ANNEE-NUMERO` (ex : `DEV-2025-001`).

## Endpoints

| Méthode | URL | Description |
|---------|-----|-------------|
| `GET` | `/api/quotes/` | Liste des devis avec filtres |
| `POST` | `/api/quotes/` | Création d'un devis avec ses lignes |
| `GET` | `/api/quotes/{id}/` | Détail d'un devis |
| `PUT` | `/api/quotes/{id}/` | Mise à jour complète (devis + lignes) |
| `PATCH` | `/api/quotes/{id}/` | Mise à jour partielle |
| `DELETE` | `/api/quotes/{id}/` | Suppression (soft delete) |
| `POST` | `/api/quotes/{id}/changer-statut/` | Changement de statut |

## Filtres et tri

La liste des devis supporte les paramètres suivants :

| Paramètre | Exemple | Description |
|-----------|---------|-------------|
| `statut` | `?statut=BROUILLON` | Filtrer par statut |
| `client` | `?client=1` | Filtrer par client |
| `date_emission_after` | `?date_emission_after=2025-01-01` | Devis émis après cette date |
| `date_emission_before` | `?date_emission_before=2025-12-31` | Devis émis avant cette date |
| `ordering` | `?ordering=-total_ttc` | Tri (préfixe `-` pour décroissant) |

Les filtres sont cumulables : `?client=1&statut=ENVOYE&ordering=-date_emission`

Champs de tri disponibles : `date_emission`, `created_at`, `total_ttc`.

## Cycle de vie d'un devis

```
BROUILLON → ENVOYE → ACCEPTE
                   → REFUSE  → BROUILLON
                   → EXPIRE  → BROUILLON
```

Chaque transition est enregistrée dans l'historique et accessible via le champ `historique` du devis. Les transitions non autorisées retournent une erreur `400`.

## Gestion des lignes

Les lignes de devis sont gérées directement depuis le endpoint du devis (nested writable). Lors d'une mise à jour :

- Les lignes avec un `id` existant sont **mises à jour**.
- Les lignes sans `id` sont **créées**.
- Les lignes existantes absentes du payload sont **supprimées** (soft delete).

Les totaux HT, TVA et TTC sont recalculés automatiquement après chaque modification.

## Numérotation automatique

Le numéro de devis est généré automatiquement à la création à partir de la table `UserConfiguration` :

- **Format** : `{prefixe_devis}-{année}-{numéro}` → `DEV-2025-001`
- Le compteur `next_quote_number` est incrémenté automatiquement.
- La `date_validite` est calculée à partir de `quote_validity_days` si elle n'est pas fournie.

## Soft delete

La suppression d'un devis ne le retire pas de la base de données. Le champ `deleted_at` est renseigné et le devis est exclu des requêtes par défaut. Les lignes et l'historique associés sont également soft-deletés en cascade.

## Exemple de payload (création)

```json
{
  "client": 1,
  "objet": "Refonte site web vitrine",
  "notes": "Délai estimé : 3 semaines",
  "lignes": [
    {
      "ordre": 1,
      "libelle": "Maquette UX/UI",
      "description": "Création des maquettes Figma",
      "quantite": "1.00",
      "unite": "forfait",
      "prix_unitaire_ht": "1500.00",
      "taux_tva": "20.00"
    },
    {
      "ordre": 2,
      "libelle": "Intégration front-end",
      "quantite": "5.00",
      "unite": "jour",
      "prix_unitaire_ht": "450.00",
      "taux_tva": "20.00"
    }
  ]
}
```

## Exemple de réponse

```json
{
  "id": 1,
  "utilisateur": 1,
  "client": 1,
  "numero": "DEV-2025-001",
  "date_emission": "2025-02-05",
  "date_validite": "2025-03-07",
  "statut": "BROUILLON",
  "objet": "Refonte site web vitrine",
  "notes": "Délai estimé : 3 semaines",
  "total_ht": "3750.00",
  "total_tva": "750.00",
  "total_ttc": "4500.00",
  "lignes": [
    {
      "id": 1,
      "ordre": 1,
      "libelle": "Maquette UX/UI",
      "description": "Création des maquettes Figma",
      "quantite": "1.00",
      "unite": "forfait",
      "prix_unitaire_ht": "1500.00",
      "taux_tva": "20.00",
      "montant_ht": "1500.00"
    },
    {
      "id": 2,
      "ordre": 2,
      "libelle": "Intégration front-end",
      "description": "",
      "quantite": "5.00",
      "unite": "jour",
      "prix_unitaire_ht": "450.00",
      "taux_tva": "20.00",
      "montant_ht": "2250.00"
    }
  ],
  "historique": [
    {
      "id": 1,
      "ancien_statut": null,
      "nouveau_statut": "BROUILLON",
      "created_at": "2025-02-05T14:30:00Z"
    }
  ],
  "created_at": "2025-02-05T14:30:00Z",
  "updated_at": "2025-02-05T14:30:00Z"
}
```