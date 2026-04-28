import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserConfiguration
from clients.models import Client, Address
from services.models import Service
from quotes.models import Quote, QuoteLine, QuoteHistory
from invoices.models import Invoice, InvoiceLine, InvoiceHistory


# ──────────────────────────────────────────────
# Données statiques
# ──────────────────────────────────────────────

USERS_DATA = [
    {
        "first_name": "Marie", "last_name": "Dupont",
        "email": "mariedupont@email.com", "password": "Marie123!",
        "company_name": "Marie Dupont Consulting", "siret": "81234567890123",
        "address": "15 Rue de Rivoli", "postal_code": "75001", "city": "Paris",
        "phone": "01 42 33 12 45",
    },
    {
        "first_name": "Thomas", "last_name": "Bernard",
        "email": "thomasbernard@email.com", "password": "Thomas123!",
        "company_name": "TB Developpement", "siret": "82345678901234",
        "address": "8 Rue de la Republique", "postal_code": "69001", "city": "Lyon",
        "phone": "04 72 10 25 30",
    },
    {
        "first_name": "Sophie", "last_name": "Martin",
        "email": "sophiemartin@email.com", "password": "Sophie123!",
        "company_name": "SM Design Studio", "siret": "83456789012345",
        "address": "22 Cours de l'Intendance", "postal_code": "33000", "city": "Bordeaux",
        "phone": "05 56 44 18 92",
    },
    {
        "first_name": "Lucas", "last_name": "Petit",
        "email": "lucaspetit@email.com", "password": "Lucas123!",
        "company_name": "LP Digital", "siret": "84567890123456",
        "address": "5 Place du Capitole", "postal_code": "31000", "city": "Toulouse",
        "phone": "05 61 22 33 44",
    },
]

FRENCH_COMPANIES = [
    "Groupe Duval", "Nextera Solutions", "Bretagne Logistique", "Provence Immobilier",
    "Normandie BTP", "Loire Consulting", "Alsace Technologies", "Rhone Conseil",
    "Cabinet Moreau", "Lefebvre et Fils", "Maison Gauthier", "Agence Rousseau",
    "Industries Mercier", "Atelier Lambert", "Societe Girard", "Transport Bonnet",
    "Boulangerie Dupuis", "Garage Michel", "Clinique Fontaine", "Librairie Chevalier",
    "Editions du Soleil", "Vignobles de France", "Hotel Le Parisien", "Restaurant Chez Jules",
    "Pharmacie Centrale", "Optique Martin", "Jardinerie Verte", "Fleuriste Beaumont",
    "Cabinet Perrin", "Electricite Simon", "Plomberie Leroy", "Menuiserie Roux",
    "Carrosserie Blanc", "Informatique Plus", "Web Factory", "Data Solutions France",
    "Cloud Nine SAS", "Pixel Parfait", "Studio Creatif", "Media Vision",
    "Ecole Montessori Lumiere", "Centre Sportif Olympe", "Spa Bien-Etre", "Traiteur Gourmet",
    "Boucherie Tradition", "Fromagerie Saveurs", "Cave du Terroir", "Patisserie Delice",
    "Securite Globale", "Nettoyage Express", "Demenagement Rapide", "Location Facile",
    "Imprimerie Moderne", "Publicite Horizon", "Evenements Prestige", "Formation Pro",
    "Architectes Reunis", "Bureau d'Etudes Sigma", "Geometre Expert Ville",
    "Assurances Tranquille", "Banque Regionale", "Comptabilite Plus", "Avocats Associes",
    "Notaire Legrand", "Agence Immobiliere du Parc", "Decorateur Interieur Chic",
    "Auto-Ecole Conduite", "Pressing Minute", "Coiffure Elegance", "Opticien du Centre",
    "Veterinaire des Champs", "Creche Les Petits Pas", "Garage Auto Premium",
    "Paysagiste Nature", "Serrurerie Securite", "Couvreur Toiture", "Peinture et Deco",
    "Chauffage Confort", "Climatisation Fraicheur", "Ascenseurs Montee",
    "Renovation Habitat", "Isolation Thermique Pro", "Energies Vertes",
    "Ferme Bio du Val", "Cooperative Agricole Sud", "Elevage des Monts",
    "Peche et Marine", "Textile Mode Paris", "Bijouterie Eclat",
    "Horlogerie Precision", "Musique et Sons", "Sport Extreme",
    "Voyage Evasion", "Camping Nature", "Ski Montagne Plus",
]

