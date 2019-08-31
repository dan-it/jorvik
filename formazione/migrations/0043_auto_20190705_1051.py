# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2019-07-05 10:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formazione', '0042_auto_20190606_1429'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partecipazionecorsobase',
            name='ammissione',
            field=models.CharField(blank=True, choices=[('AM', 'Ammesso'), ('NA', 'Non Ammesso'), ('AS', 'Assente'), ('MO', 'Assente per motivo giustificato')], db_index=True, default=None, max_length=2, null=True),
        ),
    ]
