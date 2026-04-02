# Prompt pour Claude Code — Setup Frontend React

Copie ce prompt dans Claude Code depuis ton projet frontend React.

---

## Le prompt

```
Je veux connecter mon frontend React (TypeScript) a mon API backend Django REST.

## Stack frontend
- React + TypeScript
- Axios pour les requetes HTTP
- React Hook Form pour les formulaires (avec useFieldArray pour les lignes dynamiques devis/factures)

## API Backend

Base URL : `http://localhost:8001/api`

### Format des reponses (JSend)

Toutes les reponses sont wrappees :
- Succes : `{ "status": "success", "data": { ... } }`
- Erreur validation (400) : `{ "status": "fail", "data": { "champ": ["message erreur"] } }`
- Erreur serveur (500) : `{ "status": "error", "message": "..." }`

Les donnees utiles sont toujours dans `response.data.data`.

### Authentification JWT

- Login : `POST /api/auth/login/` → body `{ email, password }` → retourne `{ access, refresh, user }`
- Register : `POST /api/auth/register/` → body `{ email, username, password, password_confirm, first_name, last_name, company_name?, siret?, address?, postal_code?, city?, phone? }`
- Refresh : `POST /api/auth/token/refresh/` → body `{ refresh }` → retourne `{ access, refresh }`
- Logout : `POST /api/auth/logout/` (auth) → body `{ refresh }`
- Me : `GET /api/auth/me/` (auth) → retourne user + configuration
- Profile : `GET|PATCH /api/auth/profile/` (auth) → champs user modifiables
- Configuration : `GET|PATCH /api/auth/configuration/` (auth) → `{ next_quote_number, next_invoice_number, quote_prefix, invoice_prefix, payment_deadline_days, quote_validity_days }`

Tokens : access valide 1h, refresh valide 7j, rotation activee.

### Endpoints CRUD

Tous les endpoints ci-dessous necessitent le header `Authorization: Bearer <access_token>`.
Tous sont pagines (20/page) : `{ count, next, previous, results: [...] }`.

#### Clients — `/api/clients/`

CRUD standard (GET list, GET detail, POST, PATCH, DELETE).
Filtres : `?search=X&ordering=X`
Recherche (`search`) : dans `raison_sociale`, `contact_nom`, `email`, `contact_email`.

Champs : `id, raison_sociale (requis, unique par user), siret, email, telephone, contact_nom, contact_email, contact_telephone, notes, adresses[], created_at, updated_at`

Les adresses sont imbriquees dans le client. Envoyer `adresses` dans un POST/PATCH remplace toutes les adresses.

Adresse : `{ type: "SIEGE"|"FACTURATION"|"LIVRAISON", ligne1 (requis), ligne2, code_postal (requis), ville (requis), pays (defaut "France") }`

Endpoint adresses standalone : `/api/adresses/` (CRUD, filtrage par `?client_id=X`)

#### Services — `/api/services/`

CRUD standard.

Champs : `id, label (requis), description, unit_price_excl_tax (requis, decimal string), unit: "heure"|"jour"|"forfait", taux_tva: "20.00"|"10.00"|"5.50"|"0.00", created_at, updated_at`

#### Devis — `/api/quotes/`

CRUD + action custom.
Filtres : `?statut=X&client_id=X&search=X&ordering=X` (search : `numero`, `objet`, `client.raison_sociale`, `client.contact_nom`, `client.email`)

Champs lecture : `id, utilisateur, client (objet complet), numero (auto), date_emission, date_validite (auto si vide), statut, objet, notes, total_ht (auto), total_tva (auto), total_ttc (auto), lignes[], historique[], created_at, updated_at`

Champs ecriture : `client_id (requis, write-only, non modifiable apres creation), date_emission, date_validite, objet, notes, lignes[]`

Ligne devis : `{ ordre, libelle (requis), description, quantite (decimal), unite, prix_unitaire_ht (requis, decimal), taux_tva (decimal) }` — `montant_ht` est calcule cote serveur.

Statuts : BROUILLON → ENVOYE → ACCEPTE / REFUSE / EXPIRE
Changement statut : `POST /api/quotes/{id}/changer_statut/` → body `{ statut }`

Regles : seuls les BROUILLON sont modifiables/supprimables. Envoyer `lignes` remplace toutes les lignes.

#### Factures — `/api/invoices/`

