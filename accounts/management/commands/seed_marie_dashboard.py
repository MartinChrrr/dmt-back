import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, UserConfiguration
from clients.models import Client
from services.models import Service
from quotes.models import Quote, QuoteLine, QuoteHistory
from invoices.models import Invoice, InvoiceLine, InvoiceHistory

# Reuse helpers from the main seed command
from accounts.management.commands.seed_data import (
    make_datetime,
    next_available_numero,
)


MARIE_EMAIL = "mariedupont@email.com"
DEMO_MARKER = "[DEMO]"

# "Today" of the presentation
TODAY = date(2026, 6, 23)
YEAR = TODAY.year


class Command(BaseCommand):
    help = (
        "Add demo dashboard data for Marie Dupont: paid invoices for the "
        "current month, upcoming invoice/quote deadlines, and recent "
        "transactions. Re-runnable (clears previous [DEMO] rows first)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep", action="store_true",
            help="Do not delete previously created [DEMO] rows before seeding.",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email=MARIE_EMAIL)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                f"User {MARIE_EMAIL} not found. Run `seed_data` first."
            ))
            return

        clients = list(Client.objects.filter(utilisateur=user))
        services = list(Service.objects.filter(utilisateur=user))
        if not clients or not services:
            self.stderr.write(self.style.ERROR(
                "Marie has no clients or services. Run `seed_data` first."
            ))
            return

        random.seed(2026)

        with transaction.atomic():
            if not options["keep"]:
                self._purge_previous(user)

            stats = {"paid": 0, "deadlines_inv": 0, "deadlines_quote": 0}

            # 1. Paid invoices this month → Bénéfice/Entrée mois, chart, transactions
            paid_specs = [
                (date(YEAR, 6, 3),  date(YEAR, 6, 18), "Refonte site web vitrine"),
                (date(YEAR, 6, 9),  date(YEAR, 6, 20), "Developpement application mobile"),
                (date(YEAR, 6, 12), date(YEAR, 6, 22), "Maintenance applicative"),
                (date(YEAR, 6, 16), date(YEAR, 6, 23), "Integration API"),
            ]
            for emission, paid_on, objet in paid_specs:
                self._create_invoice(
                    user, random.choice(clients), services,
                    statut=Invoice.STATUT_PAYEE,
                    date_emission=emission,
                    date_echeance=emission + timedelta(days=30),
                    objet=objet,
                    paid_on=paid_on,
                )
                stats["paid"] += 1

            # 2. Sent invoices with upcoming due dates → Deadlines + Entrées en attente
            deadline_inv_specs = [
                (date(YEAR, 6, 10), date(YEAR, 7, 10), "Developpement portail client"),
                (date(YEAR, 6, 15), date(YEAR, 7, 25), "Audit de securite informatique"),
                (date(YEAR, 6, 18), date(YEAR, 8, 5),  "Migration infrastructure cloud"),
                (date(YEAR, 6, 20), date(YEAR, 8, 20), "Formation equipe technique"),
            ]
            for emission, echeance, objet in deadline_inv_specs:
                self._create_invoice(
                    user, random.choice(clients), services,
                    statut=Invoice.STATUT_ENVOYEE,
                    date_emission=emission,
                    date_echeance=echeance,
                    objet=objet,
                    paid_on=None,
                )
                stats["deadlines_inv"] += 1

            # 3. Sent quotes with upcoming validity dates → Deadlines à venir
            deadline_quote_specs = [
                (date(YEAR, 6, 14), date(YEAR, 7, 14), "Creation charte graphique"),
                (date(YEAR, 6, 19), date(YEAR, 7, 31), "Mise en place CI/CD"),
            ]
            for emission, validite, objet in deadline_quote_specs:
                self._create_quote(
                    user, random.choice(clients), services,
                    date_emission=emission,
                    date_validite=validite,
                    objet=objet,
                )
                stats["deadlines_quote"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDemo dashboard data for Marie Dupont created!\n"
            f"  Paid invoices (June):     {stats['paid']}\n"
            f"  Sent invoices (deadlines):{stats['deadlines_inv']}\n"
            f"  Sent quotes (deadlines):  {stats['deadlines_quote']}\n"
        ))

    # ── Cleanup ──

    def _purge_previous(self, user):
        invs = Invoice.all_objects.filter(utilisateur=user, notes__contains=DEMO_MARKER)
        n_inv = invs.count()
        for inv in invs:
            InvoiceLine.objects.filter(facture=inv).delete()
            InvoiceHistory.all_objects.filter(facture=inv).delete()
            # Hard delete (bypass the draft-only soft delete) — demo rows only
            Invoice.all_objects.filter(pk=inv.pk).delete()

        quotes = Quote.all_objects.filter(utilisateur=user, notes__contains=DEMO_MARKER)
        n_q = quotes.count()
        for q in quotes:
            QuoteLine.all_objects.filter(devis=q).delete()
            QuoteHistory.all_objects.filter(devis=q).delete()
            Quote.all_objects.filter(pk=q.pk).delete()

        if n_inv or n_q:
            self.stdout.write(self.style.WARNING(
                f"Removed previous demo rows: {n_inv} invoices, {n_q} quotes."
            ))

    # ── Builders ──

    def _add_lines(self, parent, services, line_model, fk_name):
        num_lines = random.randint(1, 3)
        for idx, svc in enumerate(random.choices(services, k=num_lines)):
            if svc.unit == "heure":
                qty = Decimal(str(random.randint(4, 20)))
            elif svc.unit == "jour":
                qty = Decimal(str(random.randint(2, 12)))
            else:
                qty = Decimal("1.00")
            line_model(**{
                fk_name: parent,
                "ordre": idx,
                "libelle": svc.label,
                "description": svc.description,
                "quantite": qty,
                "unite": svc.unit,
                "prix_unitaire_ht": svc.unit_price_excl_tax,
                "taux_tva": svc.taux_tva,
                "montant_ht": qty * svc.unit_price_excl_tax,
            }).save()

    def _create_invoice(self, user, client, services, *, statut,
                        date_emission, date_echeance, objet, paid_on):
        config = UserConfiguration.objects.get(user=user)
        prefix = config.invoice_prefix
        num = next_available_numero(prefix, date_emission.year, Invoice)
        numero = f"{prefix}-{date_emission.year}-{num:03d}"

        invoice = Invoice.objects.create(
            utilisateur=user,
            client=client,
            numero=numero,
            date_emission=date_emission,
            date_echeance=date_echeance,
            statut=statut,
            objet=objet,
            notes=DEMO_MARKER,
        )
        self._add_lines(invoice, services, InvoiceLine, "facture")

        # History
        dt_creation = make_datetime(date_emission)
        h1 = InvoiceHistory.objects.create(
            facture=invoice, ancien_statut=None, nouveau_statut="BROUILLON")
        InvoiceHistory.objects.filter(pk=h1.pk).update(created_at=dt_creation)

        dt_sent = make_datetime(date_emission + timedelta(days=1))
        h2 = InvoiceHistory.objects.create(
            facture=invoice, ancien_statut="BROUILLON", nouveau_statut="ENVOYEE")
        InvoiceHistory.objects.filter(pk=h2.pk).update(created_at=dt_sent)

        updated_dt = dt_sent
        if statut == Invoice.STATUT_PAYEE and paid_on:
            dt_paid = make_datetime(paid_on)
            h3 = InvoiceHistory.objects.create(
                facture=invoice, ancien_statut="ENVOYEE", nouveau_statut="PAYEE")
            InvoiceHistory.objects.filter(pk=h3.pk).update(created_at=dt_paid)
            updated_dt = dt_paid

        # Backdate created_at, set updated_at so transactions order looks natural
        Invoice.all_objects.filter(pk=invoice.pk).update(
            created_at=dt_creation, updated_at=updated_dt)

        # Keep config counter ahead
        config.next_invoice_number = max(config.next_invoice_number, num + 1)
        config.save(update_fields=["next_invoice_number"])
        return invoice

    def _create_quote(self, user, client, services, *,
                      date_emission, date_validite, objet):
        config = UserConfiguration.objects.get(user=user)
        prefix = config.quote_prefix
        num = next_available_numero(prefix, date_emission.year, Quote)
        numero = f"{prefix}-{date_emission.year}-{num:03d}"

        quote = Quote(
            utilisateur=user,
            client=client,
            numero=numero,
            date_emission=date_emission,
            date_validite=date_validite,
            statut=Quote.STATUT_ENVOYE,
            objet=objet,
            notes=DEMO_MARKER,
        )
        quote.save()
        self._add_lines(quote, services, QuoteLine, "devis")

        dt_creation = make_datetime(date_emission)
        h1 = QuoteHistory.objects.create(
            devis=quote, ancien_statut=None, nouveau_statut="BROUILLON")
        QuoteHistory.objects.filter(pk=h1.pk).update(created_at=dt_creation)
        dt_sent = make_datetime(date_emission + timedelta(days=1))
        h2 = QuoteHistory.objects.create(
            devis=quote, ancien_statut="BROUILLON", nouveau_statut="ENVOYE")
        QuoteHistory.objects.filter(pk=h2.pk).update(created_at=dt_sent)

        Quote.all_objects.filter(pk=quote.pk).update(
            created_at=dt_creation, updated_at=dt_sent)

        config.next_quote_number = max(config.next_quote_number, num + 1)
        config.save(update_fields=["next_quote_number"])
        return quote
