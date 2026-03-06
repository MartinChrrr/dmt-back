# Module Factures (Invoices)

Gestion des factures avec lignes imbriquées, workflow de statuts strict, conversion depuis un devis et génération PDF.
Soft delete sur les factures et l'historique.

## Modèle de données

### Facture (Invoice)

| Champ | Type | Requis | Lecture seule | Description |
|---|---|---|---|---|
| `id` | integer | auto | oui | Identifiant unique |
| `utilisateur` | FK → User | auto | oui | Propriétaire |
| `client` | FK → Client | oui | lecture | Objet client complet (lecture) |
| `client_id` | integer | oui | écriture | ID du client (écriture) |
| `devis_origine` | FK → Quote | non | oui | Devis d'origine (si conversion) |
| `numero` | string (50) | auto | oui | Numéro généré à l'envoi (ex. `FAC-2025-001`) |
| `date_emission` | date | non | non | Date d'émission (défaut : aujourd'hui) |
| `date_echeance` | date | non | non | Date d'échéance (auto-calculée si omise) |
| `statut` | enum | auto | oui | Statut de la facture (défaut : `BROUILLON`) |
| `objet` | string (255) | non | non | Objet / titre |
| `notes` | text | non | non | Notes libres |
| `total_ht` | decimal | auto | oui | Total hors taxes |
| `total_tva` | decimal | auto | oui | Total TVA |
| `total_ttc` | decimal | auto | oui | Total TTC |
| `lignes` | array | oui | non | Lignes de facture (imbriquées) |
| `historique` | array | auto | oui | Historique des statuts |
| `created_at` | datetime | auto | oui | Date de création |
| `updated_at` | datetime | auto | oui | Date de modification |

### Ligne de facture (InvoiceLine)

| Champ | Type | Requis | Lecture seule | Description |
|---|---|---|---|---|
| `id` | integer | auto/opt | non | ID (fourni pour mise à jour, omis pour création) |
| `ordre` | integer | non | non | Ordre d'affichage (défaut : 0) |
| `libelle` | string (255) | oui | non | Libellé de la prestation |
| `description` | text | non | non | Description détaillée |
| `quantite` | decimal | non | non | Quantité (défaut : 1.00) |
| `unite` | string (20) | non | non | Unité |
| `prix_unitaire_ht` | decimal | oui | non | Prix unitaire HT |
| `taux_tva` | decimal | non | non | Taux de TVA en % (défaut : 20.00) |
| `montant_ht` | decimal | auto | oui | Montant HT calculé |

### Historique de facture (InvoiceHistory)

| Champ | Type | Description |
|---|---|---|
| `id` | integer | Identifiant unique |
| `ancien_statut` | string | Ancien statut (`null` si création) |
| `nouveau_statut` | string | Nouveau statut |
| `created_at` | datetime | Date du changement |

## Workflow de statuts

```
    ┌──────────┐
    │ BROUILLON │
    └─────┬────┘
          │
          ▼
    ┌──────────┐
    │ ENVOYEE  │──────────────┐
    └─────┬────┘              │
          │                   ▼
          │            ┌───────────┐
          │            │ EN_RETARD │
          │            └─────┬─────┘
          │                  │
          ▼                  ▼
    ┌──────────┐
    │  PAYEE   │  ← (terminal)
    └──────────┘
```

| Statut | Valeur | Description |
|---|---|---|
| Brouillon | `BROUILLON` | Éditable et supprimable |
| Envoyée | `ENVOYEE` | Envoyée au client, numéro généré |
| Payée | `PAYEE` | Payée (statut terminal) |
| En retard | `EN_RETARD` | Échéance dépassée |

**Transitions autorisées :**

| Depuis | Vers |
|---|---|
| `BROUILLON` | `ENVOYEE` |
| `ENVOYEE` | `PAYEE`, `EN_RETARD` |
| `EN_RETARD` | `PAYEE` |
| `PAYEE` | *(aucune — terminal)* |

