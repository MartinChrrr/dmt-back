from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, UserConfiguration
from clients.models import Client
from invoices.models import Invoice
from quotes.models import Quote


DASHBOARD_URL = '/api/dashboard/stats/'
MONTHS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]


class DashboardTestMixin:
    """Common fixtures and helpers for dashboard tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com', password='testpass123'
        )
        self.config = UserConfiguration.objects.create(
            user=self.user,
            invoice_prefix='FAC',
            next_invoice_number=1,
            payment_deadline_days=30,
            quote_prefix='DEV',
            next_quote_number=1,
            quote_validity_days=30,
        )
        self.client_obj = Client.objects.create(
            utilisateur=self.user,
            raison_sociale='Client Test',
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _make_invoice(
        self,
        *,
        user=None,
        client=None,
        statut=Invoice.STATUT_BROUILLON,
        total_ttc='100.00',
        date_emission=None,
        date_echeance=None,
        numero=None,
        updated_at=None,
    ):
        """Create an invoice directly in DB with explicit fields (bypassing API)."""
        emission = date_emission or date.today()
        invoice = Invoice.objects.create(
            utilisateur=user or self.user,
            client=client or self.client_obj,
            numero=numero,
            date_emission=emission,
            date_echeance=date_echeance or (emission + timedelta(days=30)),
            statut=statut,
            total_ttc=Decimal(total_ttc),
        )
        if updated_at is not None:
            Invoice.objects.filter(pk=invoice.pk).update(updated_at=updated_at)
            invoice.refresh_from_db()
        return invoice

    def _make_quote(
        self,
        *,
        user=None,
        client=None,
        statut=Quote.STATUT_BROUILLON,
        total_ttc='100.00',
        date_emission=None,
        date_validite=None,
    ):
        """Create a quote directly in DB with explicit fields."""
        emission = date_emission or date.today()
        return Quote.objects.create(
            utilisateur=user or self.user,
            client=client or self.client_obj,
            date_emission=emission,
            date_validite=date_validite or (emission + timedelta(days=30)),
            statut=statut,
            total_ttc=Decimal(total_ttc),
        )


# AUTH
class DashboardAuthTest(DashboardTestMixin, TestCase):

    def test_unauthenticated_access_denied(self):
        api = APIClient()
        resp = api.get(DASHBOARD_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data['status'], 'fail')

    def test_authenticated_access_ok(self):
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'success')


# RESPONSE STRUCTURE
class DashboardResponseShapeTest(DashboardTestMixin, TestCase):

    def test_response_contains_all_keys(self):
        resp = self.api.get(DASHBOARD_URL)
        data = resp.data['data']
        for key in ('monthly_revenue', 'monthly_profit', 'pending_total',
                    'upcoming_deadlines', 'last_transactions'):
            self.assertIn(key, data)

    def test_empty_dashboard_returns_zeros(self):
        resp = self.api.get(DASHBOARD_URL)
        data = resp.data['data']
        self.assertEqual(len(data['monthly_revenue']), 12)
        for entry in data['monthly_revenue']:
            self.assertEqual(Decimal(entry['total']), Decimal('0'))
        self.assertEqual(Decimal(data['monthly_profit']), Decimal('0'))
        self.assertEqual(Decimal(data['pending_total']), Decimal('0'))
        self.assertEqual(data['upcoming_deadlines'], [])
        self.assertEqual(data['last_transactions'], [])

    def test_monthly_revenue_uses_french_month_labels(self):
        resp = self.api.get(DASHBOARD_URL)
        labels = [entry['month'] for entry in resp.data['data']['monthly_revenue']]
        self.assertEqual(labels, MONTHS)


# MONTHLY REVENUE
class DashboardMonthlyRevenueTest(DashboardTestMixin, TestCase):

    def _revenue_for(self, data, month_index):
        """Get revenue total for a given 0-indexed month from response data."""
        return Decimal(data['monthly_revenue'][month_index]['total'])

    def test_paid_invoice_counted_in_emission_month(self):
        today = date.today()
        self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            total_ttc='240.00',
            date_emission=today,
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(
            self._revenue_for(resp.data['data'], today.month - 1),
            Decimal('240.00'),
        )

    def test_unpaid_invoice_excluded(self):
        today = date.today()
        self._make_invoice(statut=Invoice.STATUT_ENVOYEE, total_ttc='500.00', date_emission=today)
        self._make_invoice(statut=Invoice.STATUT_BROUILLON, total_ttc='500.00', date_emission=today)
        self._make_invoice(statut=Invoice.STATUT_EN_RETARD, total_ttc='500.00', date_emission=today)
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(
            self._revenue_for(resp.data['data'], today.month - 1),
            Decimal('0'),
        )

    def test_prior_year_invoice_excluded(self):
        today = date.today()
        last_year = date(today.year - 1, today.month, 1)
        self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            total_ttc='999.00',
            date_emission=last_year,
        )
        resp = self.api.get(DASHBOARD_URL)
        for i in range(12):
            self.assertEqual(self._revenue_for(resp.data['data'], i), Decimal('0'))

    def test_multiple_invoices_same_month_summed(self):
        today = date.today()
        self._make_invoice(statut=Invoice.STATUT_PAYEE, total_ttc='100.00', date_emission=today)
        self._make_invoice(statut=Invoice.STATUT_PAYEE, total_ttc='250.50', date_emission=today)
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(
            self._revenue_for(resp.data['data'], today.month - 1),
            Decimal('350.50'),
        )

    def test_invoices_distributed_across_months(self):
        year = date.today().year
        # Use January and March of current year (months 1 and 3 in 1-indexed)
        self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            total_ttc='100.00',
            date_emission=date(year, 1, 15),
        )
        self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            total_ttc='200.00',
            date_emission=date(year, 3, 10),
        )
        resp = self.api.get(DASHBOARD_URL)
        data = resp.data['data']
        self.assertEqual(self._revenue_for(data, 0), Decimal('100.00'))
        self.assertEqual(self._revenue_for(data, 1), Decimal('0'))
        self.assertEqual(self._revenue_for(data, 2), Decimal('200.00'))


# MONTHLY PROFIT
class DashboardMonthlyProfitTest(DashboardTestMixin, TestCase):

    def test_paid_invoice_current_month_counted(self):
        self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            total_ttc='480.00',
            date_emission=date.today(),
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['monthly_profit']), Decimal('480.00'))

    def test_paid_invoice_different_month_excluded(self):
        today = date.today()
        # Pick a different month within the same year
        other_month = 1 if today.month != 1 else 2
        self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            total_ttc='999.00',
            date_emission=date(today.year, other_month, 5),
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['monthly_profit']), Decimal('0'))

    def test_unpaid_invoice_excluded(self):
        self._make_invoice(
            statut=Invoice.STATUT_ENVOYEE,
            total_ttc='999.00',
            date_emission=date.today(),
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['monthly_profit']), Decimal('0'))

    def test_multiple_paid_invoices_summed(self):
        today = date.today()
        self._make_invoice(statut=Invoice.STATUT_PAYEE, total_ttc='100.00', date_emission=today)
        self._make_invoice(statut=Invoice.STATUT_PAYEE, total_ttc='150.50', date_emission=today)
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['monthly_profit']), Decimal('250.50'))


# PENDING TOTAL
class DashboardPendingTotalTest(DashboardTestMixin, TestCase):

    def test_accepted_quotes_counted(self):
        self._make_quote(statut=Quote.STATUT_ACCEPTE, total_ttc='300.00')
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('300.00'))

    def test_sent_invoices_counted(self):
        self._make_invoice(statut=Invoice.STATUT_ENVOYEE, total_ttc='400.00')
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('400.00'))

    def test_overdue_invoices_counted(self):
        self._make_invoice(statut=Invoice.STATUT_EN_RETARD, total_ttc='500.00')
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('500.00'))

    def test_paid_invoices_excluded(self):
        self._make_invoice(statut=Invoice.STATUT_PAYEE, total_ttc='999.00')
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('0'))

    def test_draft_invoices_excluded(self):
        self._make_invoice(statut=Invoice.STATUT_BROUILLON, total_ttc='999.00')
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('0'))

    def test_non_accepted_quotes_excluded(self):
        self._make_quote(statut=Quote.STATUT_BROUILLON, total_ttc='100.00')
        self._make_quote(statut=Quote.STATUT_ENVOYE, total_ttc='200.00')
        self._make_quote(statut=Quote.STATUT_REFUSE, total_ttc='300.00')
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('0'))

    def test_pending_total_is_sum_of_quotes_and_invoices(self):
        self._make_quote(statut=Quote.STATUT_ACCEPTE, total_ttc='100.00')
        self._make_invoice(statut=Invoice.STATUT_ENVOYEE, total_ttc='200.00')
        self._make_invoice(statut=Invoice.STATUT_EN_RETARD, total_ttc='50.00')
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('350.00'))


# UPCOMING DEADLINES
class DashboardUpcomingDeadlinesTest(DashboardTestMixin, TestCase):

    def test_sent_invoice_with_future_deadline_shown(self):
        today = date.today()
        invoice = self._make_invoice(
            statut=Invoice.STATUT_ENVOYEE,
            numero='FAC-001',
            date_echeance=today + timedelta(days=10),
        )
        resp = self.api.get(DASHBOARD_URL)
        deadlines = resp.data['data']['upcoming_deadlines']
        self.assertEqual(len(deadlines), 1)
        self.assertEqual(deadlines[0]['id'], invoice.id)
        self.assertEqual(deadlines[0]['type'], 'facture')
        self.assertEqual(deadlines[0]['numero'], 'FAC-001')
        self.assertEqual(deadlines[0]['client'], 'Client Test')

    def test_sent_quote_with_future_validity_shown(self):
        today = date.today()
        quote = self._make_quote(
            statut=Quote.STATUT_ENVOYE,
            date_validite=today + timedelta(days=15),
        )
        resp = self.api.get(DASHBOARD_URL)
        deadlines = resp.data['data']['upcoming_deadlines']
        self.assertEqual(len(deadlines), 1)
        self.assertEqual(deadlines[0]['id'], quote.id)
        self.assertEqual(deadlines[0]['type'], 'devis')

    def test_past_deadline_excluded(self):
        today = date.today()
        self._make_invoice(
            statut=Invoice.STATUT_ENVOYEE,
            date_echeance=today - timedelta(days=1),
        )
        self._make_quote(
            statut=Quote.STATUT_ENVOYE,
            date_validite=today - timedelta(days=1),
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(resp.data['data']['upcoming_deadlines'], [])

    def test_today_deadline_included(self):
        today = date.today()
        self._make_invoice(statut=Invoice.STATUT_ENVOYEE, date_echeance=today)
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(len(resp.data['data']['upcoming_deadlines']), 1)

    def test_non_sent_invoice_excluded(self):
        today = date.today()
        self._make_invoice(
            statut=Invoice.STATUT_BROUILLON,
            date_echeance=today + timedelta(days=10),
        )
        self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            date_echeance=today + timedelta(days=10),
        )
        self._make_invoice(
            statut=Invoice.STATUT_EN_RETARD,
            date_echeance=today + timedelta(days=10),
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(resp.data['data']['upcoming_deadlines'], [])

    def test_non_sent_quote_excluded(self):
        today = date.today()
        self._make_quote(
            statut=Quote.STATUT_BROUILLON,
            date_validite=today + timedelta(days=10),
        )
        self._make_quote(
            statut=Quote.STATUT_ACCEPTE,
            date_validite=today + timedelta(days=10),
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(resp.data['data']['upcoming_deadlines'], [])

    def test_deadlines_sorted_by_date_asc(self):
        today = date.today()
        self._make_invoice(
            statut=Invoice.STATUT_ENVOYEE,
            numero='FAC-LATE',
            date_echeance=today + timedelta(days=20),
        )
        self._make_quote(
            statut=Quote.STATUT_ENVOYE,
            date_validite=today + timedelta(days=5),
        )
        self._make_invoice(
            statut=Invoice.STATUT_ENVOYEE,
            numero='FAC-EARLY',
            date_echeance=today + timedelta(days=10),
        )
        resp = self.api.get(DASHBOARD_URL)
        deadlines = resp.data['data']['upcoming_deadlines']
        self.assertEqual(len(deadlines), 3)
        dates = [d['date'] for d in deadlines]
        self.assertEqual(dates, sorted(dates))

    def test_deadlines_limited_to_10(self):
        today = date.today()
        for i in range(15):
            self._make_invoice(
                statut=Invoice.STATUT_ENVOYEE,
                numero=f'FAC-{i:03d}',
                date_echeance=today + timedelta(days=i + 1),
            )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(len(resp.data['data']['upcoming_deadlines']), 10)


# LAST TRANSACTIONS
class DashboardLastTransactionsTest(DashboardTestMixin, TestCase):

    def test_paid_invoice_listed(self):
        invoice = self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            numero='FAC-PAID',
            total_ttc='123.45',
        )
        resp = self.api.get(DASHBOARD_URL)
        transactions = resp.data['data']['last_transactions']
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]['id'], invoice.id)
        self.assertEqual(transactions[0]['numero'], 'FAC-PAID')
        self.assertEqual(transactions[0]['client'], 'Client Test')
        self.assertEqual(Decimal(transactions[0]['total_ttc']), Decimal('123.45'))

    def test_non_paid_invoices_excluded(self):
        self._make_invoice(statut=Invoice.STATUT_BROUILLON)
        self._make_invoice(statut=Invoice.STATUT_ENVOYEE)
        self._make_invoice(statut=Invoice.STATUT_EN_RETARD)
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(resp.data['data']['last_transactions'], [])

    def test_transactions_sorted_by_updated_at_desc(self):
        now = timezone.now()
        old = self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            numero='FAC-OLD',
            updated_at=now - timedelta(days=5),
        )
        recent = self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            numero='FAC-RECENT',
            updated_at=now - timedelta(hours=1),
        )
        middle = self._make_invoice(
            statut=Invoice.STATUT_PAYEE,
            numero='FAC-MID',
            updated_at=now - timedelta(days=2),
        )
        resp = self.api.get(DASHBOARD_URL)
        ids = [t['id'] for t in resp.data['data']['last_transactions']]
        self.assertEqual(ids, [recent.id, middle.id, old.id])

    def test_transactions_limited_to_10(self):
        now = timezone.now()
        for i in range(12):
            self._make_invoice(
                statut=Invoice.STATUT_PAYEE,
                numero=f'FAC-{i:03d}',
                updated_at=now - timedelta(hours=i),
            )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(len(resp.data['data']['last_transactions']), 10)


# USER ISOLATION
class DashboardUserIsolationTest(DashboardTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.other_user = User.objects.create_user(
            username='other', email='other@test.com', password='pass123'
        )
        UserConfiguration.objects.create(user=self.other_user)
        self.other_client = Client.objects.create(
            utilisateur=self.other_user,
            raison_sociale='Other Client',
        )

    def test_other_user_paid_invoice_excluded_from_revenue(self):
        self._make_invoice(
            user=self.other_user,
            client=self.other_client,
            statut=Invoice.STATUT_PAYEE,
            total_ttc='999.00',
        )
        resp = self.api.get(DASHBOARD_URL)
        for entry in resp.data['data']['monthly_revenue']:
            self.assertEqual(Decimal(entry['total']), Decimal('0'))
        self.assertEqual(Decimal(resp.data['data']['monthly_profit']), Decimal('0'))

    def test_other_user_pending_excluded(self):
        self._make_invoice(
            user=self.other_user,
            client=self.other_client,
            statut=Invoice.STATUT_ENVOYEE,
            total_ttc='999.00',
        )
        self._make_quote(
            user=self.other_user,
            client=self.other_client,
            statut=Quote.STATUT_ACCEPTE,
            total_ttc='999.00',
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(Decimal(resp.data['data']['pending_total']), Decimal('0'))

    def test_other_user_deadlines_excluded(self):
        today = date.today()
        self._make_invoice(
            user=self.other_user,
            client=self.other_client,
            statut=Invoice.STATUT_ENVOYEE,
            date_echeance=today + timedelta(days=5),
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(resp.data['data']['upcoming_deadlines'], [])

    def test_other_user_transactions_excluded(self):
        self._make_invoice(
            user=self.other_user,
            client=self.other_client,
            statut=Invoice.STATUT_PAYEE,
        )
        resp = self.api.get(DASHBOARD_URL)
        self.assertEqual(resp.data['data']['last_transactions'], [])
