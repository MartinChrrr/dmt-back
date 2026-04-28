# Module Administration (RGPD)

Endpoints réservés aux administrateurs (`is_staff=True`) pour gérer les obligations RGPD : **droit à l'effacement** (article 17) et **droit à la portabilité** (article 20).

## Endpoints

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/api/admin/users/` | Liste des utilisateurs avec compteurs |
| `DELETE` | `/api/admin/users/<id>/` | Effacement définitif des données d'un utilisateur |
| `GET` | `/api/admin/users/<id>/export/` | Export RGPD (ZIP de CSV) des données d'un utilisateur |

**Authentification** : JWT requis.
**Permission** : `IsAdminUser` — l'utilisateur doit avoir `is_staff=True`. Un utilisateur standard reçoit `403 Forbidden`.

## `GET /api/admin/users/`

Retourne tous les utilisateurs de la plateforme triés par `date_joined` décroissant, avec trois compteurs annotés en SQL (un seul aller-retour DB).

### Réponse

```json
{
  "status": "success",
  "data": [
    {
      "id": 12,
      "email": "user@example.com",
      "username": "user",
      "first_name": "John",
      "last_name": "Doe",
      "company_name": "ACME",
      "is_active": true,
      "is_staff": false,
      "date_joined": "2026-01-14T09:12:00Z",
      "last_login": "2026-04-27T18:02:11Z",
      "clients_count": 8,
      "quotes_count": 23,
      "invoices_count": 17
    }
  ]
}
```

## `DELETE /api/admin/users/<id>/` — Droit à l'effacement

Supprime **définitivement** (hard delete) toutes les données personnelles de l'utilisateur ciblé.

### Périmètre supprimé

L'opération s'exécute dans une transaction atomique et purge dans l'ordre :

1. `QuoteLine` (y compris soft-deleted via `all_objects`)
2. `QuoteHistory` (y compris soft-deleted)
3. `Quote` (y compris soft-deleted)
4. `InvoiceLine`
5. `InvoiceHistory` (y compris soft-deleted)
6. `Invoice` (y compris soft-deleted)
7. `Address` (cascade via `client__utilisateur`)
8. `Client`
9. `Service`
10. `User` (et `UserConfiguration` via `on_delete=CASCADE`)

> **Note** : les modèles concernés par le soft delete sont purgés via le manager `all_objects` afin d'effacer aussi les enregistrements déjà marqués `deleted_at`. Sans cela, les données resteraient en base après l'« effacement RGPD ».

### Garde-fous

| Cas | Code | Détail |
|---|---|---|
| Cible introuvable | `404 Not Found` | — |
| Cible est un superuser | `403 Forbidden` | `Impossible de supprimer un superutilisateur.` |
| Cible = appelant | `403 Forbidden` | `Impossible de supprimer son propre compte via cette route.` |
| Succès | `200 OK` | `{"detail": "Données de <email> supprimées définitivement."}` |

## `GET /api/admin/users/<id>/export/` — Droit à la portabilité

Génère et renvoie une archive ZIP contenant **un fichier CSV par entité** détenue par l'utilisateur. Format adapté à une réutilisation directe (tableur, import dans un autre service).

### Réponse

- `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="rgpd_export_user_<id>_<YYYYMMDD_HHMMSS>.zip"`
- Corps : flux binaire ZIP

> **Important** : cette route ne renvoie **pas** de JSON enveloppé JSend. Le client doit consommer le `Blob`/flux directement.

### Contenu de l'archive

| Fichier | Données |
|---|---|
| `user.csv` | Profil utilisateur (email, identité, entreprise, SIRET, adresse, téléphone, dates) |
| `clients.csv` | Clients (raison sociale, contact, notes) |
| `addresses.csv` | Adresses liées aux clients |
| `services.csv` | Catalogue de prestations |
| `quotes.csv` | Devis (y compris soft-deleted, `deleted_at` exposé) |
| `quote_lines.csv` | Lignes de devis (y compris soft-deleted) |
| `invoices.csv` | Factures (y compris soft-deleted) |
| `invoice_lines.csv` | Lignes de factures |

Séparateur : `;` (point-virgule, compatible Excel FR). Encodage : UTF-8.

### Exemple

```bash
curl -X GET http://localhost:8000/api/admin/users/12/export/ \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  --output export_user_12.zip
```

## Codes d'erreur

| Code | Cas |
|---|---|
| `200 OK` | Succès (liste, suppression, export) |
| `401 Unauthorized` | JWT manquant ou invalide |
| `403 Forbidden` | Appelant non-admin, ou cible protégée (superuser / soi-même) |
| `404 Not Found` | `user_id` inexistant |

## Implémentation

| Fichier | Rôle |
|---|---|
| [administration/views.py](../administration/views.py) | `AdminUserListView`, `AdminUserDeleteView`, `AdminUserExportView` |
| [administration/serializers.py](../administration/serializers.py) | `AdminUserListSerializer` (compteurs annotés) |
| [administration/urls.py](../administration/urls.py) | Routes `admin/users/`, `admin/users/<id>/`, `admin/users/<id>/export/` |

### Choix techniques

- **`IsAdminUser`** plutôt qu'un système de rôles dédié : aligne sur le flag natif `is_staff` déjà géré par Django et par l'admin `/admin/`.
- **Hard delete** plutôt qu'anonymisation : approche la plus simple et conforme à la demande RGPD « effacer mes données ». À noter que le Code de commerce français impose une conservation 10 ans des factures — un déploiement en production devrait basculer sur une **anonymisation** (remplacement des champs personnels par des valeurs neutres) pour les factures déjà émises.
- **Export en ZIP de CSV** plutôt qu'un seul JSON : format ouvert, lisible sans outil spécifique, conforme à l'esprit de l'article 20 (« format structuré, couramment utilisé et lisible par machine »).
- **Annotations `Count(distinct=True)`** sur la liste : évite N+1 en calculant les compteurs côté SQL en une requête.
