from django.db import migrations, models


class Migration(migrations.Migration):
    """Per-list Glicko tuning.

    Each field is added with the *old* behaviour as its default, so existing
    lists keep the rankings they already have, then altered to the new default
    for lists created afterwards. AddField backfills existing rows; AlterField
    does not, so no data migration is needed.
    """

    dependencies = [
        ('sorterinput', '0004_characterlist_show_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='characterlist',
            name='initial_rd',
            field=models.PositiveIntegerField(default=350),
        ),
        migrations.AddField(
            model_name='characterlist',
            name='max_decay_rd',
            field=models.PositiveIntegerField(default=350),
        ),
        migrations.AddField(
            model_name='characterlist',
            name='rd_reset_days',
            field=models.PositiveIntegerField(default=90),
        ),
        migrations.AddField(
            model_name='characterlist',
            name='match_recency_days',
            field=models.PositiveIntegerField(default=90),
        ),
        migrations.AlterField(
            model_name='characterlist',
            name='initial_rd',
            field=models.PositiveIntegerField(default=450),
        ),
        migrations.AlterField(
            model_name='characterlist',
            name='rd_reset_days',
            field=models.PositiveIntegerField(default=365),
        ),
    ]
