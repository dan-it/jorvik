# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2018-11-27 15:47
from __future__ import unicode_literals

import anagrafica.validators
from django.db import migrations, models
import formazione.validators


class Migration(migrations.Migration):

    dependencies = [
        ('formazione', '0028_auto_20181122_1700'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='assenzacorsobase',
            options={'permissions': (('view_assenzacorsobase', 'Can view corso Assenza a Corso Base'),), 'verbose_name': 'Assenza a Corso', 'verbose_name_plural': 'Assenze ai Corsi'},
        ),
        migrations.AlterModelOptions(
            name='corsobase',
            options={'ordering': ['-anno', '-progressivo'], 'permissions': (('view_corsobase', 'Can view corso base'),), 'verbose_name': 'Corso', 'verbose_name_plural': 'Corsi'},
        ),
        migrations.AlterModelOptions(
            name='invitocorsobase',
            options={'ordering': ('persona__cognome', 'persona__nome', 'persona__codice_fiscale'), 'permissions': (('view_invitocorsobase', 'Can view invito partecipazione corso base'),), 'verbose_name': 'Invito di partecipazione a corso', 'verbose_name_plural': 'Inviti di partecipazione a corso'},
        ),
        migrations.AlterModelOptions(
            name='lezionecorsobase',
            options={'ordering': ['inizio'], 'permissions': (('view_lezionecorsobase', 'Can view corso Lezione di Corso Base'),), 'verbose_name': 'Lezione di Corso', 'verbose_name_plural': 'Lezioni di Corsi'},
        ),
        migrations.AddField(
            model_name='lezionecorsobase',
            name='luogo',
            field=models.CharField(blank=True, help_text='Compilare nel caso il luogo è diverso dal comitato che ha organizzato il corso.', max_length=255, null=True, verbose_name='il luogo di dove si svolgeranno le lezioni'),
        ),
        migrations.AlterField(
            model_name='corsofile',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to=formazione.validators.course_file_directory_path, validators=[anagrafica.validators.valida_dimensione_file_8mb, formazione.validators.validate_file_extension], verbose_name='FIle'),
        ),
    ]
