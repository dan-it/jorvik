from datetime import datetime, timedelta

# from django.conf import settings
# from django.core.exceptions import ObjectDoesNotExist
# from django.db.transaction import atomic
# from django.template import Context
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.core.urlresolvers import reverse
from django.template.loader import get_template

from anagrafica.models import Persona, Documento
from anagrafica.forms import ModuloCreazioneDocumento
from anagrafica.permessi.applicazioni import DIRETTORE_CORSO
from anagrafica.permessi.costanti import (GESTIONE_CORSI_SEDE,
    GESTIONE_CORSO, ERRORE_PERMESSI, COMPLETO, MODIFICA, ELENCHI_SOCI)
from curriculum.models import TitoloPersonale
from ufficio_soci.elenchi import ElencoPerTitoliCorso
from autenticazione.funzioni import pagina_privata, pagina_pubblica
from base.errori import errore_generico, messaggio_generico # ci_siamo_quasi
from base.files import Zip
from base.models import Log
from base.utils import poco_fa
from posta.models import Messaggio
from survey.models import Survey
from .elenchi import ElencoPartecipantiCorsiBase
from .decorators import can_access_to_course
from .models import (Corso, CorsoBase, CorsoEstensione, AssenzaCorsoBase,
    LezioneCorsoBase, PartecipazioneCorsoBase, Aspirante, InvitoCorsoBase)
from .forms import (ModuloCreazioneCorsoBase, ModuloModificaLezione,
    ModuloModificaCorsoBase, ModuloIscrittiCorsoBaseAggiungi,
    ModuloVerbaleAspiranteCorsoBase)


@pagina_privata
def formazione(request, me):
    contesto = {
        "sedi": me.oggetti_permesso(GESTIONE_CORSI_SEDE),
        "corsi": me.oggetti_permesso(GESTIONE_CORSO),
    }
    return 'formazione.html', contesto


@pagina_privata
def formazione_corsi_base_elenco(request, me):
    contesto = {
        "corsi": me.oggetti_permesso(GESTIONE_CORSO),
        "puo_pianificare": me.ha_permesso(GESTIONE_CORSI_SEDE),
    }
    return 'formazione_corsi_base_elenco.html', contesto


@pagina_privata
def formazione_corsi_base_domanda(request, me):
    contesto = {
        "sedi": me.oggetti_permesso(GESTIONE_CORSI_SEDE),
        "min_sedi": Aspirante.MINIMO_COMITATI,
        "max_km": Aspirante.MASSIMO_RAGGIO,
    }
    return 'formazione_corsi_base_domanda.html', contesto


@pagina_privata
def formazione_corsi_base_nuovo(request, me):
    now = datetime.now() + timedelta(days=14)
    form = ModuloCreazioneCorsoBase(
        request.POST or None,
        request.FILES or None,
        initial={'data_inizio': now, 'data_esame': now + timedelta(days=14)},
        me=me
    )
    form.fields['sede'].queryset = me.oggetti_permesso(GESTIONE_CORSI_SEDE)

    if form.is_valid():
        kwargs = {}
        cd = form.cleaned_data
        tipo, data_inizio, data_esame = cd['tipo'], cd['data_inizio'], cd['data_esame']
        data_esame = data_esame if tipo == Corso.CORSO_NUOVO else data_inizio

        if tipo == Corso.CORSO_NUOVO:
            kwargs['titolo_cri'] = cd['titolo_cri']
            kwargs['cdf_level'] = cd['level']
            kwargs['cdf_area'] = cd['area']
            kwargs['survey'] = Survey.survey_for_corso()

        course = CorsoBase.nuovo(
            anno=data_inizio.year,
            sede=cd['sede'],
            data_inizio=data_inizio,
            data_esame=data_esame,
            tipo=tipo,
            delibera_file=cd['delibera_file'],
            **kwargs
        )

        if cd['locazione'] == form.PRESSO_SEDE:
            course.locazione = course.sede.locazione
            course.save()

        # Il corso è creato. Informa presidenza allegando delibera_file
        course.inform_presidency_with_delibera_file()

        # Rindirizza sulla pagina selezione direttori del corso
        request.session['corso_base_creato'] = course.pk
        return redirect(course.url_direttori)

    context = {
        'modulo': form,
    }
    return 'formazione_corsi_base_nuovo.html', context


