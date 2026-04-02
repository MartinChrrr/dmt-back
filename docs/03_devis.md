# Module Devis (Quotes)

Gestion des devis avec lignes imbriquées, workflow de statuts et historique des changements.
Soft delete sur les devis, lignes et historique.

## Modèle de données

### Devis (Quote)

| Champ | Type | Requis | Lecture seule | Description |
|---|---|---|---|---|
| `id` | integer | auto | oui | Identifiant unique |
| `utilisateur` | FK → User | auto | oui | Propriétaire |
| `client` | FK → Client | oui | lecture | Objet client complet (lecture) |
| `client_id` | integer | oui | écriture | ID du client (écriture) |
| `numero` | string (50) | auto | oui | Numéro auto-généré (ex. `DEV-2025-001`) |
| `date_emission` | date | non | non | Date d'émission (défaut : aujourd'hui) |
| `date_validite` | date | auto | non | Date de validité (auto-calculée si omise) |
| `statut` | enum | non | non | Statut du devis (défaut : `BROUILLON`) |
| `objet` | string (255) | non | non | Objet / titre du devis |
| `notes` | text | non | non | Notes libres |
| `total_ht` | decimal | auto | oui | Total hors taxes |
| `total_tva` | decimal | auto | oui | Total TVA |
| `total_ttc` | decimal | auto | oui | Total toutes taxes comprises |
| `created_at` | datetime | auto | oui | Date de création |
| `updated_at` | datetime | auto | oui | Date de modification |
| `lignes` | array | non | non | Lignes du devis (imbriquées) |
| `historique` | array | auto | oui | Historique des statuts |

### Ligne de devis (QuoteLine)

| Champ | Type | Requis | Lecture seule | Description |
|---|---|---|---|---|
| `id` | integer | auto | oui | Identifiant unique |
| `ordre` | integer | non | non | Ordre d'affichage (défaut : 0) |
| `libelle` | string (255) | oui | non | Libellé de la prestation |
| `description` | text | non | non | Description détaillée |
| `quantite` | decimal | non | non | Quantité (défaut : 1.00) |
| `unite` | string (20) | non | non | Unité (heure, jour, forfait…) |
| `prix_unitaire_ht` | decimal | oui | non | Prix unitaire HT |
| `taux_tva` | decimal | non | non | Taux de TVA en % (défaut : 20.00) |
| `montant_ht` | decimal | auto | oui | Montant HT calculé (`quantite × prix_unitaire_ht`) |
| `created_at` | datetime | auto | oui | Date de création |

### Historique de devis (QuoteHistory)

| Champ | Type | Description |
|---|---|---|
| `id` | integer | Identifiant unique |
| `devis` | FK → Quote | Devis concerné |
| `ancien_statut` | string | Ancien statut (`null` si création) |
| `nouveau_statut` | string | Nouveau statut |
| `created_at` | datetime | Date du changement |

## Workflow de statuts

```
                    ┌──────────┐
         ┌─────────│ BROUILLON │─────────┐
         │         └──────────┘          │
         ▼                               ▼
    ┌─────────┐                    ┌──────────┐
    │ ENVOYE  │                    │  REFUSE  │
    └─────────┘                    └──────────┘
         │
         ▼
    ┌──────────┐         ┌─────────┐
    │ ACCEPTE  │         │ EXPIRE  │
    └──────────┘         └─────────┘
```

| Statut | Valeur | Description |
|---|---|---|
| Brouillon | `BROUILLON` | Éditable et supprimable |
| Envoyé | `ENVOYE` | Envoyé au client, en attente de réponse |
| Accepté | `ACCEPTE` | Accepté par le client |
| Refusé | `REFUSE` | Refusé par le client |
| Expiré | `EXPIRE` | Date de validité dépassée |

**Règles d'immutabilité :**
- Seuls les devis au statut `BROUILLON` sont modifiables (PUT/PATCH)
- Seuls les devis au statut `BROUILLON` sont supprimables (DELETE)
- Le changement de statut est possible quel que soit le statut actuel (pas de machine à états stricte côté devis)

---

## Endpoints

Tous les endpoints nécessitent une **authentification Bearer token**.

### GET `/api/quotes/` — Liste des devis

Retourne la liste paginée des devis de l'utilisateur connecté.

**Filtres disponibles :**

| Paramètre | Type | Description |
|---|---|---|
| `statut` | string | Filtre par statut (`BROUILLON`, `ENVOYE`, etc.) |
| `client_id` | integer | Filtre par client |
| `search` | string | Recherche dans `numero`, `objet`, `client.raison_sociale`, `client.contact_nom` et `client.email` |
| `ordering` | string | Tri : `date_emission`, `total_ttc`, `created_at` (préfixer par `-` pour desc) |

