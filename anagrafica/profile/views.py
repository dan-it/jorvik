from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.db import transaction

from autenticazione.funzioni import pagina_privata
from autenticazione.models import Utenza
from attivita.forms import ModuloStatisticheAttivitaPersona
from attivita.models import Partecipazione
from attivita.stats import statistiche_attivita_persona
from base.errori import (errore_generico, messaggio_generico)
from base.models import Log
from posta.models import Messaggio
from sangue.models import Donatore
from ..permessi.costanti import (ERRORE_PERMESSI, MODIFICA, LETTURA)
from ..forms import (ModuloCreazioneDocumento, ModuloCreazioneTelefono, ModuloDonatore,
    ModuloDonazione, ModuloNuovaFototessera, ModuloProfiloModificaAnagrafica,
    ModuloProfiloTitoloPersonale, ModuloUtenza, ModuloModificaDataInizioAppartenenza,
    ModuloUSModificaUtenza)
from ..models import (Persona, Appartenenza, ProvvedimentoDisciplinare, Riserva)


@pagina_privata
def profilo(request, me, pk, sezione=None):
    from ..profile.menu import profile_sections, filter_per_role

    persona = get_object_or_404(Persona, pk=pk)
    puo_modificare = me.permessi_almeno(oggetto=persona, minimo=MODIFICA)
    puo_leggere = me.permessi_almeno(oggetto=persona, minimo=LETTURA)

    # Controlla permessi di visualizzazione
    sezioni = profile_sections(puo_leggere, puo_modificare)
    sezioni = filter_per_role(me, persona, sezioni)

    context = {
        "persona": persona,
        "puo_modificare": puo_modificare,
        "puo_leggere": puo_leggere,
        "sezioni": sezioni,
        "attuale": sezione,
    }

    if not sezione:  # Prima pagina
        return 'anagrafica_profilo_profilo.html', context

    else:  # Sezione aperta
        if sezione not in sezioni:
            return redirect(ERRORE_PERMESSI)

        s = sezioni[sezione]
        response = s[2](request, me, persona)
        try:
            f_template, f_context = response
            context.update(f_context)
            return f_template, context
        except ValueError:
            return response


def _profilo_anagrafica(request, me, persona):
    puo_modificare = me.permessi_almeno(persona, MODIFICA)
    modulo = ModuloProfiloModificaAnagrafica(request.POST or None,
                                            me=me,
                                            instance=persona,
                                            prefix="anagrafica")
    modulo_numero_telefono = ModuloCreazioneTelefono(request.POST or None, prefix="telefono")

    if puo_modificare and modulo.is_valid():
        Log.registra_modifiche(me, modulo)
        modulo.save()

    if puo_modificare and modulo_numero_telefono.is_valid():
        persona.aggiungi_numero_telefono(
            modulo_numero_telefono.cleaned_data.get('numero_di_telefono'),
            modulo_numero_telefono.cleaned_data.get('tipologia') == modulo_numero_telefono.SERVIZIO,
        )

    contesto = {
        "modulo": modulo,
        "modulo_numero_telefono": modulo_numero_telefono,
    }
    return 'anagrafica_profilo_anagrafica.html', contesto


def _profilo_appartenenze(request, me, persona):
    puo_modificare = me.permessi_almeno(persona, MODIFICA)
    alredy_valid = False
    moduli = []
    terminabili = []
    for app in persona.appartenenze.all():
        modulo = None
        terminabile = me.permessi_almeno(app.estensione.first(), MODIFICA)
        for modulo in moduli:
            if not modulo is None and modulo.is_valid:
                alredy_valid = True
        if app.attuale() and app.modificabile() and puo_modificare and not alredy_valid:
            modulo = ModuloModificaDataInizioAppartenenza(request.POST or None,
                                                          instance=app,
                                                          prefix="%d" % (app.pk,))
            if ("%s-inizio" % (app.pk,)) in request.POST and modulo.is_valid():
                with transaction.atomic():
                    if app.membro == Appartenenza.DIPENDENTE:
                        app_volontario = persona.appartenenze_attuali(membro=Appartenenza.VOLONTARIO).first()
                        if app_volontario:
                            try:
                                riserva = Riserva.objects.get(appartenenza=app_volontario)
                            except Exception:
                                pass
                            else:
                                riserva.inizio = modulo.cleaned_data['inizio']
                                riserva.save()
                    modulo.save()

        moduli += [modulo]
        terminabili += [terminabile]

    appartenenze = zip(persona.appartenenze.all(), moduli, terminabili)

    contesto = {
        "appartenenze": appartenenze,
        "es": Appartenenza.ESTESO
    }

    return 'anagrafica_profilo_appartenenze.html', contesto


def _profilo_fototessera(request, me, persona):
    puo_modificare = me.permessi_almeno(persona, MODIFICA)

    modulo = ModuloNuovaFototessera(request.POST or None, request.FILES or None)
    if modulo.is_valid():
        fototessera = modulo.save(commit=False)
        fototessera.persona = persona
        fototessera.save()

        # Ritira eventuali fototessere in attesa
        if persona.fototessere_pending().exists():
            for x in persona.fototessere_pending():
                x.autorizzazioni_ritira()

        Log.crea(me, fototessera)

    contesto = {
        "puo_modificare": puo_modificare,
        "modulo": modulo,
    }
    return 'anagrafica_profilo_fototessera.html', contesto


def _profilo_deleghe(request, me, persona):
    return 'anagrafica_profilo_deleghe.html', {}


