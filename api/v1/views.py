from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from oauth2_provider.ext.rest_framework import TokenHasScope
from api.settings import SCOPE_ANAGRAFICA_LETTURA_BASE, SCOPE_ANAGRAFICA_LETTURA_COMPLETA, SCOPE_APPARTENENZE_LETTURA

from api.v1 import serializzatori
from anagrafica.permessi.applicazioni import PERMESSI_NOMI_DICT

# /me/anagrafica/base/
class MiaAnagraficaBase(APIView):
    """
    Una vista che ritorna informazioni sulla persona identificata.
    """
    permission_classes = (permissions.IsAuthenticated,
                          TokenHasScope)
    required_scopes = [SCOPE_ANAGRAFICA_LETTURA_BASE]

    def get(self, request, format=None):
        dati = serializzatori.persona_anagrafica_base(request.user.persona)
        return Response(dati)


# /me/anagrafica/completa/
class MiaAnagraficaCompleta(APIView):
    """
    Una vista che ritorna l'anagrafica completa della persona identificata
     (anagrafica base, più dati aggiuntivi).
    """

    permission_classes = (permissions.IsAuthenticated,
                          TokenHasScope)
    required_scopes = [SCOPE_ANAGRAFICA_LETTURA_BASE,
                       SCOPE_ANAGRAFICA_LETTURA_COMPLETA]

    def get(self, request, format=None):
        dati = serializzatori.persona_anagrafica_completa(request.user.persona)
        return Response(dati)


# /me/appartenenze/attuali/
class MieAppartenenzeAttuali(APIView):
    """
    Una vista che ritorna informazioni sulle appartenenze attuali.
    """

    required_scopes = [SCOPE_APPARTENENZE_LETTURA]

    def get(self, request, format=None):
        me = request.user.persona
        appartenenze = me.appartenenze_attuali()
        appartenenze = [serializzatori.appartenenza(i) for i in appartenenze]
        dati = {"appartenenze": appartenenze}
        return Response(dati)


class MiaAppartenenzaComplaeta(APIView):

    """
        ID utente, - Persona

        nome, - Persona

        cognome, - Persona

        indirizzo mail di contatto - Persona

        rispettiva sede di appartenenza, - Persona

        ID comitato,

        nome comitato,

        estensione del comitato R/P/L/T,

        delega
    """
    permission_classes = (permissions.IsAuthenticated,
                          TokenHasScope)
    required_scopes = [SCOPE_ANAGRAFICA_LETTURA_BASE,
                       SCOPE_ANAGRAFICA_LETTURA_COMPLETA,
                       SCOPE_APPARTENENZE_LETTURA]

    def get(self, request, format=None):
        me = request.user.persona

        # Persona
        dati = {
            'id_persona': me.pk,
            'nome': me.nome,
            'cognome': me.cognome,
            'data_di_nascita': me.data_nascita,
            'codice_fiscale': me.codice_fiscale,
        }
        if me.email is not None:
            dati['email'] = me.email

        # Comitato
        deleghe = me.deleghe_attuali()

        l_deleghe = []
        for delega in deleghe:
            d_delega = {
                'id': delega.id,
                'tipo': PERMESSI_NOMI_DICT[delega.tipo],
                'appartenenza': delega.oggetto.nome,
            }
            l_deleghe.append(d_delega)
        dati['deleghe'] = l_deleghe

        # appartenenze
        appartenenze = me.appartenenze_attuali()
        l_appartenenza = []

        for appartenenza in appartenenze:
            comitato = appartenenza.sede
            l_appartenenza.append({
                'id': comitato.id,
                'nome': comitato.nome,
                'tipo': {
                    'id': appartenenza.membro,
                    'descrizione': appartenenza.get_membro_display()
                },
                'comitato': {
                    'id': comitato.estensione,
                    'descrizione': comitato.get_estensione_display()
                },
            })
        dati['appartenenze'] = l_appartenenza

        return Response(dati)

#serializzatori._campo(comitato.estensione, comitato.get_estensione_display())
