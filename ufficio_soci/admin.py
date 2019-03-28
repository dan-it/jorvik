from django.contrib import admin

from gruppi.readonly_admin import ReadonlyAdminMixin
from .models import Tesserino, Quota, Tesseramento, Riduzione, ReportElenco


@admin.register(Quota)
class AdminQuota(ReadonlyAdminMixin, admin.ModelAdmin):
    search_fields = ["persona__nome", "persona__cognome", "persona__codice_fiscale",
                     "sede__nome", ]
    list_display = ("persona", "tipo", "stato", "sede", "progressivo", "anno", "data_versamento",)
    list_filter = ("stato", "tipo", "data_versamento", "anno",)
    raw_id_fields = ("persona", "appartenenza", "sede", "registrato_da", "annullato_da",)


@admin.register(Tesserino)
class AdminTesserino(ReadonlyAdminMixin, admin.ModelAdmin):
    search_fields = ["persona__nome", "persona__cognome", "persona__codice_fiscale",
                     "codice", ]
    list_display = ("codice", "persona", "valido", "tipo_richiesta", "stato_richiesta", "stato_emissione",)
    list_filter = ("stato_emissione", "stato_richiesta", "valido", "tipo_richiesta",)
    raw_id_fields = ("persona", "emesso_da", "richiesto_da", "confermato_da", "riconsegnato_a",)


@admin.register(Tesseramento)
class AdminTesseramento(ReadonlyAdminMixin, admin.ModelAdmin):
    search_fields = ["anno", ]
    list_display = ("anno", "stato", "inizio", "quota_attivo", "quota_ordinario", "quota_sostenitore",
                    "quota_benemerito", "quota_aspirante",)
    list_filter = ("anno", "stato",)
    raw_id_fields = ()


@admin.register(Riduzione)
class AdminRiduzione(ReadonlyAdminMixin, admin.ModelAdmin):
    pass


@admin.register(ReportElenco)
class AdminReportElenco(ReadonlyAdminMixin, admin.ModelAdmin):
    raw_id_fields = ('user',)
    list_display = ['user', 'file', 'is_ready', 'creazione',
                    'ultima_modifica', 'report_type', 'task_id']
    list_filter = ['is_ready', 'report_type',]
