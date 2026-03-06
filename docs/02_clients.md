# Module Clients

Gestion des clients et de leurs adresses. Un client peut être une entreprise ou un particulier.
Chaque client appartient à un utilisateur ; un utilisateur ne voit que ses propres clients.

## Modèle de données

### Client

| Champ | Type | Requis | Description |
|---|---|---|---|
| `id` | integer | auto | Identifiant unique |
| `raison_sociale` | string (255) | oui | Raison sociale / nom |
| `siret` | string (14) | non | Numéro SIRET |
| `email` | email | non | Email de l'entreprise |
| `telephone` | string (20) | non | Téléphone de l'entreprise |
| `contact_nom` | string (200) | non | Nom du contact principal |
| `contact_email` | email | non | Email du contact |
| `contact_telephone` | string (20) | non | Téléphone du contact |
| `notes` | text | non | Notes libres |
| `created_at` | datetime | auto | Date de création |
| `updated_at` | datetime | auto | Date de dernière modification |

**Contrainte d'unicité :** La combinaison `(utilisateur, raison_sociale)` est unique. Un utilisateur ne peut pas avoir deux clients avec la même raison sociale.

### Adresse

| Champ | Type | Requis | Description |
|---|---|---|---|
| `id` | integer | auto | Identifiant unique |
| `client` | FK → Client | oui | Client associé |
| `type` | enum | oui | Type d'adresse (voir ci-dessous) |
| `ligne1` | string (255) | oui | Adresse ligne 1 |
| `ligne2` | string (255) | non | Adresse ligne 2 |
| `code_postal` | string (10) | oui | Code postal |
| `ville` | string (100) | oui | Ville |
| `pays` | string (100) | non | Pays (défaut : `France`) |
| `created_at` | datetime | auto | Date de création |
| `updated_at` | datetime | auto | Date de dernière modification |

**Types d'adresse :**

| Valeur | Description |
|---|---|
| `SIEGE` | Siège social (défaut) |
| `FACTURATION` | Adresse de facturation |
| `LIVRAISON` | Adresse de livraison |

---

## Endpoints Clients

Tous les endpoints nécessitent une **authentification Bearer token**.

### GET `/api/clients/` — Liste des clients

Retourne la liste paginée des clients de l'utilisateur connecté, avec leurs adresses imbriquées.

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 1,
        "utilisateur": 1,
        "raison_sociale": "Acme Corp",
        "siret": "12345678901234",
        "email": "contact@acme.com",
        "telephone": "01 23 45 67 89",
        "contact_nom": "Pierre Martin",
        "contact_email": "pierre@acme.com",
        "contact_telephone": "06 12 34 56 78",
        "notes": "",
        "adresses": [
          {
            "id": 1,
            "type": "SIEGE",
            "ligne1": "10 rue de la Paix",
            "ligne2": "",
            "code_postal": "75001",
            "ville": "Paris",
            "pays": "France",
            "created_at": "2025-01-15 10:30:00",
            "updated_at": "2025-01-15 10:30:00"
          }
        ],
        "created_at": "2025-01-15 10:30:00",
        "updated_at": "2025-01-15 10:30:00"
      }
    ]
  }
}
```

---

### POST `/api/clients/` — Créer un client

Crée un client avec optionnellement des adresses imbriquées.

**Corps de la requête :**

```json
{
  "raison_sociale": "Acme Corp",
  "siret": "12345678901234",
  "email": "contact@acme.com",
  "telephone": "01 23 45 67 89",
  "contact_nom": "Pierre Martin",
  "contact_email": "pierre@acme.com",
  "contact_telephone": "06 12 34 56 78",
  "notes": "Client VIP",
  "adresses": [
    {
      "type": "SIEGE",
      "ligne1": "10 rue de la Paix",
      "code_postal": "75001",
      "ville": "Paris"
    },
    {
      "type": "FACTURATION",
      "ligne1": "20 avenue des Champs",
      "code_postal": "75008",
      "ville": "Paris"
    }
  ]
}
```

**Réponse succès (201) :** Objet client complet avec adresses.

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | `raison_sociale` manquante |
| 400 | Raison sociale déjà utilisée par cet utilisateur |

---

### GET `/api/clients/{id}/` — Détail d'un client

Retourne un client avec ses adresses imbriquées.

**Erreurs :**

| Code HTTP | Cause |
|---|---|
| 404 | Client inexistant ou appartenant à un autre utilisateur |

---

### PUT/PATCH `/api/clients/{id}/` — Modifier un client

Modifie un client. Si le champ `adresses` est fourni, **toutes les adresses existantes sont supprimées et remplacées** par celles du payload.

**Exemple PATCH :**

```json
{
  "telephone": "09 87 65 43 21",
  "adresses": [
    {
      "type": "SIEGE",
      "ligne1": "Nouvelle adresse",
      "code_postal": "69001",
      "ville": "Lyon"
    }
  ]
}
```

> **Attention :** Envoyer `adresses` dans un PATCH remplace entièrement la liste d'adresses. Omettre le champ `adresses` ne modifie pas les adresses existantes.

---

### DELETE `/api/clients/{id}/` — Supprimer un client

Suppression définitive (hard delete) du client et de ses adresses.

**Réponse succès :** 204 No Content

> **Note :** Un client référencé par un devis ne peut pas être supprimé (la clé étrangère utilise `PROTECT` sur les devis).

---

## Endpoints Adresses

### GET `/api/adresses/` — Liste des adresses

Retourne les adresses de tous les clients de l'utilisateur.

**Paramètre de filtrage :**

| Paramètre | Type | Description |
|---|---|---|
| `client_id` | integer | Filtre les adresses d'un client spécifique |

**Exemple :** `GET /api/adresses/?client_id=1`

---

### POST `/api/adresses/` — Créer une adresse

**Corps de la requête :**

```json
{
  "client": 1,
  "type": "LIVRAISON",
  "ligne1": "Zone industrielle Nord",
  "code_postal": "69100",
  "ville": "Villeurbanne"
}
```

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | `client` manquant ou invalide |
| 403 | Le client n'appartient pas à l'utilisateur connecté |

---

### GET `/api/adresses/{id}/` — Détail d'une adresse

### PUT/PATCH `/api/adresses/{id}/` — Modifier une adresse

### DELETE `/api/adresses/{id}/` — Supprimer une adresse

Suppression définitive. **Réponse :** 204 No Content.
