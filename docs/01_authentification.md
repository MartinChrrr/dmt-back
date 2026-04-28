# Authentification

## Mécanisme

Authentification **JWT** (JSON Web Token) via le header HTTP :

```
Authorization: Bearer <access_token>
```

| Token | Durée de vie | Rotation |
|---|---|---|
| Access token | 1 heure | — |
| Refresh token | 7 jours | Oui (nouveau refresh token à chaque utilisation) |

L'ancien refresh token est automatiquement blacklisté après rotation.

## Claims personnalisés du JWT

Le token d'accès contient les claims supplémentaires suivants :

| Claim | Description |
|---|---|
| `user_id` | ID de l'utilisateur |
| `email` | Adresse email |
| `username` | Nom d'utilisateur |
| `company_name` | Nom de l'entreprise |

---

## Endpoints

### POST `/api/auth/register/` — Inscription

Crée un compte utilisateur et retourne les tokens JWT.
Une `UserConfiguration` avec les valeurs par défaut est automatiquement créée.

**Permissions :** Aucune (accès public)

**Corps de la requête :**

| Champ | Type | Requis | Description |
|---|---|---|---|
| `email` | string | oui | Adresse email (unique) |
| `username` | string | oui | Nom d'utilisateur (unique) |
| `password` | string | oui | Mot de passe (validé par Django) |
| `password_confirm` | string | oui | Confirmation du mot de passe |
| `first_name` | string | oui | Prénom |
| `last_name` | string | oui | Nom |
| `company_name` | string | non | Nom de l'entreprise |
| `siret` | string | non | Numéro SIRET (14 caractères) |
| `address` | string | non | Adresse |
| `postal_code` | string | non | Code postal |
| `city` | string | non | Ville |
| `phone` | string | non | Téléphone |

**Exemple de requête :**

```json
{
  "email": "jean.dupont@example.com",
  "username": "jdupont",
  "password": "MonMotDePasse123!",
  "password_confirm": "MonMotDePasse123!",
  "first_name": "Jean",
  "last_name": "Dupont",
  "company_name": "Dupont SARL",
  "siret": "12345678901234"
}
```

**Réponse succès (201) :**

```json
{
  "status": "success",
  "data": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": {
      "id": 1,
      "email": "jean.dupont@example.com",
      "username": "jdupont",
      "first_name": "Jean",
      "last_name": "Dupont",
      "company_name": "Dupont SARL",
      "siret": "12345678901234",
      "address": "",
      "postal_code": "",
      "city": "",
      "phone": "",
      "configuration": {
        "next_quote_number": 1,
        "next_invoice_number": 1,
        "quote_prefix": "DEV",
        "invoice_prefix": "FAC",
        "payment_deadline_days": 30,
        "quote_validity_days": 30
      },
      "date_joined": "2025-01-15 10:30:00"
    }
  }
}
```

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 400 | Email déjà utilisé |
| 400 | Mots de passe non identiques |
| 400 | Mot de passe trop simple (validation Django) |
| 400 | Champs requis manquants (`email`, `first_name`, `last_name`) |

---

### POST `/api/auth/login/` — Connexion

Retourne une paire de tokens JWT.

**Permissions :** Aucune (accès public)

**Corps de la requête :**

| Champ | Type | Requis | Description |
|---|---|---|---|
| `email` | string | oui | Adresse email |
| `password` | string | oui | Mot de passe |

**Exemple de requête :**

```json
{
  "email": "jean.dupont@example.com",
  "password": "MonMotDePasse123!"
}
```

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": {
      "id": 1,
      "email": "jean.dupont@example.com",
      "username": "jdupont",
      "first_name": "Jean",
      "last_name": "Dupont",
      "company_name": "Dupont SARL",
      "siret": "12345678901234",
      "address": "",
      "postal_code": "",
      "city": "",
      "phone": "",
      "configuration": { ... },
      "date_joined": "2025-01-15 10:30:00"
    }
  }
}
```

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 401 | Identifiants incorrects |
| 401 | Utilisateur inexistant |

---

### POST `/api/auth/token/refresh/` — Rafraîchissement du token

Génère un nouveau access token (et un nouveau refresh token par rotation).

**Permissions :** Aucune (accès public)

**Corps de la requête :**

| Champ | Type | Requis | Description |
|---|---|---|---|
| `refresh` | string | oui | Refresh token valide |

**Exemple de requête :**

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}
```

