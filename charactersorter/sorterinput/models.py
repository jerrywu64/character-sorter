from django.db import models
from django.contrib.auth.models import User

class CharacterList(models.Model):
    INSERTION = "IS"
    GLICKO = "GL"
    CONTROLLER_CHOICES = (
        (INSERTION, "InsertionSortController"),
        (GLICKO, "GlickoRatingController"),
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    controller_type = models.CharField(
        max_length=2, choices=CONTROLLER_CHOICES, default=INSERTION)
    show_images = models.BooleanField(default=False)

    # Glicko tuning, per list, read by GlickoRatingController.settings_for.
    # initial_rd sitting above max_decay_rd is what separates "never compared"
    # from "compared long ago": at 450 a new character is ~99x likelier to be
    # picked than a top-rated fully-decayed one, where sharing 350 made it 65x
    # *less* likely. rd_reset_days is how long TYPICAL_RD takes to reach the
    # ceiling; match_recency_days caps rematch weighting only, never decay.
    initial_rd = models.PositiveIntegerField(default=450)
    max_decay_rd = models.PositiveIntegerField(default=350)
    rd_reset_days = models.PositiveIntegerField(default=365)
    match_recency_days = models.PositiveIntegerField(default=90)

    def get_controller_class_name(self):
        for shortkey, name in self.CONTROLLER_CHOICES:
            if shortkey == self.controller_type:
                return name
        assert False, "Controller class {} doesn't exist".format(
            self.controller_type)
        return None

    def __str__(self):
        return self.title


class Character(models.Model):
    characterlist = models.ForeignKey(CharacterList, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    fandom = models.CharField(max_length=200)

    def __str__(self):
        return "{} ({})".format(self.name, self.fandom)


class CharacterImageRecord(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    thumbnail_link = models.TextField()
    context_link = models.TextField()