@pagina_privata
def formazione_corsi_base_direttori(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, COMPLETO):
        return redirect(ERRORE_PERMESSI)

    continua_url = corso.url

    if 'corso_base_creato' in request.session and int(request.session['corso_base_creato']) == int(pk):
        continua_url = "/formazione/corsi-base/%d/fine/" % int(pk)
        del request.session['corso_base_creato']

    context = {
        "delega": DIRETTORE_CORSO,
        "corso": corso,
        "continua_url": continua_url,
        'puo_modificare': me and me.permessi_almeno(corso, MODIFICA)
    }
    return 'formazione_corsi_base_direttori.html', context


@pagina_privata
def formazione_corsi_base_fine(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, COMPLETO):
        return redirect(ERRORE_PERMESSI)

    if me in corso.delegati_attuali():  # Se sono direttore, continuo.
        redirect(corso.url)

    contesto = {
        "corso": corso,
    }
    return 'formazione_corsi_base_fine.html', contesto


@pagina_pubblica
@can_access_to_course
def aspirante_corso_base_informazioni(request, me=None, pk=None):
    context = dict()
    corso = get_object_or_404(CorsoBase, pk=pk)
    puo_modificare = me and me.permessi_almeno(corso, MODIFICA)
    puoi_partecipare = corso.persona(me) if me else None

    if puoi_partecipare == CorsoBase.NON_HAI_CARICATO_DOCUMENTI_PERSONALI:
        if request.method == 'POST':
            doc = Documento(persona=me)
            load_personal_document_form = ModuloCreazioneDocumento(request.POST,
                request.FILES, instance=doc)

            if load_personal_document_form.is_valid():
                load_personal_document_form.save()
                return redirect(reverse('aspirante:info', kwargs={'pk': corso.pk}))
        else:
            load_personal_document_form = ModuloCreazioneDocumento()

        context['load_personal_document'] = load_personal_document_form

    context['corso'] = corso
    context['puo_modificare'] = puo_modificare
    context['puoi_partecipare'] = puoi_partecipare

    return 'aspirante_corso_base_scheda_informazioni.html', context


@pagina_privata
def aspirante_corso_base_iscriviti(request, me=None, pk=None):
    corso = get_object_or_404(CorsoBase, pk=pk)

    puoi_partecipare = corso.persona(me)
    if not puoi_partecipare in corso.PUOI_ISCRIVERTI:
        return errore_generico(request, me,
           titolo="Non puoi partecipare a questo corso",
           messaggio="Siamo spiacenti, ma non sembra che tu possa partecipare "
                     "a questo corso per qualche motivo.",
           torna_titolo="Torna al corso",
           torna_url=corso.url
        )

    if corso.is_reached_max_participants_limit:
        # TODO: informa direttore
        # send_mail()

        return errore_generico(request, me,
           titolo="Non puoi partecipare a questo corso",
           messaggio="È stato raggiunto il limite massimo di richieste di "
                     "partecipazione al corso.",
           torna_titolo="Torna al corso",
           torna_url=corso.url
        )

    p = PartecipazioneCorsoBase(persona=me, corso=corso)
    p.save()
    p.richiedi()

    return messaggio_generico(request, me,
        titolo="Sei iscritto al corso",
        messaggio="Complimenti! Abbiamo inoltrato la tua richiesta al direttore "
                "del corso, che ti contatterà appena possibile.",
        torna_titolo="Torna al corso",
        torna_url=corso.url
    )


@pagina_privata
def aspirante_corso_base_ritirati(request, me=None, pk=None):

    corso = get_object_or_404(CorsoBase, pk=pk)
    puoi_partecipare = corso.persona(me)
    if not puoi_partecipare == corso.SEI_ISCRITTO_PUOI_RITIRARTI:
        return errore_generico(request, me, titolo="Non puoi ritirarti da questo corso",
                               messaggio="Siamo spiacenti, ma non sembra che tu possa ritirarti "
                                         "da questo corso per qualche motivo. ",
                               torna_titolo="Torna al corso",
                               torna_url=corso.url)

    p = PartecipazioneCorsoBase.con_esito_pending(corso=corso, persona=me).first()
    p.ritira()

    return messaggio_generico(request, me, titolo="Ti sei ritirato dal corso",
                              messaggio="Siamo spiacenti che hai deciso di ritirarti da questo corso. "
                                        "La tua partecipazione è stata ritirata correttamente. "
                                        "Non esitare a iscriverti a questo o un altro corso, nel caso cambiassi idea.",
                              torna_titolo="Torna alla pagina del corso",
                              torna_url=corso.url)


