# Module Services (Prestations)

Catalogue de prestations réutilisables. Chaque service appartient à un utilisateur et sert de référence pour créer rapidement des lignes de devis ou facture.

## Modèle de données

### Service

| Champ | Type | Requis | Lecture seule | Description |
|---|---|---|---|---|
| `id` | integer | auto | oui | Identifiant unique |
| `utilisateur` | FK → User | auto | oui | Propriétaire |
| `label` | string (255) | oui | non | Libellé de la prestation |
| `description` | text | non | non | Description détaillée |
| `unit_price_excl_tax` | decimal | oui | non | Prix unitaire HT |
| `unit` | enum | oui | non | Unité de mesure |
| `taux_tva` | decimal | oui | non | Taux de TVA |
| `created_at` | datetime | auto | oui | Date de création |
| `updated_at` | datetime | auto | oui | Date de modification |

**Unités disponibles :**

| Valeur | Description |
|---|---|
| `heure` | Heure |
| `jour` | Jour |
| `forfait` | Forfait |

**Taux de TVA disponibles :**

| Valeur | Description |
|---|---|
| `20.00` | 20 % (taux normal) |
| `10.00` | 10 % (taux intermédiaire) |
| `5.50` | 5,5 % (taux réduit) |
| `0.00` | 0 % (exonéré) |

---

## Endpoints

Tous les endpoints nécessitent une **authentification Bearer token**.

### GET `/api/services/` — Liste des services

Retourne la liste paginée des services de l'utilisateur connecté.

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
        "label": "Développement web",
        "description": "Développement d'applications web sur mesure",
        "unit_price_excl_tax": "500.00",
        "unit": "jour",
        "taux_tva": "20.00",
        "created_at": "2025-01-10 09:00:00",
        "updated_at": "2025-01-10 09:00:00"
      },
      {
        "id": 2,
        "utilisateur": 1,
        "label": "Conseil technique",
        "description": "",
        "unit_price_excl_tax": "120.00",
        "unit": "heure",
        "taux_tva": "20.00",
        "created_at": "2025-01-12 14:00:00",
        "updated_at": "2025-01-12 14:00:00"
      }
    ]
  }
}
```

---

### POST `/api/services/` — Créer un service

**Corps de la requête :**

```json
{
  "label": "Développement web",
  "description": "Développement d'applications web sur mesure",
  "unit_price_excl_tax": "500.00",
  "unit": "jour",
  "taux_tva": "20.00"
}
```

**Réponse succès (201) :** Objet service complet.

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | `label` manquant |
| 400 | `unit_price_excl_tax` manquant ou invalide |
| 400 | `unit` invalide (valeur non reconnue) |
| 400 | `taux_tva` invalide (valeur non reconnue) |

---

### GET `/api/services/{id}/` — Détail d'un service

### PUT/PATCH `/api/services/{id}/` — Modifier un service

**Exemple PATCH :**

```json
{
  "unit_price_excl_tax": "550.00"
}
```

---

### DELETE `/api/services/{id}/` — Supprimer un service

Suppression définitive (hard delete).

**Réponse succès :** 204 No Content