FRENCH_ADDRESSES = [
    ("12 Rue de la Republique", "75001", "Paris"),
    ("45 Avenue des Champs-Elysees", "75008", "Paris"),
    ("8 Boulevard Haussmann", "75009", "Paris"),
    ("23 Rue du Commerce", "75015", "Paris"),
    ("3 Place de la Bastille", "75004", "Paris"),
    ("17 Rue Oberkampf", "75011", "Paris"),
    ("56 Avenue de Saxe", "69006", "Lyon"),
    ("14 Rue de la Part-Dieu", "69003", "Lyon"),
    ("29 Cours Lafayette", "69006", "Lyon"),
    ("7 Place Bellecour", "69002", "Lyon"),
    ("33 Rue Paradis", "13001", "Marseille"),
    ("18 Boulevard de la Canebiere", "13001", "Marseille"),
    ("5 Rue Saint-Ferreol", "13006", "Marseille"),
    ("42 Cours Mirabeau", "13100", "Aix-en-Provence"),
    ("11 Rue Sainte-Catherine", "33000", "Bordeaux"),
    ("26 Cours Victor Hugo", "33000", "Bordeaux"),
    ("9 Place de la Bourse", "33000", "Bordeaux"),
    ("15 Rue Alsace-Lorraine", "31000", "Toulouse"),
    ("37 Place du Capitole", "31000", "Toulouse"),
    ("20 Rue de Metz", "31000", "Toulouse"),
    ("6 Rue de la Monnaie", "59000", "Lille"),
    ("31 Rue Faidherbe", "59000", "Lille"),
    ("24 Grand Place", "59000", "Lille"),
    ("13 Rue du Vieux Marche", "67000", "Strasbourg"),
    ("48 Quai des Bateliers", "67000", "Strasbourg"),
    ("2 Place Kleber", "67000", "Strasbourg"),
    ("19 Rue Marechal Joffre", "06000", "Nice"),
    ("35 Promenade des Anglais", "06000", "Nice"),
    ("10 Rue de Siam", "29200", "Brest"),
    ("27 Quai de la Fosse", "44000", "Nantes"),
    ("4 Place Graslin", "44000", "Nantes"),
    ("16 Rue Le Bastard", "35000", "Rennes"),
    ("22 Place de la Mairie", "35000", "Rennes"),
    ("38 Boulevard Gambetta", "34000", "Montpellier"),
    ("21 Rue de la Loge", "34000", "Montpellier"),
    ("50 Avenue Jean Jaures", "42000", "Saint-Etienne"),
    ("14 Rue Nationale", "37000", "Tours"),
    ("8 Place du Ralliement", "49000", "Angers"),
    ("30 Rue de la Liberte", "21000", "Dijon"),
    ("11 Place Stanislas", "54000", "Nancy"),
]

FRENCH_FIRST_NAMES = [
    "Pierre", "Jean", "Marc", "Philippe", "Alain", "Patrick", "Michel",
    "Francois", "Jacques", "Nicolas", "Laurent", "Christophe", "Stephane",
    "Nathalie", "Isabelle", "Catherine", "Sylvie", "Valerie", "Christine",
    "Sandrine", "Aurelie", "Cecile", "Emilie", "Delphine", "Caroline",
    "Antoine", "Benoit", "Damien", "Etienne", "Fabien", "Guillaume",
    "Hugo", "Julien", "Kevin", "Mathieu", "Olivier", "Quentin", "Romain",
]