def _profilo_turni(request, me, persona):
    modulo = ModuloStatisticheAttivitaPersona(request.POST or None)
    storico = Partecipazione.objects.filter(persona=persona).order_by('-turno__inizio')
    statistiche = statistiche_attivita_persona(persona, modulo)
    contesto = {
        "storico": storico,
        "statistiche": statistiche,
        "statistiche_modulo": modulo,
    }
    return 'anagrafica_profilo_turni.html', contesto


def _profilo_riserve(request, me, persona):

    riserve = Riserva.objects.filter(persona=persona)

    contesto = {
        "riserve": riserve,
    }


    return 'anagrafica_profilo_riserve.html', contesto


def _profilo_curriculum(request, me, persona):
    form = ModuloProfiloTitoloPersonale(request.POST or None)

    if form.is_valid():
        tp = form.save(commit=False)
        tp.persona = persona
        tp.save()

    context = {
        "modulo": form,
    }
    return 'anagrafica_profilo_curriculum.html', context


def _profilo_sangue(request, me, persona):
    modulo_donatore = ModuloDonatore(request.POST or None, prefix="donatore", instance=Donatore.objects.filter(persona=persona).first())
    modulo_donazione = ModuloDonazione(request.POST or None, prefix="donazione")

    if modulo_donatore.is_valid():
        donatore = modulo_donatore.save(commit=False)
        donatore.persona = persona
        donatore.save()

    if modulo_donazione.is_valid():
        donazione = modulo_donazione.save(commit=False)
        donazione.persona = persona
        r = donazione.save()

    contesto = {
        "modulo_donatore": modulo_donatore,
        "modulo_donazione": modulo_donazione,
    }

    return 'anagrafica_profilo_sangue.html', contesto


def _profilo_documenti(request, me, persona):
    puo_modificare = me.permessi_almeno(persona, MODIFICA)
    modulo = ModuloCreazioneDocumento(request.POST or None, request.FILES or None)
    if puo_modificare and modulo.is_valid():
        f = modulo.save(commit=False)
        f.persona = persona
        f.save()

    contesto = {
        "modulo": modulo,
    }
    return 'anagrafica_profilo_documenti.html', contesto


def _profilo_provvedimenti(request, me, persona):
        provvedimenti = ProvvedimentoDisciplinare.objects.filter(persona=persona)
        contesto = {
            "provvedimenti": provvedimenti,
        }

        return 'anagrafica_profilo_provvedimenti.html', contesto


def _profilo_quote(request, me, persona):
    contesto = {}
    return 'anagrafica_profilo_quote.html', contesto


def _profilo_credenziali(request, me, persona):
    utenza = Utenza.objects.filter(persona=persona).first()

    modulo_utenza = modulo_modifica = None
    if utenza:
        modulo_modifica = ModuloUSModificaUtenza(request.POST or None, instance=utenza)
    else:
        modulo_utenza = ModuloUtenza(request.POST or None, instance=utenza, initial={"email": persona.email_contatto})

    if modulo_utenza and modulo_utenza.is_valid():
        utenza = modulo_utenza.save(commit=False)
        utenza.persona = persona
        utenza.save()
        utenza.genera_credenziali()
        return redirect(persona.url_profilo_credenziali)

    if modulo_modifica and modulo_modifica.is_valid():
        vecchia_email_contatto = persona.email
        vecchia_email = Utenza.objects.get(pk=utenza.pk).email
        nuova_email = modulo_modifica.cleaned_data.get('email')

        if vecchia_email == nuova_email:
            return errore_generico(request, me, titolo="Nessun cambiamento",
                                   messaggio="Per cambiare indirizzo e-mail, inserisci un "
                                             "indirizzo differente.",
                                   torna_titolo="Credenziali",
                                   torna_url=persona.url_profilo_credenziali)

        if Utenza.objects.filter(email__icontains=nuova_email).first():
            return errore_generico(request, me, titolo="E-mail già utilizzata",
                                   messaggio="Esiste un altro utente in Gaia che utilizza "
                                             "questa e-mail (%s). Impossibile associarla quindi "
                                             "a %s." % (nuova_email, persona.nome_completo),
                                   torna_titolo="Credenziali",
                                   torna_url=persona.url_profilo_credenziali)

        def _invia_notifica():
            Messaggio.costruisci_e_invia(
                oggetto="IMPORTANTE: Cambio e-mail di accesso a Gaia (credenziali)",
                modello="email_credenziali_modificate.html",
                corpo={
                    "vecchia_email": vecchia_email,
                    "nuova_email": nuova_email,
                    "persona": persona,
                    "autore": me,
                },
                mittente=me,
                destinatari=[persona],
                utenza=True
            )

        _invia_notifica()  # Invia notifica alla vecchia e-mail
        Log.registra_modifiche(me, modulo_modifica)
        modulo_modifica.save()  # Effettua le modifiche
        persona.refresh_from_db()
        if persona.email != vecchia_email_contatto:  # Se e-mail principale cambiata
            _invia_notifica()  # Invia la notifica anche al nuovo indirizzo

        return messaggio_generico(request, me, titolo="Credenziali modificate",
                                  messaggio="Le credenziali di %s sono state correttamente aggiornate." % persona.nome,
                                  torna_titolo="Credenziali",
                                  torna_url=persona.url_profilo_credenziali)

    contesto = {
        "utenza": utenza,
        "modulo_creazione": modulo_utenza,
        "modulo_modifica": modulo_modifica

    }
    return 'anagrafica_profilo_credenziali.html', contesto