**Règles d'immutabilité :**
- Seules les factures au statut `BROUILLON` sont modifiables (PUT/PATCH)
- Seules les factures au statut `BROUILLON` sont supprimables (DELETE)
- Le numéro de facture est **généré uniquement lors de la transition BROUILLON → ENVOYEE**

---

## Endpoints

Tous les endpoints nécessitent une **authentification Bearer token**.

### GET `/api/invoices/` — Liste des factures

**Filtres disponibles :**

| Paramètre | Type | Description |
|---|---|---|
| `client` | integer | Filtre par client |
| `statut` | string | Filtre par statut |
| `devis_origine` | integer | Filtre par devis d'origine |
| `devis_origine__isnull` | boolean | Factures avec/sans devis d'origine |
| `date_emission_after` | date | Date d'émission minimale |
| `date_emission_before` | date | Date d'émission maximale |
| `date_echeance_after` | date | Date d'échéance minimale |
| `date_echeance_before` | date | Date d'échéance maximale |
| `search` | string | Recherche dans `numero` et `objet` |
| `ordering` | string | Tri : `date_emission`, `date_echeance`, `created_at`, `total_ttc` |

**Exemple :** `GET /api/invoices/?statut=ENVOYEE&date_echeance_before=2025-03-01`

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
          "adresses": [ ... ]
        },
        "devis_origine": null,
        "numero": "FAC-2025-001",
        "date_emission": "2025-02-01",
        "date_echeance": "2025-03-03",
        "statut": "ENVOYEE",
        "objet": "Prestation de conseil",
        "notes": "",
        "total_ht": "2000.00",
        "total_tva": "400.00",
        "total_ttc": "2400.00",
        "lignes": [
          {
            "id": 1,
            "ordre": 1,
            "libelle": "Conseil stratégique",
            "description": "",
            "quantite": "4.00",
            "unite": "jour",
            "prix_unitaire_ht": "500.00",
            "taux_tva": "20.00",
            "montant_ht": "2000.00"
          }
        ],
        "historique": [
          {
            "id": 2,
            "ancien_statut": "BROUILLON",
            "nouveau_statut": "ENVOYEE",
            "created_at": "2025-02-01 14:00:00"
          },
          {
            "id": 1,
            "ancien_statut": null,
            "nouveau_statut": "BROUILLON",
            "created_at": "2025-02-01 10:00:00"
          }
        ],
        "created_at": "2025-02-01 10:00:00",
        "updated_at": "2025-02-01 14:00:00"
      }
    ]
  }
}
```

---

### POST `/api/invoices/` — Créer une facture

Crée une facture avec ses lignes en une seule requête.

**Comportements automatiques :**
- La `date_echeance` est calculée si non fournie (`date_emission + payment_deadline_days`)
- Le `statut` initial est `BROUILLON` (pas de numéro à ce stade)
- Les totaux sont calculés à partir des lignes
- Une entrée d'historique est créée

**Corps de la requête :**

```json
{
  "client_id": 1,
  "date_emission": "2025-02-01",
  "objet": "Prestation de conseil",
  "notes": "Paiement à 30 jours",
  "lignes": [
    {
      "ordre": 1,
      "libelle": "Conseil stratégique",
      "description": "Accompagnement transformation digitale",
      "quantite": "4.00",
      "unite": "jour",
      "prix_unitaire_ht": "500.00",
      "taux_tva": "20.00"
    }
  ]
}
```

**Réponse succès (201) :** Objet facture complet.

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | `client_id` manquant ou invalide |
| 400 | Aucune ligne fournie |
| 400 | `date_echeance` antérieure à `date_emission` |

---

### GET `/api/invoices/{id}/` — Détail d'une facture

Retourne la facture complète avec lignes et historique.

---

### PUT/PATCH `/api/invoices/{id}/` — Modifier une facture

Modifie une facture **uniquement si le statut est `BROUILLON`**.

**Synchronisation des lignes :**
- Lignes avec `id` existant → mises à jour
- Lignes sans `id` → créées
- Lignes existantes absentes du payload → **supprimées** (hard delete)

**Règles :**
- Le `client` ne peut pas être changé après création
- Le `statut` ne peut pas être changé via PUT/PATCH (utiliser `changer_statut`)
- Les totaux sont recalculés automatiquement

**Exemple PUT :**

```json
{
  "client_id": 1,
  "objet": "Prestation de conseil - mis à jour",
  "lignes": [
    {
      "id": 1,
      "ordre": 1,
      "libelle": "Conseil stratégique",
      "quantite": "5.00",
      "unite": "jour",
      "prix_unitaire_ht": "500.00",
      "taux_tva": "20.00"
    },
    {
      "ordre": 2,
      "libelle": "Formation équipe",
      "quantite": "2.00",
      "unite": "jour",
      "prix_unitaire_ht": "400.00",
      "taux_tva": "20.00"
    }
  ]
}
```

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | Facture non modifiable (statut ≠ `BROUILLON`) |
| 400 | Aucune ligne fournie |
| 400 | `date_echeance` antérieure à `date_emission` |

---

### DELETE `/api/invoices/{id}/` — Supprimer une facture

Soft delete de la facture, ses lignes et son historique. **Uniquement si le statut est `BROUILLON`.**

**Réponse succès :** 204 No Content

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 403 | Facture non supprimable (statut ≠ `BROUILLON`) |

---

### POST `/api/invoices/{id}/changer_statut/` — Changer le statut

Change le statut de la facture selon les transitions autorisées.

**Corps de la requête :**

```json
{
  "statut": "ENVOYEE"
}
```

**Comportements automatiques :**
- Transition `BROUILLON → ENVOYEE` : génère le numéro de facture (`FAC-2025-001`)
- Une entrée d'historique est créée
- Opération atomique (transaction)

**Réponse succès (200) :** Objet facture complet avec le nouveau statut et numéro.

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | Champ `statut` manquant |
| 400 | Transition non autorisée (ex. `BROUILLON → PAYEE`) |

**Exemple d'erreur de transition :**

```json
{
  "status": "fail",
  "data": {
    "statut": "Transition from 'BROUILLON' to 'PAYEE' is not allowed. Allowed transitions: ['ENVOYEE']"
  }
}
```

---

### POST `/api/invoices/from-devis/` — Créer une facture depuis un devis

Convertit un devis envoyé ou accepté en facture.

**Corps de la requête :**

```json
{
  "devis_id": 1
}
```

**Comportements automatiques :**
1. Si le devis est au statut `ENVOYE`, il passe à `ACCEPTE` (avec historique)
2. Une facture est créée avec les informations du devis (client, objet, notes)
3. Toutes les lignes du devis sont copiées dans la facture
4. La `date_echeance` est calculée depuis `payment_deadline_days`
5. La facture passe directement au statut `ENVOYEE` avec numéro généré
6. Deux entrées d'historique sont créées sur la facture (BROUILLON → ENVOYEE)
7. Le devis est lié via le champ `devis_origine`

**Réponse succès (201) :** Objet facture complet.

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | `devis_id` invalide ou devis inexistant |
| 400 | Devis ni envoyé ni accepté |
| 400 | Devis déjà converti en facture |

---

### GET `/api/invoices/{id}/pdf/` — Générer le PDF

Génère et télécharge le PDF de la facture.

**Réponse :** Fichier PDF en téléchargement (`Content-Type: application/pdf`)

**Nom du fichier :** `{numero}.pdf` (ex. `FAC-2025-001.pdf`) ou `draft-{id}.pdf` si brouillon.

**Adresse utilisée :** L'adresse de facturation (`FACTURATION`) du client est utilisée en priorité, avec fallback sur l'adresse du siège (`SIEGE`).
