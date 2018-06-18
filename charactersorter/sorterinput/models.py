from django.db import models
from django.contrib.auth.models import User

class CharacterList(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class Character(models.Model):
    characterlist = models.ForeignKey(CharacterList, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    fandom = models.CharField(max_length=200)

    def __str__(self):
        return "{} ({})".format(self.name, self.fandom)
