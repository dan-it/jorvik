from django.db import models
from anagrafica.models import Persona


class Survey(models.Model):
    FORMAZIONE = 'f'
    SURVEY_TYPE_CHOICES = (
        (FORMAZIONE, 'Formazione'),
    )

    is_active = models.BooleanField(default=True)
    text = models.CharField(max_length=255)
    survey_type = models.CharField(max_length=3, choices=SURVEY_TYPE_CHOICES,
                                   null=True, blank=True)

    def get_questions(self):
        return self.question_set.all()

    def get_my_responses(self, user):
        return SurveyResult.objects.filter(user=user, survey=self)

    def get_responses_dict(self, me):
        d = dict()
        for r in self.get_my_responses(me):
            qid = r.question.qid
            if qid not in d:
                d[qid] = dict(response=r.response, object=r)
        return d

    def is_course_admin(self, me, course):
        from anagrafica.permessi.costanti import MODIFICA
        return me and me.permessi_almeno(course, MODIFICA)

    def can_vote(self, me, course):
        """
        Cannot vote because is not participant of the course
        or the course is not ended yet.
        """
        if self.is_course_admin(me, course):
            return True
        elif me in [p.persona for p in course.partecipazioni_confermate()]:
            if course.concluso:
                return True
        return False

    def has_user_responses(self, course):
        return SurveyResult.get_responses_for_course(course).exists()

    @classmethod
    def survey_for_corso(cls):
        try:
            return cls.objects.get(id=2)
        except Survey.DoesNotExist:
            s = cls.objects.filter(survey_type=cls.FORMAZIONE, is_active=True)
            return s.last() if s.exists() else None

    class Meta:
        verbose_name = 'Questionario di gradimento'
        verbose_name_plural = 'Questionari di gradimento'

    def __str__(self):
        return str(self.text)


class Question(models.Model):
    TEXT = 'text'
    RADIO = 'radio'
    SELECT = 'select'
    SELECT_MULTIPLE = 'select-multiple'
    INTEGER = 'integer'

    QUESTION_TYPES = (
        (TEXT, 'text'),
        (RADIO, 'radio'),
        (SELECT, 'select'),
        (SELECT_MULTIPLE, 'Select Multiple'),
        (INTEGER, 'integer'),
    )

    text = models.CharField(max_length=255)
    survey = models.ForeignKey(Survey)
    is_active = models.BooleanField(default=True)
    required = models.BooleanField(default=True, verbose_name='Obbligatorio')
    question_group = models.ForeignKey('QuestionGroup', null=True, blank=True)

    # question_type = models.CharField(max_length=100, choices=QUESTION_TYPES,
    #                                  default=TEXT, null=True, blank=True)

    @property
    def qid(self):
        return 'qid_%s' % self.pk

    class Meta:
        verbose_name = 'Domanda'
        verbose_name_plural = 'Domande'

    def __str__(self):
        return str(self.text)


class SurveyResult(models.Model):
    user = models.ForeignKey(Persona)
    course = models.ForeignKey('formazione.CorsoBase', blank=True, null=True)
    survey = models.ForeignKey(Survey)
    question = models.ForeignKey(Question)
    response = models.TextField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_responses_for_course(cls, course):
        return cls.objects.filter(course=course)

    @classmethod
    def generate_report_for_course(cls, course):
        import csv
        from django.shortcuts import HttpResponse

        filename = "Questionario di gradimento [%s].csv" % course.nome
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s"' % filename

        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Corso', 'Domanda', 'Risposta', 'Creato', 'Modificato'])

        for result in cls.get_responses_for_course(course):
            writer.writerow([
                course.nome,
                result.question,
                result.response,
                result.created_at,
                result.updated_at
            ])

        return response

    class Meta:
        verbose_name = "Risposta dell'utente"
        verbose_name_plural = "Risposte degli utenti"

    def __str__(self):
        return "%s = %s" % (self.survey, self.user)


class QuestionGroup(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return str(self.name)
