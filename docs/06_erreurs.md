# Codes d'erreur et règles métier transversales

## Format des erreurs

Toutes les erreurs suivent le format **JSend**.

### Erreurs de validation (400)

```json
{
  "status": "fail",
  "data": {
    "nom_du_champ": ["Message d'erreur de validation"]
  }
}
```

### Erreur d'authentification (401)

```json
{
  "status": "fail",
  "data": {
    "detail": "Given token not valid for any token type",
    "code": "token_not_valid",
    "messages": [
      {
        "token_class": "AccessToken",
        "token_type": "access",
        "message": "Token is invalid or expired"
      }
    ]
  }
}
```

### Erreur d'autorisation (403)

```json
{
  "status": "fail",
  "data": {
    "detail": "You do not have permission to perform this action."
  }
}
```

### Ressource non trouvée (404)

```json
{
  "status": "fail",
  "data": {
    "detail": "Not found."
  }
}
```

### Erreur serveur (500)

```json
{
  "status": "error",
  "message": "Internal server error"
}
```

---

## Tableau des erreurs métier

| Module | Situation | Code HTTP | Message |
|---|---|---|---|
| **Auth** | Email déjà utilisé | 400 | `{"email": ["user with this Email already exists."]}` |
| **Auth** | Mots de passe différents | 400 | `{"password": ["Passwords do not match."]}` |
| **Auth** | Identifiants invalides | 401 | `{"detail": "No active account found with the given credentials"}` |
| **Auth** | Token expiré | 401 | `{"detail": "Given token not valid for any token type"}` |
| **Auth** | Token blacklisté | 401 | `{"detail": "Token is blacklisted"}` |
| **Clients** | Raison sociale en doublon | 400 | `{"raison_sociale": ["You already have a client with this company name."]}` |
| **Clients** | Adresse pour un client d'un autre utilisateur | 403 | `{"detail": "This client does not belong to you"}` |
| **Devis** | Modification hors brouillon | 400 | `{"error": "Cannot modify a quote that is not in draft status."}` |
| **Devis** | Suppression hors brouillon | 400 | `{"error": "Cannot delete a quote that is not in draft status."}` |
| **Devis** | Statut invalide | 400 | `{"error": "Invalid status"}` |
| **Factures** | Modification hors brouillon | 400 | `{"non_field_errors": ["Only a draft invoice can be modified."]}` |
| **Factures** | Suppression hors brouillon | 403 | `{"detail": "Only a draft invoice can be deleted."}` |
| **Factures** | Aucune ligne fournie | 400 | `{"lignes": ["The invoice must contain at least one line."]}` |
| **Factures** | Échéance < émission | 400 | `{"date_echeance": "The due date cannot be earlier than the issue date."}` |
| **Factures** | Transition non autorisée | 400 | `{"statut": "Transition from '...' to '...' is not allowed."}` |
| **Factures** | Champ statut manquant | 400 | `{"statut": "This field is required."}` |
| **Factures** | Devis non trouvé (conversion) | 400 | `{"devis_id": ["Quote not found."]}` |
| **Factures** | Devis ni envoyé ni accepté | 400 | `{"devis_id": ["Only a sent or accepted quote can be converted to an invoice."]}` |
| **Factures** | Devis déjà converti | 400 | `{"devis_id": ["This quote has already been converted to an invoice."]}` |

---

## Règles métier transversales

### 1. Isolation des données

Chaque utilisateur ne voit et ne manipule que ses propres données. Le filtrage est appliqué au niveau du `get_queryset()` de chaque ViewSet.

### 2. Numérotation automatique

| Document | Moment de génération | Format |
|---|---|---|
| Devis | À la création | `{PREFIX}-{ANNÉE}-{NNN}` |
| Facture | Transition vers `ENVOYEE` | `{PREFIX}-{ANNÉE}-{NNN}` |

- Les préfixes et compteurs sont configurables par utilisateur via `UserConfiguration`
- Le compteur utilise `select_for_update()` (factures) pour éviter les doublons en cas d'accès concurrent
- Exemple : `DEV-2025-001`, `FAC-2025-042`

### 3. Immutabilité des documents finalisés

| Document | Modifiable si | Supprimable si |
|---|---|---|
| Devis | `statut == BROUILLON` | `statut == BROUILLON` |
| Facture | `statut == BROUILLON` | `statut == BROUILLON` |

Une fois qu'un document quitte le statut brouillon, ses données (lignes comprises) sont figées.

### 4. Soft delete

Les entités suivantes utilisent le soft delete (champ `deleted_at`) :
- `Quote`, `QuoteLine`, `QuoteHistory`
- `Invoice`, `InvoiceHistory`

Les `InvoiceLine` utilisent un hard delete (suppression réelle).

Les `Client`, `Address` et `Service` utilisent un hard delete.

### 5. Calcul automatique des totaux

Les montants sont calculés automatiquement :

```
montant_ht (ligne) = quantite × prix_unitaire_ht
total_ht (document) = Σ montant_ht (lignes)
total_tva (document) = Σ (montant_ht × taux_tva / 100) (lignes)
total_ttc (document) = total_ht + total_tva
```

Les totaux sont recalculés à chaque modification de ligne.

### 6. Opérations imbriquées (nested operations)

**Devis :** Les lignes sont envoyées dans le champ `lignes` du payload. Lors d'une mise à jour, toutes les lignes existantes sont soft-supprimées et remplacées par celles du payload.

**Factures :** Synchronisation intelligente des lignes :
- Ligne avec `id` existant → mise à jour
- Ligne sans `id` → création
- Ligne existante absente du payload → hard delete

### 7. Dates par défaut

| Champ | Calcul automatique |
|---|---|
| `date_emission` (devis/facture) | Date du jour si non fournie |
| `date_validite` (devis) | `date_emission + quote_validity_days` si non fournie |
| `date_echeance` (facture) | `date_emission + payment_deadline_days` si non fournie |

### 8. Conversion devis → facture

La conversion d'un devis en facture (`POST /api/invoices/from-devis/`) est une opération atomique qui :

1. Passe le devis au statut `ACCEPTE` (si ce n'est pas déjà le cas)
2. Crée la facture avec les données du devis
3. Copie toutes les lignes actives du devis
4. Calcule les totaux
5. Passe la facture directement au statut `ENVOYEE` avec numéro généré
6. Crée les entrées d'historique correspondantes
7. Lie la facture au devis via `devis_origine`

Un devis ne peut être converti qu'une seule fois.

### 9. Transactions atomiques

Les opérations suivantes sont protégées par `transaction.atomic()` :
- Création de facture (avec lignes)
- Changement de statut de facture (avec génération de numéro)
- Conversion devis → facture

### 10. Pagination

Toutes les listes sont paginées par défaut (20 éléments par page).

| Paramètre | Description |
|---|---|
| `page` | Numéro de page (défaut : 1) |

### 11. CORS

Origines autorisées :
- `http://localhost:3000`
- `http://localhost:5173`
- `http://localhost:8080`
