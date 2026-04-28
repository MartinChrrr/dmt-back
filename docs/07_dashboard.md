# Module Dashboard

Endpoint en lecture seule qui retourne les statistiques agrégées de l'utilisateur authentifié pour alimenter le tableau de bord du frontend.

## Endpoint

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/api/dashboard/stats/` | Statistiques agrégées de l'utilisateur connecté |

**Authentification** : JWT requis (`IsAuthenticated`).
**Isolation** : toutes les agrégations filtrent sur `utilisateur=request.user`.

## Format de réponse

```json
{
  "status": "success",
  "data": {
    "monthly_revenue": [
      {"month": "Jan", "total": "1500.00"},
      {"month": "Fév", "total": "0"},
      ...
    ],
    "monthly_profit": "2400.00",
    "pending_total": "5800.00",
    "upcoming_deadlines": [
      {
        "id": 12,
        "numero": "FAC-2026-005",
        "client": "ACME SAS",
        "date": "2026-05-03",
        "statut": "ENVOYEE",
        "type": "facture"
      },
      {
        "id": 7,
        "numero": "DEV-2026-009",
        "client": "Globex",
        "date": "2026-05-12",
        "statut": "ENVOYE",
        "type": "devis"
      }
    ],
    "last_transactions": [
      {
        "id": 21,
        "numero": "FAC-2026-004",
        "client": "Initech",
        "updated_at": "2026-04-25T14:32:11Z",
        "total_ttc": "1200.00"
      }
    ]
  }
}
```

## Détail des champs

### `monthly_revenue`

Chiffre d'affaires mensuel (factures `PAYEE`) de l'**année courante**, regroupé par mois sur `date_emission`.

- Toujours 12 entrées (Jan → Déc), même si un mois est vide (`total: "0"`).
- Libellés : `Jan, Fév, Mar, Avr, Mai, Jun, Jul, Aoû, Sep, Oct, Nov, Déc`.

### `monthly_profit`

Somme `total_ttc` des factures `PAYEE` du **mois courant** uniquement.

### `pending_total`

Somme `total_ttc` des éléments « en attente » de l'utilisateur :

- Devis avec statut `ACCEPTE`
- Factures avec statut `ENVOYEE` ou `EN_RETARD`

Aucune dépendance à la date du jour : à base de données identique, deux clients voient la même valeur.

### `upcoming_deadlines`

Les 10 prochaines échéances **à venir** (date `>= aujourd'hui`), triées par date ascendante (la plus proche en premier).

Sources :
- Factures avec statut `ENVOYEE` et `date_echeance >= aujourd'hui`
- Devis avec statut `ENVOYE` et `date_validite >= aujourd'hui`

Les factures `EN_RETARD` ne sont **pas** incluses (par définition leur échéance est passée).

Champ `type` : `"facture"` ou `"devis"`. Champ `date` : `date_echeance` pour une facture, `date_validite` pour un devis.

### `last_transactions`

Les 10 dernières factures `PAYEE` triées par `updated_at` décroissant (plus récente en premier).

## Codes d'erreur

| Code | Cas |
|---|---|
| `200 OK` | Succès |
| `401 Unauthorized` | JWT manquant ou invalide |

## Implémentation

| Fichier | Rôle |
|---|---|
| [dashboard/views.py](../dashboard/views.py) | `DashboardStatsView` (APIView) — agrège les 5 métriques |
| [dashboard/urls.py](../dashboard/urls.py) | Route `dashboard/stats/` |

Les agrégations utilisent `Sum`, `ExtractMonth` et `select_related('client')` pour limiter le nombre de requêtes SQL. Les limites de liste (`upcoming_deadlines`, `last_transactions`) sont définies par les constantes `DEADLINES_LIMIT` et `TRANSACTIONS_LIMIT` (10 par défaut).
