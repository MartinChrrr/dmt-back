from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from invoices.models import Invoice
from quotes.models import Quote


MONTHS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]
DEADLINES_LIMIT = 10
TRANSACTIONS_LIMIT = 10


class DashboardStatsView(APIView):
    """
    GET /api/dashboard/stats/

    Returns aggregated dashboard data for the authenticated user:
    - monthly_revenue: revenue per month (paid invoices) for the current year
    - monthly_profit: total revenue (paid invoices) for the current month
    - pending_total: accepted quotes + sent/overdue invoices total
    - upcoming_deadlines: top 10 sent/overdue invoices and sent quotes by deadline asc
    - last_transactions: top 10 paid invoices by updated_at desc
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        current_year = now.year
        current_month = now.month

        return Response({
            "monthly_revenue": self._monthly_revenue(user, current_year),
            "monthly_profit": self._monthly_profit(user, current_year, current_month),
            "pending_total": self._pending_total(user),
            "upcoming_deadlines": self._upcoming_deadlines(user),
            "last_transactions": self._last_transactions(user),
        })

    @staticmethod
    def _monthly_revenue(user, year):
        rows = (
            Invoice.objects
            .filter(utilisateur=user, statut=Invoice.STATUT_PAYEE, date_emission__year=year)
            .annotate(month=ExtractMonth('date_emission'))
            .values('month')
            .annotate(total=Sum('total_ttc'))
        )
        totals_by_month = {r['month']: r['total'] or Decimal('0') for r in rows}
        return [
            {"month": MONTHS[i], "total": totals_by_month.get(i + 1, Decimal('0'))}
            for i in range(12)
        ]

    @staticmethod
    def _monthly_profit(user, year, month):
        total = (
            Invoice.objects
            .filter(
                utilisateur=user,
                statut=Invoice.STATUT_PAYEE,
                date_emission__year=year,
                date_emission__month=month,
            )
            .aggregate(s=Sum('total_ttc'))['s']
        )
        return total or Decimal('0')

    @staticmethod
    def _pending_total(user):
        quotes_total = (
            Quote.objects
            .filter(utilisateur=user, statut=Quote.STATUT_ACCEPTE)
            .aggregate(s=Sum('total_ttc'))['s']
        ) or Decimal('0')
        invoices_total = (
            Invoice.objects
            .filter(utilisateur=user, statut__in=[Invoice.STATUT_ENVOYEE, Invoice.STATUT_EN_RETARD])
            .aggregate(s=Sum('total_ttc'))['s']
        ) or Decimal('0')
        return quotes_total + invoices_total

    @staticmethod
    def _upcoming_deadlines(user):
        invoice_deadlines = (
            Invoice.objects
            .filter(utilisateur=user, statut__in=[Invoice.STATUT_ENVOYEE, Invoice.STATUT_EN_RETARD])
            .select_related('client')
            .order_by('date_echeance')[:DEADLINES_LIMIT]
        )
        quote_deadlines = (
            Quote.objects
            .filter(utilisateur=user, statut=Quote.STATUT_ENVOYE)
            .select_related('client')
            .order_by('date_validite')[:DEADLINES_LIMIT]
        )

        merged = [
            {
                "id": inv.id,
                "numero": inv.numero,
                "client": inv.client.raison_sociale,
                "date": inv.date_echeance,
                "statut": inv.statut,
                "type": "facture",
            }
            for inv in invoice_deadlines
        ] + [
            {
                "id": q.id,
                "numero": q.numero,
                "client": q.client.raison_sociale,
                "date": q.date_validite,
                "statut": q.statut,
                "type": "devis",
            }
            for q in quote_deadlines
        ]

        merged.sort(key=lambda d: d["date"])
        return merged[:DEADLINES_LIMIT]

    @staticmethod
    def _last_transactions(user):
        invoices = (
            Invoice.objects
            .filter(utilisateur=user, statut=Invoice.STATUT_PAYEE)
            .select_related('client')
            .order_by('-updated_at')[:TRANSACTIONS_LIMIT]
        )
        return [
            {
                "id": inv.id,
                "numero": inv.numero,
                "client": inv.client.raison_sociale,
                "updated_at": inv.updated_at,
                "total_ttc": inv.total_ttc,
            }
            for inv in invoices
        ]
