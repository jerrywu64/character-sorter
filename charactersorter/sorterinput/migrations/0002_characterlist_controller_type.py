# Generated by Django 2.0.6 on 2018-07-12 07:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sorterinput', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='characterlist',
            name='controller_type',
            field=models.CharField(choices=[('IS', 'InsertionSortController')], default='IS', max_length=2),
        ),
    ]