@pagina_privata
@can_access_to_course
def aspirante_corso_base_mappa(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    puo_modificare = me.permessi_almeno(corso, MODIFICA)
    context = {
        "corso": corso,
        "puo_modificare": puo_modificare
    }
    return 'aspirante_corso_base_scheda_mappa.html', context


@pagina_privata
def aspirante_corso_base_lezioni(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    partecipanti = Persona.objects.filter(partecipazioni_corsi__in=corso.partecipazioni_confermate())
    lezioni = corso.lezioni.all()
    moduli = []
    partecipanti_lezioni = []
    for lezione in lezioni:
        form = ModuloModificaLezione(
            request.POST if request.POST and request.POST['azione'] == 'salva' else None,
            instance=lezione,
            corso=corso,
            prefix="%s" % (lezione.pk,)
        )
        if request.POST and request.POST['azione'] == 'salva' and form.is_valid():
            form.save()

        moduli += [form]
        partecipanti_lezione = partecipanti.exclude(assenze_corsi_base__lezione=lezione).order_by('nome', 'cognome')

        if request.POST and request.POST['azione'] == 'salva':
            for partecipante in partecipanti:
                if ("%s" % (partecipante.pk,)) in request.POST.getlist('presenze-%s' % (lezione.pk,)):
                    # Se presente, rimuovi ogni assenza.
                    AssenzaCorsoBase.objects.filter(lezione=lezione, persona=partecipante).delete()
                else:
                    # Assicurati che sia segnato come assente.
                    if not AssenzaCorsoBase.objects.filter(lezione=lezione, persona=partecipante).exists():
                        a = AssenzaCorsoBase(lezione=lezione, persona=partecipante, registrata_da=me)
                        a.save()

        partecipanti_lezioni += [partecipanti_lezione]

    if request.POST and request.POST['azione'] == 'nuova':
        modulo_nuova_lezione = ModuloModificaLezione(request.POST,
                                                     prefix="nuova",
                                                     corso=corso)
        if modulo_nuova_lezione.is_valid():
            lezione = modulo_nuova_lezione.save(commit=False)
            lezione.corso = corso
            lezione.save()

            if corso.is_nuovo_corso:
                # Informa docente della lezione
                lezione.send_messagge_to_docente(me)

            return redirect("%s#%d" % (corso.url_lezioni, lezione.pk,))
    else:
        modulo_nuova_lezione = ModuloModificaLezione(prefix="nuova", initial={
            "inizio": timezone.now(),
            "fine": timezone.now() + timedelta(hours=2)
        }, corso=corso)

    lezioni = zip(lezioni, moduli, partecipanti_lezioni)

    context = {
        "corso": corso,
        "puo_modificare": True,
        "lezioni": lezioni,
        "partecipanti": partecipanti,
        "modulo_nuova_lezione": modulo_nuova_lezione,
    }
    return 'aspirante_corso_base_scheda_lezioni.html', context


@pagina_privata
def aspirante_corso_base_lezioni_cancella(request, me, pk, lezione_pk):

    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    lezione = get_object_or_404(LezioneCorsoBase, pk=lezione_pk)
    if lezione.corso != corso:
        return redirect(ERRORE_PERMESSI)

    lezione.delete()
    return redirect(corso.url_lezioni)


@pagina_privata
def aspirante_corso_base_modifica(request, me, pk):
    from .models import CorsoFile, CorsoLink
    from .forms import CorsoFileFormSet, CorsoLinkFormSet

    course = get_object_or_404(CorsoBase, pk=pk)
    course_files = CorsoFile.objects.filter(corso=course)
    course_links = CorsoLink.objects.filter(corso=course)

    FILEFORM_PREFIX = 'files'
    LINKFORM_PREFIX = 'links'

    if not me.permessi_almeno(course, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    if request.method == 'POST':
        course_form = ModuloModificaCorsoBase(request.POST, instance=course)
        file_formset = CorsoFileFormSet(request.POST, request.FILES,
                                        queryset=course_files,
                                        form_kwargs={'empty_permitted': False},
                                        prefix=FILEFORM_PREFIX)
        link_formset = CorsoLinkFormSet(request.POST,
                                        queryset=course_links,
                                        prefix=LINKFORM_PREFIX)

        if course_form.is_valid():
            course_form.save()

        if file_formset.is_valid():
            file_formset.save(commit=False)

            for obj in file_formset.deleted_objects:
                obj.delete()

            for form in file_formset:
                if form.is_valid() and not form.empty_permitted:
                    instance = form.instance
                    instance.corso = course
            file_formset.save()

        if link_formset.is_valid():
            link_formset.save(commit=False)
            for form in link_formset:
                instance = form.instance
                instance.corso = course
            link_formset.save()

        if course_form.is_valid() and file_formset.is_valid() and \
                link_formset.is_valid():
            return redirect(reverse('aspirante:modify', args=[pk]))
    else:
        course_form = ModuloModificaCorsoBase(instance=course)
        file_formset = CorsoFileFormSet(queryset=course_files, prefix=FILEFORM_PREFIX)
        link_formset = CorsoLinkFormSet(queryset=course_links, prefix=LINKFORM_PREFIX)

    context = {
        'corso': course,
        'puo_modificare': True,
        'modulo': course_form,
        'file_formset': file_formset,
        'link_formset': link_formset,
    }
    return 'aspirante_corso_base_scheda_modifica.html', context


@pagina_privata
def aspirante_corso_base_attiva(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)

    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    if corso.stato != corso.PREPARAZIONE:
        return messaggio_generico(request, me,
                                  titolo="Il corso è già attivo",
                                  messaggio="Non puoi attivare un corso già attivo",
                                  torna_titolo="Torna al Corso",
                                  torna_url=corso.url)
    if not corso.attivabile():
        return errore_generico(request, me,
                               titolo="Impossibile attivare questo corso",
                               messaggio="Non sono soddisfatti tutti i criteri di attivazione. "
                                         "Torna alla pagina del corso e verifica che tutti i "
                                         "criteri siano stati soddisfatti prima di attivare un "
                                         "nuovo corso.",
                               torna_titolo="Torna al Corso",
                               torna_url=corso.url)

    if corso.data_inizio < poco_fa():
        return errore_generico(request, me,
                               titolo="Impossibile attivare un corso già iniziato",
                               messaggio="Siamo spiacenti, ma non possiamo attivare il corso e inviare "
                                         "le e-mail a tutti gli aspiranti nella zona se il corso è "
                                         "già iniziato. Ti inviato a verificare i dati del corso.",
                               torna_titolo="Torna al Corso",
                               torna_url=corso.url)

    email_body = {"corso": corso, "persona": me}
    text = get_template("email_aspirante_corso_inc_testo.html").render(
        email_body)

    if request.POST:
        corso.attiva(rispondi_a=me)
        if corso.is_nuovo_corso:
            messaggio = "A breve tutti i volontari dei segmenti selezionati "\
                        "verranno informati dell'attivazione di questo corso."
        else:
            messaggio = "A breve tutti gli aspiranti nelle vicinanze verranno "\
                        "informati dell'attivazione di questo corso base."
        return messaggio_generico(
            request, me,
            titolo="Corso attivato con successo",
            messaggio=messaggio,
            torna_titolo="Torna al Corso",
            torna_url=corso.url
        )

    context = {
        "corso": corso,
        "puo_modificare": True,
        "testo": text,
    }
    return 'aspirante_corso_base_scheda_attiva.html', context


@pagina_privata
def aspirante_corso_base_termina(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    torna = {"torna_url": corso.url_modifica, "torna_titolo": "Modifica corso"}

    if (not corso.op_attivazione) or (not corso.data_attivazione):
        return errore_generico(request, me, titolo="Necessari dati attivazione",
                               messaggio="Per generare il verbale, sono necessari i dati (O.P. e data) "
                                         "dell'attivazione del corso.",
                               **torna)

    if not corso.partecipazioni_confermate().exists():
        return errore_generico(request, me, titolo="Impossibile terminare questo corso",
                               messaggio="Non ci sono partecipanti confermati per questo corso, "
                                         "non è quindi possibile generare un verbale per il corso.",
                               **torna)

    if corso.stato != corso.ATTIVO:
        return errore_generico(request, me, titolo="Impossibile terminare questo corso",
                               messaggio="Il corso non è attivo e non può essere terminato.",
                               **torna)

    partecipanti_moduli = []

    azione = request.POST.get('azione', default=ModuloVerbaleAspiranteCorsoBase.SALVA_SOLAMENTE)
    generazione_verbale = azione == ModuloVerbaleAspiranteCorsoBase.GENERA_VERBALE
    termina_corso = generazione_verbale

    for partecipante in corso.partecipazioni_confermate():

        form = ModuloVerbaleAspiranteCorsoBase(
            request.POST or None, prefix="part_%d" % partecipante.pk,
            instance=partecipante,
            generazione_verbale=generazione_verbale
        )
        if corso.is_nuovo_corso:
            pass
        else:
            form.fields['destinazione'].queryset = corso.possibili_destinazioni()
            form.fields['destinazione'].initial = corso.sede

        if form.is_valid():
            form.save()
        elif generazione_verbale:
            termina_corso = False

        partecipanti_moduli += [(partecipante, form)]

    if termina_corso:  # Se il corso può essere terminato.
        corso.termina(mittente=me)

        if corso.is_nuovo_corso:
            email_title = "Corso terminato."
            return_title = "Vai al Report del Corso"
        else:
            email_title = "Corso base terminato"
            return_title = "Vai al Report del Corso Base"

        return messaggio_generico(request, me,
          titolo=email_title,
          messaggio="Il verbale è stato generato con successo. Tutti gli idonei "
                    "sono stati resi volontari delle rispettive sedi.",
          torna_titolo=return_title,
          torna_url=corso.url_report
        )

    context = {
        "corso": corso,
        "puo_modificare": True,
        "partecipanti_moduli": partecipanti_moduli,
        "azione_genera_verbale": ModuloVerbaleAspiranteCorsoBase.GENERA_VERBALE,
        "azione_salva_solamente": ModuloVerbaleAspiranteCorsoBase.SALVA_SOLAMENTE,
    }
    return 'aspirante_corso_base_scheda_termina.html', context


@pagina_privata
def aspirante_corso_base_iscritti(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)

    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    elenco = ElencoPartecipantiCorsiBase(corso.queryset_modello())
    in_attesa = corso.partecipazioni_in_attesa()
    context = {
        "corso": corso,
        "puo_modificare": True,
        "elenco": elenco,
        "in_attesa": in_attesa,
    }
    return 'aspirante_corso_base_scheda_iscritti.html', context


@pagina_privata
def aspirante_corso_base_iscritti_cancella(request, me, pk, iscritto):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    if not corso.possibile_cancellare_iscritti:
        return errore_generico(request, me, titolo="Impossibile cancellare iscritti",
                               messaggio="Non si possono cancellare iscritti a questo "
                                         "stadio della vita del corso base.",
                               torna_titolo="Torna al corso base", torna_url=corso.url_iscritti)

    try:
        persona = Persona.objects.get(pk=iscritto)
    except Persona.DoesNotExist:
        return errore_generico(request, me, titolo="Impossibile cancellare iscritto",
                               messaggio="La persona cercata non è iscritta.",
                               torna_titolo="Torna al corso base", torna_url=corso.url_iscritti)
    if request.method == 'POST':
        for partecipazione in corso.partecipazioni_confermate_o_in_attesa().filter(persona=persona):
            partecipazione.disiscrivi(mittente=me)
        for partecipazione in corso.inviti_confermati_o_in_attesa().filter(persona=persona):
            partecipazione.disiscrivi(mittente=me)
        return messaggio_generico(request, me, titolo="Iscritto cancellato",
                                  messaggio="{} è stato cancellato dal corso {}.".format(persona, corso),
                                  torna_titolo="Torna al corso base", torna_url=corso.url_iscritti)
    contesto = {
        "corso": corso,
        "puo_modificare": True,
        "persona": persona,
    }
    return 'aspirante_corso_base_scheda_iscritti_cancella.html', contesto


@pagina_privata
def aspirante_corso_base_iscritti_aggiungi(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)

    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)
    if not corso.possibile_aggiungere_iscritti:
        return errore_generico(request, me,
           titolo="Impossibile aggiungere iscritti",
           messaggio="Non si possono aggiungere altri iscritti a questo "
                     "stadio della vita del corso.",
           torna_titolo="Torna al corso",
           torna_url=corso.url_iscritti
        )

    risultati = []
    form = ModuloIscrittiCorsoBaseAggiungi(request.POST or None, corso=corso)
    if form.is_valid():
        for persona in form.cleaned_data['persone']:
            esito = corso.persona(persona)
            ok = PartecipazioneCorsoBase.NON_ISCRITTO
            partecipazione = None

            if esito in corso.PUOI_ISCRIVERTI or esito in corso.NON_PUOI_ISCRIVERTI_SOLO_SE_IN_AUTONOMIA:
                if hasattr(persona, 'aspirante'):
                    inviti = InvitoCorsoBase.con_esito_ok() | InvitoCorsoBase.con_esito_pending()
                    if inviti.filter(persona=persona, corso=corso).exists():
                        ok = PartecipazioneCorsoBase.INVITO_INVIATO
                        partecipazione = InvitoCorsoBase.objects.filter(persona=persona, corso=corso).first()
                    else:
                        partecipazione = InvitoCorsoBase(persona=persona, corso=corso, invitante=me)
                        partecipazione.save()
                        partecipazione.richiedi()
                        ok = PartecipazioneCorsoBase.IN_ATTESA_ASPIRANTE
                else:
                    partecipazione = PartecipazioneCorsoBase.objects.create(
                        persona=persona,
                        corso=corso
                    )
                    ok = PartecipazioneCorsoBase.ISCRITTO

                    if corso.is_nuovo_corso:
                        subject = "Iscrizione a Corso %s" % corso.titolo_cri
                    else:
                        subject = "Iscrizione a Corso Base"

                    Messaggio.costruisci_e_invia(
                        oggetto=subject,
                        modello="email_corso_base_iscritto.html",
                        corpo={
                            "persona": persona,
                            "corso": corso,
                        },
                        mittente=me,
                        destinatari=[persona]
                    )

                Log.crea(me, partecipazione)

            risultati += [{
                "persona": persona,
                "partecipazione": partecipazione,
                "esito": esito,
                "ok": ok,
            }]

    context = {
        "corso": corso,
        "puo_modificare": True,
        "modulo": form,
        "risultati": risultati,
    }
    return 'aspirante_corso_base_scheda_iscritti_aggiungi.html', context


@pagina_privata
def aspirante_corso_base_firme(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    archivio = corso.genera_pdf_firme()
    return redirect(archivio.download_url)


@pagina_privata
def aspirante_corso_base_report(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    contesto = {
        "corso": corso,
        "puo_modificare": True,
    }
    return 'aspirante_corso_base_scheda_report.html', contesto


@pagina_privata
def aspirante_corso_base_report_schede(request, me, pk):
    corso = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(corso, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    archivio = Zip(oggetto=corso)
    for p in corso.partecipazioni_confermate():

        # Genera la scheda di valutazione.
        scheda = p.genera_scheda_valutazione()
        archivio.aggiungi_file(scheda.file.path, "%s - Scheda di Valutazione.pdf" % p.persona.nome_completo)

        # Se idoneo, genera l'attestato.
        if p.idoneo:
            attestato = p.genera_attestato()
            archivio.aggiungi_file(attestato.file.path, "%s - Attestato.pdf" % p.persona.nome_completo)

    archivio.comprimi_e_salva(nome="Corso %d-%d.zip" % (corso.progressivo, corso.anno))
    return redirect(archivio.download_url)


@pagina_privata
def aspirante_home(request, me):
    if not me.ha_aspirante:
        return redirect(ERRORE_PERMESSI)

    contesto = {}
    return 'aspirante_home.html', contesto


@pagina_privata
@can_access_to_course
def aspirante_corsi(request, me):
    """ url: /aspirante/corsi/ """

    if me.ha_aspirante:
        corsi = me.aspirante.corsi(tipo=Corso.BASE)
    elif me.volontario:
        corsi = CorsoBase.find_courses_for_volunteer(volunteer=me)

    context = {
        'corsi':  corsi
    }
    return 'aspirante_corsi_base.html', context


@pagina_privata
def aspirante_sedi(request, me):
    if not me.ha_aspirante:
        return redirect(ERRORE_PERMESSI)

    contesto = {
        "sedi": me.aspirante.sedi(),
    }
    return 'aspirante_sedi.html', contesto


@pagina_privata
def aspirante_impostazioni(request, me):
    if not me.ha_aspirante:
        return redirect(ERRORE_PERMESSI)

    contesto = {}
    return 'aspirante_impostazioni.html', contesto


@pagina_privata
def aspirante_impostazioni_cancella(request, me):
    if not me.ha_aspirante:
        return redirect(ERRORE_PERMESSI)

    if not me.cancellabile:
        return errore_generico(request, me,
            titolo="Impossibile cancellare automaticamente il profilo da Gaia",
            messaggio="E' necessario richiedere la cancellazione manuale al personale di supporto."
        )

    # Cancella!
    me.delete()

    return messaggio_generico(request, me,
        titolo="Il tuo profilo è stato cancellato da Gaia",
        messaggio="Abbiamo rimosso tutti i tuoi dati dal nostro sistema. "
                "Se cambierai idea, non esitare a iscriverti nuovamente! "
    )


@pagina_privata
def aspirante_corso_estensioni_modifica(request, me, pk):
    from .forms import CorsoSelectExtensionTypeForm, CorsoSelectExtensionFormSet

    SELECT_EXTENSION_TYPE_FORM_PREFIX = 'extension_type'
    SELECT_EXTENSIONS_FORMSET_PREFIX = 'extensions'

    course = get_object_or_404(CorsoBase, pk=pk)
    if not me.permessi_almeno(course, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    if not course.tipo == Corso.CORSO_NUOVO:
        # The page is not accessible if the type of course is not CORSO_NUOVO
        return redirect(ERRORE_PERMESSI)

    if request.method == 'POST':
        select_extension_type_form = CorsoSelectExtensionTypeForm(request.POST,
                                    instance=course,
                                    prefix=SELECT_EXTENSION_TYPE_FORM_PREFIX)
        select_extensions_formset = CorsoSelectExtensionFormSet(request.POST,
                                    prefix=SELECT_EXTENSIONS_FORMSET_PREFIX,
                                    form_kwargs={'corso': course})

        if select_extension_type_form.is_valid() and \
            select_extensions_formset.is_valid():
            select_extensions_formset.save(commit=False)

            for form in select_extensions_formset:
                if form.is_valid:
                    cd = form.cleaned_data
                    instance = form.save(commit=False)
                    instance.corso = course
                    corso = instance.corso

                    # Skip blank extra formset
                    if cd == {} and len(select_extensions_formset) > 1:
                        continue

                    # Do validation only with specified extension type
                    if corso.extension_type == CorsoBase.EXT_LVL_REGIONALE:
                        msg = 'Questo campo è obbligatorio.'
                        if not cd.get('sede'):
                            form.add_error('sede', msg)
                        if not cd.get('segmento'):
                            form.add_error('segmento', msg)
                        if cd.get('sedi_sottostanti') and not cd.get('sede'):
                            form.add_error('sede', 'Seleziona una sede')

                    # No errors nor new added error - save form instance
                    if not form.errors:
                        instance.save()

            # Return form with error without saving
            if any(select_extensions_formset.errors):
                pass
            else:
                # Save all forms and redirect to the same page.
                select_extension_type_form.save()
                select_extensions_formset.save()

                # Set EXT_MIA_SEDE if course has no extensions
                reset_corso_ext = CorsoBase.objects.get(pk=pk)
                corso_has_extensions = reset_corso_ext.has_extensions()
                new_objects = select_extensions_formset.new_objects
                if not corso_has_extensions and not new_objects:
                    reset_corso_ext.extension_type = CorsoBase.EXT_MIA_SEDE
                    reset_corso_ext.save()

                return redirect(reverse('aspirante:estensioni_modifica', args=[pk]))

    else:
        select_extension_type_form = CorsoSelectExtensionTypeForm(
            prefix=SELECT_EXTENSION_TYPE_FORM_PREFIX,
            instance=course,
        )
        select_extensions_formset = CorsoSelectExtensionFormSet(
            prefix=SELECT_EXTENSIONS_FORMSET_PREFIX,
            form_kwargs={'corso': course},
            queryset=CorsoEstensione.objects.filter(corso=course)
        )

    context = {
        'corso': course,
        'puo_modificare': True,
        'select_extension_type_form': select_extension_type_form,
        'select_extensions_formset': select_extensions_formset,
    }
    return 'aspirante_corso_estensioni_modifica.html', context


@pagina_privata
def aspirante_corso_estensioni_informa(request, me, pk):
    from .forms import InformCourseParticipantsForm
    from django.contrib import messages

    course = get_object_or_404(CorsoBase, pk=pk)

    if not me.permessi_almeno(course, MODIFICA):
        return redirect(ERRORE_PERMESSI)

    qs = Persona.objects.filter()
    form_data = {
        'instance': course,
    }
    form = InformCourseParticipantsForm(request.POST or None, **form_data)
    if form.is_valid():
        cd = form.cleaned_data
        recipients = PartecipazioneCorsoBase.objects.none()
        sent_with_success = False

        recipient_type = cd['recipient_type']
        if recipient_type == form.ALL:
            recipients = course.partecipazioni_in_attesa() | course.partecipazioni_confermate()
        elif recipient_type == form.UNCONFIRMED_REQUESTS:
            recipients = course.partecipazioni_in_attesa()
        elif recipient_type == form.CONFIRMED_REQUESTS:
            recipients = course.partecipazioni_confermate()
        elif recipient_type == form.INVIA_QUESTIONARIO:
            recipients = course.partecipazioni_confermate()
        else:
            # todo: something went wrong ...
            pass

        if recipients and not recipient_type == form.INVIA_QUESTIONARIO:
            sent_with_success = Messaggio.costruisci_e_invia(
                oggetto="Informativa dal direttore %s (%s)" % (course.nome, course.titolo_cri),
                modello="email_corso_informa_participants.html",
                corpo={
                    'corso': course,
                    'message': cd['message'],
                },
                mittente=me,
                destinatari=[r.persona for r in recipients]
            )

        if recipients and recipient_type == form.INVIA_QUESTIONARIO:
            sent_with_success = Messaggio.costruisci_e_invia(
                oggetto="Questionario di gradimento del %s per %s" % (course.nome, course.titolo_cri),
                modello="email_corso_questionario_gradimento.html",
                corpo={
                    'corso': course,
                    'message': cd['message']
                },
                mittente=me,
                destinatari=[r.persona for r in recipients]
            )

        if sent_with_success:
            messages.success(request, "Il messaggio ai volontari è stato inviato con successo. ")
            return redirect(reverse('aspirante:informa', args=[pk]))

        if not recipients:
            messages.success(request,  "Il messaggio non è stato inviato a nessuno.")
            return redirect(reverse('aspirante:informa', args=[pk]))

    context = {
        'corso': course,
        'form': form,
        'puo_modificare': True,
    }
    return 'aspirante_corso_informa_persone.html', context


@pagina_privata
def formazione_albo_informatizzato(request, me):
    sedi = me.oggetti_permesso(ELENCHI_SOCI)
    context = {
        'elenco_nome': 'Albo Informatizzato',
        'elenco_template': None,
    }

    # Step 2: Elaborare elenco per le sedi selezionate
    if request.method == 'POST':
        elenco = ElencoPerTitoliCorso(sedi.filter(pk__in=request.POST.getlist('sedi')))
        context['elenco'] = elenco
        return 'formazione_albo_elenco_generico.html', context

    # Step 1: Selezione sedi
    context['sedi'] = sedi
    return 'formazione_albo_informatizzato.html', context


@pagina_privata
def formazione_albo_titoli_corso_full_list(request, me):
    context = {}
    if 'persona_id' in request.GET:
        persona = Persona.objects.get(id=request.GET['persona_id'])
        titles = TitoloPersonale.objects.filter(persona=persona,
                                                is_course_title=True)
        context['titles'] = titles.order_by('titolo__nome', '-data_scadenza')
        context['person'] = persona

    return 'formazione_albo_titoli_corso_full_list.html', context