CRUD + actions custom.
Filtres : `?client=X&statut=X&devis_origine=X&date_emission_after=X&date_emission_before=X&date_echeance_after=X&date_echeance_before=X&search=X&ordering=X` (search : `numero`, `objet`, `client.raison_sociale`, `client.contact_nom`, `client.email`)

Champs lecture : `id, utilisateur, client (objet), devis_origine, numero (genere au passage BROUILLON→ENVOYEE), date_emission, date_echeance (auto si vide), statut, objet, notes, total_ht (auto), total_tva (auto), total_ttc (auto), lignes[], historique[], created_at, updated_at`

Champs ecriture : `client_id (requis, write-only, non modifiable), date_emission, date_echeance, objet, notes, lignes[]`

Ligne facture : memes champs que devis + `id` optionnel (pour identifier les lignes existantes lors d'un update).

Sync des lignes en update : lignes avec `id` → update, sans `id` → create, absentes du payload → delete.

Statuts : BROUILLON → ENVOYEE → PAYEE ou EN_RETARD → PAYEE
Changement statut : `POST /api/invoices/{id}/changer_statut/` → body `{ statut }`

Conversion devis→facture : `POST /api/invoices/from-devis/` → body `{ devis_id }` → cree facture ENVOYEE avec numero, copie les lignes, passe le devis en ACCEPTE.

Telecharger PDF : `GET /api/invoices/{id}/pdf/` → reponse binaire (blob). Si la facture est en BROUILLON, elle passe automatiquement en ENVOYEE (numero genere + historique cree).

Regles : seuls les BROUILLON sont modifiables/supprimables. Au moins 1 ligne requise. date_echeance >= date_emission.

## Ce que je veux que tu generes

### 1. Instance Axios centralisee (`src/api/api.ts`)
- baseURL configuree
- Intercepteur request : injecter le Bearer token depuis localStorage
- Intercepteur response : refresh automatique sur 401 (avec file d'attente pour les requetes concurrentes), deconnexion si le refresh echoue
- Ne pas tenter de refresh sur les routes `/auth/login` et `/auth/token/refresh`

### 2. Types TypeScript (`src/api/types/`)
Un fichier par entite avec tous les types (lecture ET ecriture) :
- `src/api/types/index.ts` — types partages : ApiError, PaginatedResponse<T>
- `src/api/types/auth.ts` — User, UserConfiguration, LoginRequest, RegisterRequest, AuthResponse, ProfileUpdateRequest, ConfigurationUpdateRequest
- `src/api/types/client.ts` — Client, Address, AddressType, ClientInput, AddressInput
- `src/api/types/service.ts` — Service, ServiceUnit, VatRate, ServiceInput
- `src/api/types/quote.ts` — Quote, QuoteLine, QuoteHistory, QuoteStatus, QuoteInput, QuoteLineInput
- `src/api/types/invoice.ts` — Invoice, InvoiceLine, InvoiceHistory, InvoiceStatus, InvoiceInput, InvoiceLineInput

Les decimaux de l'API sont renvoyes comme des strings en JSON (DRF). Les types doivent refleter ca.

### 3. Fonctions API (`src/api/`)
Un fichier par module avec des fonctions async qui appellent l'instance Axios et retournent les donnees typees (pas la reponse Axios brute) :
- `src/api/auth.ts` — login, register, logout, refreshToken, getCurrentUser, getProfile, updateProfile, getConfiguration, updateConfiguration
- `src/api/clients.ts` — getClients, getClient, createClient, updateClient, deleteClient, getAddresses, createAddress, updateAddress, deleteAddress
- `src/api/services.ts` — getServices, getService, createService, updateService, deleteService
- `src/api/quotes.ts` — getQuotes (avec filtres), getQuote, createQuote, updateQuote, deleteQuote, changeQuoteStatus
- `src/api/invoices.ts` — getInvoices (avec filtres), getInvoice, createInvoice, updateInvoice, deleteInvoice, changeInvoiceStatus, createInvoiceFromQuote, downloadInvoicePdf

Pour le PDF, creer un blob et declencher le telechargement navigateur.

### 4. Helper erreurs formulaires (`src/api/handleFormErrors.ts`)
Une fonction reutilisable qui prend une erreur Axios et un `setError` de React Hook Form, et mappe les erreurs JSend `fail` sur les champs du formulaire. Retourne un message d'erreur globale si c'est une erreur serveur.

Ne genere PAS de composants React, pas de pages, pas de routing, pas de context/store. Uniquement la couche API (types + fonctions + axios + helper erreurs).
```