**Erreurs possibles :**

| Code HTTP | Cause |
|---|---|
| 401 | Token invalide ou expiré |
| 401 | Token déjà blacklisté |

---

### POST `/api/auth/logout/` — Déconnexion

Blackliste le refresh token pour invalider la session.

**Permissions :** Authentifié

**Corps de la requête :**

| Champ | Type | Requis | Description |
|---|---|---|---|
| `refresh` | string | oui | Refresh token à invalider |

**Exemple de requête :**

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "message": "Logout successful"
  }
}
```

---

### GET `/api/auth/me/` — Utilisateur courant

Retourne les informations de l'utilisateur connecté.

**Permissions :** Authentifié

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "id": 1,
    "email": "jean.dupont@example.com",
    "username": "jdupont",
    "first_name": "Jean",
    "last_name": "Dupont",
    "company_name": "Dupont SARL",
    "siret": "12345678901234",
    "address": "10 rue de la Paix",
    "postal_code": "75001",
    "city": "Paris",
    "phone": "01 23 45 67 89",
    "configuration": {
      "next_quote_number": 5,
      "next_invoice_number": 3,
      "quote_prefix": "DEV",
      "invoice_prefix": "FAC",
      "payment_deadline_days": 30,
      "quote_validity_days": 30
    },
    "date_joined": "2025-01-15 10:30:00"
  }
}
```

---

### GET/PUT/PATCH `/api/auth/profile/` — Profil utilisateur

Consulte ou modifie le profil de l'utilisateur connecté.

**Permissions :** Authentifié

**Champs modifiables :**

| Champ | Type | Description |
|---|---|---|
| `email` | string | Adresse email |
| `username` | string | Nom d'utilisateur |
| `first_name` | string | Prénom |
| `last_name` | string | Nom |
| `company_name` | string | Nom de l'entreprise |
| `siret` | string | Numéro SIRET |
| `address` | string | Adresse |
| `postal_code` | string | Code postal |
| `city` | string | Ville |
| `phone` | string | Téléphone |

**Exemple PATCH :**

```json
{
  "company_name": "Nouvelle Raison Sociale",
  "phone": "06 12 34 56 78"
}
```

---

### GET/PUT/PATCH `/api/auth/configuration/` — Configuration utilisateur

Consulte ou modifie la configuration de numérotation et délais.

**Permissions :** Authentifié

**Champs modifiables :**

| Champ | Type | Défaut | Description |
|---|---|---|---|
| `next_quote_number` | integer | `1` | Prochain numéro séquentiel de devis |
| `next_invoice_number` | integer | `1` | Prochain numéro séquentiel de facture |
| `quote_prefix` | string | `DEV` | Préfixe de numérotation des devis |
| `invoice_prefix` | string | `FAC` | Préfixe de numérotation des factures |
| `payment_deadline_days` | integer | `30` | Délai de paiement par défaut (jours) |
| `quote_validity_days` | integer | `30` | Validité par défaut des devis (jours) |

**Exemple PATCH :**

```json
{
  "quote_prefix": "D",
  "invoice_prefix": "F",
  "payment_deadline_days": 60
}
```

**Réponse succès (200) :**

```json
{
  "status": "success",
  "data": {
    "next_quote_number": 5,
    "next_invoice_number": 3,
    "quote_prefix": "D",
    "invoice_prefix": "F",
    "payment_deadline_days": 60,
    "quote_validity_days": 30
  }
}
```
