from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from base.geo import Locazione
from base.models import Autorizzazione, Token

# Aggiugni al pannello di amministrazione
admin.site.register(Token)

def locazione_aggiorna(modello, request, queryset):
    for locazione in queryset:
        locazione.cerca_e_aggiorna()
locazione_aggiorna.short_description = "Aggiorna indirizzi selezionati"


class InlineAutorizzazione(GenericTabularInline):
    model = Autorizzazione
    raw_id_fields = ["richiedente", "firmatario"]
    ct_field = 'oggetto_tipo'
    ct_fk_field = 'oggetto_id'
    extra = 0


@admin.register(Locazione)
class AdminLocazione(admin.ModelAdmin):
    search_fields = ["indirizzo", "via", "comune", "regione", "provincia"]
    list_display = ("indirizzo", "provincia", "regione", "stato", "creazione",)
    list_filter = ("regione", "stato", "creazione")
    actions = [locazione_aggiorna]


@admin.register(Autorizzazione)
class AdminAutorizzazione(admin.ModelAdmin):
    search_fields = ["richiedente__nome", "richiedente__cognome", "richiedente__codice_fiscale",
                     "firmatario__nome", "firmatario__cognome", "firmatario__codice_fiscale", ]
    list_display = ("richiedente", "firmatario", "concessa", "necessaria", "progressivo",
                    "oggetto_tipo", "oggetto_id",
                    "destinatario_ruolo", "destinatario_oggetto_tipo", "destinatario_oggetto_id")
    list_filter = ("necessaria", "concessa", "destinatario_oggetto_tipo",)
    raw_id_fields = ("richiedente", "firmatario", )
