# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2019-04-29 09:53
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attivita', '0023_auto_20190423_1450'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='nonsonounbersaglio',
            options={'permissions': (('view_nonSonoUnBersaglio', 'Can view non sono un bersaglio'),), 'verbose_name_plural': 'Referenti non sono un bersaglio'},
        ),
    ]