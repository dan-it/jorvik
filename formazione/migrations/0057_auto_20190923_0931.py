# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2019-09-23 09:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formazione', '0056_auto_20190916_1619'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lezionecorsobase',
            name='docente',
            field=models.ManyToManyField(blank=True, to='anagrafica.Persona', verbose_name='Docente della lezione'),
        ),
    ]