FRENCH_LAST_NAMES = [
    "Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand",
    "Dubois", "Moreau", "Laurent", "Simon", "Michel", "Lefevre", "Leroy",
    "Roux", "David", "Bertrand", "Morel", "Fournier", "Girard", "Bonnet",
    "Dupont", "Lambert", "Fontaine", "Rousseau", "Vincent", "Muller",
    "Lefevre", "Faure", "Andre", "Mercier", "Blanc", "Guerin", "Boyer",
    "Garnier", "Chevalier", "Francois", "Legrand", "Gauthier", "Garcia",
]

SERVICES_CATALOG = [
    {"label": "Developpement web", "description": "Developpement de sites et applications web", "price": Decimal("450.00"), "unit": "jour", "tva": Decimal("20.00")},
    {"label": "Conseil technique", "description": "Conseil et accompagnement technique", "price": Decimal("120.00"), "unit": "heure", "tva": Decimal("20.00")},
    {"label": "Design UX/UI", "description": "Conception d'interfaces utilisateur", "price": Decimal("400.00"), "unit": "jour", "tva": Decimal("20.00")},
    {"label": "Formation", "description": "Formation professionnelle sur mesure", "price": Decimal("1200.00"), "unit": "forfait", "tva": Decimal("20.00")},
    {"label": "Audit de code", "description": "Revue et audit de qualite du code source", "price": Decimal("800.00"), "unit": "forfait", "tva": Decimal("20.00")},
    {"label": "Maintenance applicative", "description": "Maintenance corrective et evolutive", "price": Decimal("350.00"), "unit": "jour", "tva": Decimal("20.00")},
    {"label": "Redaction technique", "description": "Documentation technique et fonctionnelle", "price": Decimal("80.00"), "unit": "heure", "tva": Decimal("20.00")},
    {"label": "Developpement mobile", "description": "Developpement d'applications mobiles", "price": Decimal("500.00"), "unit": "jour", "tva": Decimal("20.00")},
    {"label": "Integration API", "description": "Integration de services tiers et APIs", "price": Decimal("420.00"), "unit": "jour", "tva": Decimal("20.00")},
    {"label": "SEO / Referencement", "description": "Optimisation pour les moteurs de recherche", "price": Decimal("600.00"), "unit": "forfait", "tva": Decimal("20.00")},
    {"label": "Administration systeme", "description": "Gestion et configuration de serveurs", "price": Decimal("100.00"), "unit": "heure", "tva": Decimal("20.00")},
    {"label": "Gestion de projet", "description": "Pilotage et coordination de projets IT", "price": Decimal("380.00"), "unit": "jour", "tva": Decimal("20.00")},
]

QUOTE_SUBJECTS = [
    "Refonte site web vitrine", "Developpement application mobile",
    "Audit de securite informatique", "Migration infrastructure cloud",
    "Developpement API REST", "Integration CRM Salesforce",
    "Mise en place CI/CD", "Refonte UX parcours client",
    "Developpement module e-commerce", "Formation equipe technique",
    "Maintenance annuelle", "Optimisation performances",
    "Creation charte graphique", "Mise en conformite RGPD",
    "Developpement intranet", "Refonte base de donnees",
    "Integration solution de paiement", "Developpement chatbot",
    "Mise en place monitoring", "Audit accessibilite web",
    "Creation landing pages", "Developpement tableau de bord",
    "Migration WordPress vers React", "Automatisation processus metier",
    "Mise en place ERP", "Developpement portail client",
]

NOTES_TEMPLATES = [
    "Projet prioritaire pour le client.",
    "Voir specifications detaillees en annexe.",
    "Livraison en deux phases.",
    "Le client souhaite un suivi hebdomadaire.",
    "",
    "",
    "",
]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def random_siret():
    return "".join([str(random.randint(0, 9)) for _ in range(14)])


def random_phone():
    prefix = random.choice(["01", "02", "03", "04", "05", "06", "07", "09"])
    digits = [f"{random.randint(0, 99):02d}" for _ in range(4)]
    return f"{prefix} {' '.join(digits)}"