**Exemple :** `GET /api/quotes/?statut=BROUILLON&ordering=-date_emission`

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 1,
        "utilisateur": 1,
        "client": {
          "id": 1,
          "raison_sociale": "Acme Corp",
          "siret": "12345678901234",
          "email": "contact@acme.com",
          "telephone": "",
          "contact_nom": "",
          "contact_email": "",
          "contact_telephone": "",
          "notes": "",
          "adresses": [],
          "created_at": "2025-01-15 10:30:00",
          "updated_at": "2025-01-15 10:30:00"
        },
        "numero": "DEV-2025-001",
        "date_emission": "2025-01-15",
        "date_validite": "2025-02-14",
        "statut": "BROUILLON",
        "objet": "Développement site web",
        "notes": "",
        "total_ht": "1500.00",
        "total_tva": "300.00",
        "total_ttc": "1800.00",
        "created_at": "2025-01-15 10:30:00",
        "updated_at": "2025-01-15 10:30:00",
        "lignes": [
          {
            "id": 1,
            "ordre": 1,
            "libelle": "Développement frontend",
            "description": "Intégration maquettes",
            "quantite": "10.00",
            "unite": "jour",
            "prix_unitaire_ht": "150.00",
            "taux_tva": "20.00",
            "montant_ht": "1500.00",
            "created_at": "2025-01-15 10:30:00"
          }
        ],
        "historique": [
          {
            "id": 1,
            "devis": 1,
            "ancien_statut": null,
            "nouveau_statut": "BROUILLON",
            "created_at": "2025-01-15 10:30:00"
          }
        ]
      }
    ]
  }
}
```

---

### POST `/api/quotes/` — Créer un devis

Crée un devis avec ses lignes en une seule requête.

**Comportements automatiques :**
- Le `numero` est auto-généré au format `{PREFIX}-{ANNÉE}-{NUMÉRO}`
- La `date_validite` est calculée automatiquement si non fournie (`date_emission + quote_validity_days`)
- Les totaux (`total_ht`, `total_tva`, `total_ttc`) sont calculés à partir des lignes
- Une entrée d'historique est créée (statut initial `BROUILLON`)

**Corps de la requête :**

```json
{
  "client_id": 1,
  "date_emission": "2025-01-15",
  "objet": "Développement site web",
  "notes": "Devis valable 30 jours",
  "lignes": [
    {
      "ordre": 1,
      "libelle": "Développement frontend",
      "description": "Intégration maquettes Figma",
      "quantite": "10.00",
      "unite": "jour",
      "prix_unitaire_ht": "150.00",
      "taux_tva": "20.00"
    },
    {
      "ordre": 2,
      "libelle": "Développement backend",
      "description": "API REST Django",
      "quantite": "8.00",
      "unite": "jour",
      "prix_unitaire_ht": "200.00",
      "taux_tva": "20.00"
    }
  ]
}
```

**Réponse succès (201) :** Objet devis complet avec lignes, historique et client imbriqués.

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | `client_id` manquant ou invalide |
| 401 | Non authentifié |

---

### GET `/api/quotes/{id}/` — Détail d'un devis

Retourne le devis complet avec lignes et historique.

---

### PUT/PATCH `/api/quotes/{id}/` — Modifier un devis

Modifie un devis **uniquement si le statut est `BROUILLON`**.

**Règles :**
- Le `client` ne peut pas être changé après création
- Si le champ `lignes` est fourni, **toutes les lignes existantes sont soft-supprimées et remplacées** par celles du payload
- Les totaux sont recalculés automatiquement
- Si le `statut` change, une entrée d'historique est créée

**Exemple PATCH :**

```json
{
  "objet": "Développement site web v2",
  "lignes": [
    {
      "ordre": 1,
      "libelle": "Développement fullstack",
      "quantite": "15.00",
      "unite": "jour",
      "prix_unitaire_ht": "180.00",
      "taux_tva": "20.00"
    }
  ]
}
```

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | Devis non modifiable (statut ≠ `BROUILLON`) |
| 404 | Devis inexistant |

---

### DELETE `/api/quotes/{id}/` — Supprimer un devis

Soft delete du devis, de ses lignes et de son historique. **Uniquement si le statut est `BROUILLON`.**

**Réponse succès :** 204 No Content

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | Devis non supprimable (statut ≠ `BROUILLON`) |

---

### POST `/api/quotes/{id}/changer_statut/` — Changer le statut

Change le statut d'un devis et crée une entrée d'historique.

**Corps de la requête :**

```json
{
  "statut": "ENVOYE"
}
```

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "message": "Status changed successfully",
    "data": {
      "id": 1,
      "statut": "ENVOYE",
      "historique": [
        {
          "id": 2,
          "devis": 1,
          "ancien_statut": "BROUILLON",
          "nouveau_statut": "ENVOYE",
          "created_at": "2025-01-16 09:00:00"
        },
        {
          "id": 1,
          "devis": 1,
          "ancien_statut": null,
          "nouveau_statut": "BROUILLON",
          "created_at": "2025-01-15 10:30:00"
        }
      ]
    }
  }
}
```

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | Statut invalide (valeur non reconnue) |
