import csv
import io
import zipfile
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from clients.models import Address, Client
from invoices.models import Invoice, InvoiceHistory, InvoiceLine
from quotes.models import Quote, QuoteHistory, QuoteLine
from services.models import Service

from .serializers import AdminUserListSerializer

User = get_user_model()


class AdminUserListView(APIView):
    """GET /api/admin/users/ — list every user with usage counters."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        users = (
            User.objects.all()
            .annotate(
                clients_count=Count('clients', distinct=True),
                quotes_count=Count('devis', distinct=True),
                invoices_count=Count('factures', distinct=True),
            )
            .order_by('-date_joined')
        )
        return Response(AdminUserListSerializer(users, many=True).data)


class AdminUserDeleteView(APIView):
    """
    DELETE /api/admin/users/<id>/ — RGPD right to erasure.
    Hard deletes the user and cascades to clients, services, quotes, invoices.
    """

    permission_classes = [IsAdminUser]

    def delete(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        if user.is_superuser:
            return Response(
                {"detail": "Impossible de supprimer un superutilisateur."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.pk == request.user.pk:
            return Response(
                {"detail": "Impossible de supprimer son propre compte via cette route."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            # Force hard delete on soft-deleted models (otherwise FK targets remain)
            QuoteLine.all_objects.filter(devis__utilisateur=user).delete()
            QuoteHistory.all_objects.filter(devis__utilisateur=user).delete()
            Quote.all_objects.filter(utilisateur=user).delete()
            InvoiceLine.objects.filter(facture__utilisateur=user).delete()
            InvoiceHistory.all_objects.filter(facture__utilisateur=user).delete()
            Invoice.all_objects.filter(utilisateur=user).delete()
            Address.objects.filter(client__utilisateur=user).delete()
            Client.objects.filter(utilisateur=user).delete()
            Service.objects.filter(utilisateur=user).delete()
            email = user.email
            user.delete()

        return Response(
            {"detail": f"Données de {email} supprimées définitivement."},
            status=status.HTTP_200_OK,
        )


class AdminUserExportView(APIView):
    """
    GET /api/admin/users/<id>/export/ — RGPD right to portability.
    Returns a ZIP archive containing one CSV per entity owned by the user.
    """

    permission_classes = [IsAdminUser]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('user.csv', _user_csv(user))
            archive.writestr('clients.csv', _clients_csv(user))
            archive.writestr('addresses.csv', _addresses_csv(user))
            archive.writestr('services.csv', _services_csv(user))
            archive.writestr('quotes.csv', _quotes_csv(user))
            archive.writestr('quote_lines.csv', _quote_lines_csv(user))
            archive.writestr('invoices.csv', _invoices_csv(user))
            archive.writestr('invoice_lines.csv', _invoice_lines_csv(user))

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"rgpd_export_user_{user.pk}_{timestamp}.zip"
        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


def _csv(rows, header):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


def _user_csv(user):
    header = [
        'id', 'email', 'username', 'first_name', 'last_name',
        'company_name', 'siret', 'address', 'postal_code', 'city',
        'phone', 'is_active', 'is_staff', 'date_joined', 'last_login',
    ]
    rows = [[
        user.id, user.email, user.username, user.first_name, user.last_name,
        user.company_name, user.siret, user.address, user.postal_code, user.city,
        user.phone, user.is_active, user.is_staff, user.date_joined, user.last_login,
    ]]
    return _csv(rows, header)


def _clients_csv(user):
    header = [
        'id', 'raison_sociale', 'siret', 'email', 'telephone',
        'contact_nom', 'contact_email', 'contact_telephone', 'notes',
        'created_at', 'updated_at',
    ]
    rows = [
        [
            c.id, c.raison_sociale, c.siret, c.email, c.telephone,
            c.contact_nom, c.contact_email, c.contact_telephone, c.notes,
            c.created_at, c.updated_at,
        ]
        for c in Client.objects.filter(utilisateur=user)
    ]
    return _csv(rows, header)


def _addresses_csv(user):
    header = ['id', 'client_id', 'type', 'ligne1', 'ligne2', 'code_postal', 'ville', 'pays']
    rows = [
        [a.id, a.client_id, a.type, a.ligne1, a.ligne2, a.code_postal, a.ville, a.pays]
        for a in Address.objects.filter(client__utilisateur=user)
    ]
    return _csv(rows, header)


def _services_csv(user):
    header = ['id', 'label', 'description', 'unit_price_excl_tax', 'unit', 'taux_tva', 'created_at']
    rows = [
        [s.id, s.label, s.description, s.unit_price_excl_tax, s.unit, s.taux_tva, s.created_at]
        for s in Service.objects.filter(utilisateur=user)
    ]
    return _csv(rows, header)


def _quotes_csv(user):
    header = [
        'id', 'numero', 'client_id', 'date_emission', 'date_validite', 'statut',
        'objet', 'total_ht', 'total_tva', 'total_ttc', 'created_at', 'deleted_at',
    ]
    rows = [
        [
            q.id, q.numero, q.client_id, q.date_emission, q.date_validite, q.statut,
            q.objet, q.total_ht, q.total_tva, q.total_ttc, q.created_at, q.deleted_at,
        ]
        for q in Quote.all_objects.filter(utilisateur=user)
    ]
    return _csv(rows, header)


def _quote_lines_csv(user):
    header = [
        'id', 'devis_id', 'ordre', 'libelle', 'description',
        'quantite', 'unite', 'prix_unitaire_ht', 'taux_tva', 'montant_ht',
    ]
    rows = [
        [
            l.id, l.devis_id, l.ordre, l.libelle, l.description,
            l.quantite, l.unite, l.prix_unitaire_ht, l.taux_tva, l.montant_ht,
        ]
        for l in QuoteLine.all_objects.filter(devis__utilisateur=user)
    ]
    return _csv(rows, header)


def _invoices_csv(user):
    header = [
        'id', 'numero', 'client_id', 'devis_origine_id', 'date_emission', 'date_echeance',
        'statut', 'objet', 'total_ht', 'total_tva', 'total_ttc', 'created_at', 'deleted_at',
    ]
    rows = [
        [
            i.id, i.numero, i.client_id, i.devis_origine_id, i.date_emission, i.date_echeance,
            i.statut, i.objet, i.total_ht, i.total_tva, i.total_ttc, i.created_at, i.deleted_at,
        ]
        for i in Invoice.all_objects.filter(utilisateur=user)
    ]
    return _csv(rows, header)


def _invoice_lines_csv(user):
    header = [
        'id', 'facture_id', 'ordre', 'libelle', 'description',
        'quantite', 'unite', 'prix_unitaire_ht', 'taux_tva', 'montant_ht',
    ]
    rows = [
        [
            l.id, l.facture_id, l.ordre, l.libelle, l.description,
            l.quantite, l.unite, l.prix_unitaire_ht, l.taux_tva, l.montant_ht,
        ]
        for l in InvoiceLine.objects.filter(facture__utilisateur=user)
    ]
    return _csv(rows, header)
