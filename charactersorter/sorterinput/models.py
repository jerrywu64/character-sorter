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