def random_date_between(start, end):
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def make_datetime(d):
    """Convert a date to a timezone-aware datetime at a random business hour."""
    hour = random.randint(8, 18)
    minute = random.randint(0, 59)
    return timezone.make_aware(
        timezone.datetime(d.year, d.month, d.day, hour, minute, 0)
    )


def next_available_numero(prefix, year, model_class):
    """Find the next available number for a given prefix/year to avoid collisions."""
    existing = model_class.all_objects.filter(
        numero__startswith=f"{prefix}-{year}-"
    ).values_list("numero", flat=True)
    max_num = 0
    for n in existing:
        try:
            num = int(n.split("-")[-1])
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            pass
    return max_num + 1


# ──────────────────────────────────────────────
# Command
# ──────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed the database with realistic test data (4 users, clients, quotes, invoices)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help="Delete existing seed users and recreate all data",
        )

    def handle(self, *args, **options):
        seed_emails = [u["email"] for u in USERS_DATA]
        existing = User.objects.filter(email__in=seed_emails)

        if existing.exists() and not options["flush"]:
            self.stderr.write(self.style.ERROR(
                "Seed users already exist. Use --flush to delete and recreate."
            ))
            return

        with transaction.atomic():
            if options["flush"] and existing.exists():
                existing.delete()
                self.stdout.write(self.style.WARNING("Existing seed users deleted."))

            stats = {"users": 0, "clients": 0, "addresses": 0, "services": 0,
                     "quotes": 0, "quote_lines": 0, "invoices": 0, "invoice_lines": 0}

            for user_data in USERS_DATA:
                user, services = self._create_user_and_services(user_data)
                stats["users"] += 1
                stats["services"] += len(services)

                clients = self._create_clients(user)
                stats["clients"] += len(clients)
                stats["addresses"] += sum(c.adresses.count() for c in clients)

                accepted_quotes = []
                for client in clients:
                    q_accepted, q_count, ql_count = self._create_quotes(user, client, services)
                    accepted_quotes.extend(q_accepted)
                    stats["quotes"] += q_count
                    stats["quote_lines"] += ql_count

                for client in clients:
                    client_accepted = [q for q in accepted_quotes if q.client == client]
                    i_count, il_count = self._create_invoices(user, client, services, client_accepted)
                    stats["invoices"] += i_count
                    stats["invoice_lines"] += il_count

                # Update config counters
                config = UserConfiguration.objects.get(user=user)
                max_q = Quote.objects.filter(utilisateur=user).count()
                max_i = Invoice.objects.filter(utilisateur=user).exclude(numero__isnull=True).count()
                config.next_quote_number = max_q + 1
                config.next_invoice_number = max_i + 1
                config.save()

        self.stdout.write(self.style.SUCCESS(
            f"\nSeed complete!\n"
            f"  Users:         {stats['users']}\n"
            f"  Services:      {stats['services']}\n"
            f"  Clients:       {stats['clients']}\n"
            f"  Addresses:     {stats['addresses']}\n"
            f"  Quotes:        {stats['quotes']}\n"
            f"  Quote lines:   {stats['quote_lines']}\n"
            f"  Invoices:      {stats['invoices']}\n"
            f"  Invoice lines: {stats['invoice_lines']}\n"
        ))

    # ── User & Services ──

    def _create_user_and_services(self, data):
        user = User.objects.create_user(
            username=data["email"].split("@")[0],
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            company_name=data["company_name"],
            siret=data["siret"],
            address=data["address"],
            postal_code=data["postal_code"],
            city=data["city"],
            phone=data["phone"],
        )
        UserConfiguration.objects.create(user=user)

        catalog = random.sample(SERVICES_CATALOG, k=random.randint(3, 4))
        services = []
        for svc in catalog:
            factor = Decimal(str(round(random.uniform(0.85, 1.15), 2)))
            s = Service.objects.create(
                utilisateur=user,
                label=svc["label"],
                description=svc["description"],
                unit_price_excl_tax=(svc["price"] * factor).quantize(Decimal("0.01")),
                unit=svc["unit"],
                taux_tva=svc["tva"],
            )
            services.append(s)
        return user, services

    # ── Clients ──

    def _create_clients(self, user):
        count = random.randint(20, 50)
        company_names = random.sample(FRENCH_COMPANIES, k=min(count, len(FRENCH_COMPANIES)))
        clients = []

        for name in company_names:
            slug = name.lower().replace(" ", "").replace("'", "")[:20]
            client = Client.objects.create(
                utilisateur=user,
                raison_sociale=name,
                siret=random_siret() if random.random() > 0.3 else "",
                email=f"contact@{slug}.fr" if random.random() > 0.2 else "",
                telephone=random_phone() if random.random() > 0.3 else "",
                contact_nom=f"{random.choice(FRENCH_FIRST_NAMES)} {random.choice(FRENCH_LAST_NAMES)}",
                contact_email=f"{random.choice(FRENCH_FIRST_NAMES).lower()}.{random.choice(FRENCH_LAST_NAMES).lower()}@{slug}.fr" if random.random() > 0.3 else "",
                contact_telephone=random_phone() if random.random() > 0.4 else "",
                notes=random.choice(["Client fidele", "Nouveau client", "Recommande par un partenaire", "Prospect converti", ""]),
            )

            # Backdate client creation
            created = random_date_between(date(2024, 6, 1), date(2025, 12, 31))
            dt = make_datetime(created)
            Client.objects.filter(pk=client.pk).update(created_at=dt, updated_at=dt)

            # Always a SIEGE address
            addr_data = random.choice(FRENCH_ADDRESSES)
            Address.objects.create(
                client=client, type="SIEGE",
                ligne1=addr_data[0], code_postal=addr_data[1], ville=addr_data[2],
            )

            # Sometimes a FACTURATION address
            if random.random() > 0.6:
                addr_data2 = random.choice(FRENCH_ADDRESSES)
                Address.objects.create(
                    client=client, type="FACTURATION",
                    ligne1=addr_data2[0], code_postal=addr_data2[1], ville=addr_data2[2],
                )

            clients.append(client)

        return clients

    # ── Quotes ──

    def _create_quotes(self, user, client, services):
        count = random.choices([0, 1, 2, 3], weights=[30, 35, 25, 10])[0]
        accepted = []
        total_lines = 0

        for i in range(count):
            date_emission = random_date_between(date(2024, 9, 1), date(2026, 3, 15))
            date_validite = date_emission + timedelta(days=30)

            # Determine final status
            today = date(2026, 4, 2)
            if date_validite < today:
                statut = random.choices(
                    ["BROUILLON", "ENVOYE", "ACCEPTE", "REFUSE", "EXPIRE"],
                    weights=[5, 10, 45, 20, 20],
                )[0]
            else:
                statut = random.choices(
                    ["BROUILLON", "ENVOYE", "ACCEPTE", "REFUSE"],
                    weights=[15, 30, 40, 15],
                )[0]

            # Pre-generate numero (check existing to avoid collisions)
            config = UserConfiguration.objects.get(user=user)
            prefix = config.quote_prefix
            year = date_emission.year
            num = next_available_numero(prefix, year, Quote)
            numero = f"{prefix}-{year}-{num:03d}"

            quote = Quote(
                utilisateur=user,
                client=client,
                numero=numero,
                date_emission=date_emission,
                date_validite=date_validite,
                statut=statut,
                objet=random.choice(QUOTE_SUBJECTS),
                notes=random.choice(NOTES_TEMPLATES),
            )
            quote.save()

            # Create lines
            num_lines = random.randint(1, 4)
            line_services = random.choices(services, k=num_lines)
            for idx, svc in enumerate(line_services):
                if svc.unit == "heure":
                    qty = Decimal(str(random.randint(2, 20)))
                elif svc.unit == "jour":
                    qty = Decimal(str(random.randint(1, 15)))
                else:
                    qty = Decimal("1.00")

                QuoteLine(
                    devis=quote,
                    ordre=idx,
                    libelle=svc.label,
                    description=svc.description,
                    quantite=qty,
                    unite=svc.unit,
                    prix_unitaire_ht=svc.unit_price_excl_tax,
                    taux_tva=svc.taux_tva,
                    montant_ht=qty * svc.unit_price_excl_tax,
                ).save()
                total_lines += 1

            # Create status history with progressive dates
            dt_creation = make_datetime(date_emission)
            h1 = QuoteHistory.objects.create(
                devis=quote, ancien_statut=None, nouveau_statut="BROUILLON"
            )
            QuoteHistory.objects.filter(pk=h1.pk).update(created_at=dt_creation)

            if statut in ("ENVOYE", "ACCEPTE", "REFUSE", "EXPIRE"):
                dt_sent = make_datetime(date_emission + timedelta(days=random.randint(1, 3)))
                h2 = QuoteHistory.objects.create(
                    devis=quote, ancien_statut="BROUILLON", nouveau_statut="ENVOYE"
                )
                QuoteHistory.objects.filter(pk=h2.pk).update(created_at=dt_sent)

            if statut == "ACCEPTE":
                dt_accepted = make_datetime(date_emission + timedelta(days=random.randint(4, 14)))
                h3 = QuoteHistory.objects.create(
                    devis=quote, ancien_statut="ENVOYE", nouveau_statut="ACCEPTE"
                )
                QuoteHistory.objects.filter(pk=h3.pk).update(created_at=dt_accepted)
                accepted.append(quote)
            elif statut == "REFUSE":
                dt_refused = make_datetime(date_emission + timedelta(days=random.randint(5, 20)))
                h3 = QuoteHistory.objects.create(
                    devis=quote, ancien_statut="ENVOYE", nouveau_statut="REFUSE"
                )
                QuoteHistory.objects.filter(pk=h3.pk).update(created_at=dt_refused)
            elif statut == "EXPIRE":
                dt_expired = make_datetime(date_validite + timedelta(days=1))
                h3 = QuoteHistory.objects.create(
                    devis=quote, ancien_statut="ENVOYE", nouveau_statut="EXPIRE"
                )
                QuoteHistory.objects.filter(pk=h3.pk).update(created_at=dt_expired)

            # Backdate quote
            Quote.all_objects.filter(pk=quote.pk).update(
                created_at=dt_creation, updated_at=dt_creation
            )

        return accepted, count, total_lines

    # ── Invoices ──

    def _create_invoices(self, user, client, services, accepted_quotes):
        total_count = 0
        total_lines = 0

        # Invoices from accepted quotes (~70%)
        for quote in accepted_quotes:
            if random.random() > 0.7:
                continue

            # Check if this quote already has a linked invoice
            if hasattr(quote, 'facture') and Invoice.objects.filter(devis_origine=quote).exists():
                continue

            days_after = random.randint(2, 7)
            date_emission = quote.date_emission + timedelta(days=random.randint(5, 18))
            date_echeance = date_emission + timedelta(days=30)

            statut = random.choices(
                ["BROUILLON", "ENVOYEE", "PAYEE", "EN_RETARD"],
                weights=[5, 20, 55, 20],
            )[0]

            # Generate numero only for non-draft
            numero = None
            if statut != "BROUILLON":
                config = UserConfiguration.objects.get(user=user)
                prefix = config.invoice_prefix
                year = date_emission.year
                num = next_available_numero(prefix, year, Invoice)
                numero = f"{prefix}-{year}-{num:03d}"

            invoice = Invoice.objects.create(
                utilisateur=user,
                client=client,
                devis_origine=quote,
                numero=numero,
                date_emission=date_emission,
                date_echeance=date_echeance,
                statut=statut,
                objet=quote.objet,
                notes=quote.notes,
            )

            # Copy lines from quote
            for ql in quote.lignes.all():
                InvoiceLine(
                    facture=invoice,
                    ordre=ql.ordre,
                    libelle=ql.libelle,
                    description=ql.description,
                    quantite=ql.quantite,
                    unite=ql.unite,
                    prix_unitaire_ht=ql.prix_unitaire_ht,
                    taux_tva=ql.taux_tva,
                    montant_ht=ql.montant_ht,
                ).save()
                total_lines += 1

            self._create_invoice_history(invoice, date_emission)

            dt_creation = make_datetime(date_emission)
            Invoice.all_objects.filter(pk=invoice.pk).update(
                created_at=dt_creation, updated_at=dt_creation
            )
            total_count += 1

        # Standalone invoices (0-2 per client, but keep total 0-3)
        remaining = random.choices([0, 1, 2], weights=[50, 35, 15])[0]
        for _ in range(remaining):
            date_emission = random_date_between(date(2024, 9, 1), date(2026, 3, 15))
            date_echeance = date_emission + timedelta(days=30)

            statut = random.choices(
                ["BROUILLON", "ENVOYEE", "PAYEE", "EN_RETARD"],
                weights=[10, 25, 45, 20],
            )[0]

            numero = None
            if statut != "BROUILLON":
                config = UserConfiguration.objects.get(user=user)
                prefix = config.invoice_prefix
                year = date_emission.year
                num = next_available_numero(prefix, year, Invoice)
                numero = f"{prefix}-{year}-{num:03d}"

            invoice = Invoice.objects.create(
                utilisateur=user,
                client=client,
                numero=numero,
                date_emission=date_emission,
                date_echeance=date_echeance,
                statut=statut,
                objet=random.choice(QUOTE_SUBJECTS),
                notes=random.choice(NOTES_TEMPLATES),
            )

            num_lines = random.randint(1, 4)
            line_services = random.choices(services, k=num_lines)
            for idx, svc in enumerate(line_services):
                if svc.unit == "heure":
                    qty = Decimal(str(random.randint(2, 20)))
                elif svc.unit == "jour":
                    qty = Decimal(str(random.randint(1, 15)))
                else:
                    qty = Decimal("1.00")

                InvoiceLine(
                    facture=invoice,
                    ordre=idx,
                    libelle=svc.label,
                    description=svc.description,
                    quantite=qty,
                    unite=svc.unit,
                    prix_unitaire_ht=svc.unit_price_excl_tax,
                    taux_tva=svc.taux_tva,
                    montant_ht=qty * svc.unit_price_excl_tax,
                ).save()
                total_lines += 1

            self._create_invoice_history(invoice, date_emission)

            dt_creation = make_datetime(date_emission)
            Invoice.all_objects.filter(pk=invoice.pk).update(
                created_at=dt_creation, updated_at=dt_creation
            )
            total_count += 1

        return total_count, total_lines

    def _create_invoice_history(self, invoice, date_emission):
        dt_creation = make_datetime(date_emission)
        h1 = InvoiceHistory.objects.create(
            facture=invoice, ancien_statut=None, nouveau_statut="BROUILLON"
        )
        InvoiceHistory.objects.filter(pk=h1.pk).update(created_at=dt_creation)

        statut = invoice.statut

        if statut in ("ENVOYEE", "PAYEE", "EN_RETARD"):
            dt_sent = make_datetime(date_emission + timedelta(days=random.randint(1, 3)))
            h2 = InvoiceHistory.objects.create(
                facture=invoice, ancien_statut="BROUILLON", nouveau_statut="ENVOYEE"
            )
            InvoiceHistory.objects.filter(pk=h2.pk).update(created_at=dt_sent)

        if statut == "PAYEE":
            dt_paid = make_datetime(date_emission + timedelta(days=random.randint(10, 45)))
            h3 = InvoiceHistory.objects.create(
                facture=invoice, ancien_statut="ENVOYEE", nouveau_statut="PAYEE"
            )
            InvoiceHistory.objects.filter(pk=h3.pk).update(created_at=dt_paid)
        elif statut == "EN_RETARD":
            dt_late = make_datetime(invoice.date_echeance + timedelta(days=random.randint(1, 15)))
            h3 = InvoiceHistory.objects.create(
                facture=invoice, ancien_statut="ENVOYEE", nouveau_statut="EN_RETARD"
            )
            InvoiceHistory.objects.filter(pk=h3.pk).update(created_at=dt_late)
