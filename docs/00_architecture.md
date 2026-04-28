# Architecture générale du backend

## Vue d'ensemble

Backend de gestion de devis et factures construit avec **Django 5.0** et **Django REST Framework 3.14**.
Conçu pour une utilisation mono-utilisateur ou multi-utilisateur, chaque utilisateur ne voit que ses propres données.

## Stack technique

| Composant | Technologie | Version |
|---|---|---|
| Framework web | Django | 5.0 |
| API REST | Django REST Framework | 3.14.0 |
| Base de données | PostgreSQL | 15 |
| Authentification | djangorestframework-simplejwt | 5.3.1 |
| Filtrage | django-filter | 23.5 |
| Génération PDF | WeasyPrint | 61.2 |
| CORS | django-cors-headers | 4.3.1 |
| Conteneurisation | Docker + Docker Compose | — |

## Structure des applications

```
back-pfr/
├── config/                  # Configuration Django
│   ├── settings.py          # Paramètres (DB, JWT, DRF, CORS)
│   ├── urls.py              # Routage racine
│   ├── renderers.py         # Renderer JSend
│   └── exception_handlers.py # Handler d'exceptions JSend
│
├── accounts/                # Utilisateurs & configuration
├── clients/                 # Gestion des clients et adresses
├── services/                # Catalogue de prestations
├── quotes/                  # Gestion des devis
├── invoices/                # Gestion des factures + PDF
├── dashboard/               # Statistiques agrégées (lecture seule)
├── administration/          # Endpoints admin RGPD (liste, effacement, export CSV)
│
├── templates/invoices/      # Template HTML pour PDF facture
├── templates/quotes/        # Template HTML pour PDF devis
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Routage API principal

| Préfixe | Application | Description |
|---|---|---|
| `/api/auth/` | accounts | Authentification, profil, configuration |
| `/api/clients/` | clients | CRUD clients |
| `/api/adresses/` | clients | CRUD adresses |
| `/api/services/` | services | CRUD prestations |
| `/api/quotes/` | quotes | CRUD devis + changement de statut |
| `/api/invoices/` | invoices | CRUD factures + statut, PDF, conversion devis |
| `/api/dashboard/` | dashboard | Statistiques agrégées (lecture seule) |
| `/api/admin/` | administration | RGPD : liste utilisateurs, effacement, export CSV (admin uniquement) |

## Format de réponse — JSend

Toutes les réponses API sont enveloppées au format **JSend** :

### Succès (2xx)

```json
{
  "status": "success",
  "data": { ... }
}
```

### Échec client (4xx)

```json
{
  "status": "fail",
  "data": {
    "champ": ["Message d'erreur"]
  }
}
```

### Erreur serveur (5xx)

```json
{
  "status": "error",
  "message": "Internal server error"
}
```

> **Note :** Le code HTTP 204 (No Content) retourne un corps vide.

## Pagination

Pagination par numéro de page activée globalement.

| Paramètre | Défaut | Description |
|---|---|---|
| `page` | `1` | Numéro de page |
| `page_size` | `20` | Nombre d'éléments par page |

Réponse paginée :

```json
{
  "status": "success",
  "data": {
    "count": 42,
    "next": "http://host/api/quotes/?page=2",
    "previous": null,
    "results": [ ... ]
  }
}
```

## Soft Delete

Les entités **Quote**, **QuoteLine**, **QuoteHistory**, **Invoice** et **InvoiceHistory** implémentent le soft delete :

- Champ `deleted_at` : `null` si actif, timestamp si supprimé
- Le manager par défaut (`objects`) exclut automatiquement les enregistrements supprimés
- Le manager `all_objects` inclut tous les enregistrements
- La suppression cascadée est gérée au niveau applicatif (pas SQL)

À l'inverse, **InvoiceLine**, **Client**, **Address** et **Service** sont en suppression dure (pas de `deleted_at`).

## Isolation des données

Chaque utilisateur ne voit que ses propres données. Le filtrage est effectué dans le `get_queryset()` de chaque ViewSet :

```python
def get_queryset(self):
    return Model.objects.filter(utilisateur=self.request.user)
```

## Transactions atomiques

Les opérations critiques (création de facture, changement de statut, conversion devis→facture) sont protégées par `transaction.atomic()` pour garantir la cohérence des données.

## Configuration utilisateur

Chaque utilisateur dispose d'un objet `UserConfiguration` (créé automatiquement à l'inscription) qui paramètre :

| Paramètre | Défaut | Description |
|---|---|---|
| `quote_prefix` | `DEV` | Préfixe de numérotation des devis |
| `invoice_prefix` | `FAC` | Préfixe de numérotation des factures |
| `next_quote_number` | `1` | Prochain numéro séquentiel de devis |
| `next_invoice_number` | `1` | Prochain numéro séquentiel de facture |
| `quote_validity_days` | `30` | Durée de validité d'un devis (jours) |
| `payment_deadline_days` | `30` | Délai de paiement d'une facture (jours) |

## Numérotation automatique

Format : `{PRÉFIXE}-{ANNÉE}-{NUMÉRO}` (ex. `DEV-2025-001`, `FAC-2025-042`)

- **Devis** : le numéro est généré à la **création** du devis
- **Factures** : le numéro est généré à la **transition vers le statut ENVOYEE** (pas à la création en brouillon)

Le compteur est incrémenté via `UserConfiguration`. Pour les **factures**, l'opération est protégée par `select_for_update()` afin d'éviter les doublons en cas d'accès concurrent ; la numérotation des **devis** ne pose pas ce verrou.
