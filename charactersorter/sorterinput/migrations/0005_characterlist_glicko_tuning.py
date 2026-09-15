import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """Per-list Glicko tuning.

    initial_rd and rd_reset_days are added with the *old* behaviour as their
    default and then altered to the new one. AddField backfills existing rows,
    AlterField does not, so lists that already exist keep the rankings they
    have -- initial_rd 350 against a 350 ceiling reproduces today exactly --
    while lists made afterwards get the retuned values. No data migration.
    """

    dependencies = [
        ('sorterinput', '0004_characterlist_show_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='characterlist',
            name='initial_rd',
            field=models.PositiveIntegerField(default=350, help_text='Uncertainty for a character with no comparisons yet. Keep it above the decay ceiling, or new characters lose priority to stale ones.', validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='characterlist',
            name='match_recency_days',
            field=models.PositiveIntegerField(default=90, help_text='Days before a rematch is weighted as freely as a pairing that has never been asked.', validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='characterlist',
            name='max_decay_rd',
            field=models.PositiveIntegerField(default=350, help_text='Ceiling that idle time alone can push uncertainty to.', validators=[django.core.validators.MinValueValidator(51)]),
        ),
        migrations.AddField(
            model_name='characterlist',
            name='rd_reset_days',
            field=models.PositiveIntegerField(default=90, help_text='Days for a well-ranked character to drift up to that ceiling.', validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name='characterlist',
            name='initial_rd',
            field=models.PositiveIntegerField(default=450, help_text='Uncertainty for a character with no comparisons yet. Keep it above the decay ceiling, or new characters lose priority to stale ones.', validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name='characterlist',
            name='rd_reset_days',
            field=models.PositiveIntegerField(default=365, help_text='Days for a well-ranked character to drift up to that ceiling.', validators=[django.core.validators.MinValueValidator(1)]),
        ),
    ]
