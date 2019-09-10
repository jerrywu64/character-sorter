from django import forms
from django.conf import settings

from .models import Character, CharacterList

def MaybeAppendShowImages(l):
    if settings.IMAGE_SEARCH_KEY == "":
        return l
    return l + ["show_images"]

ModifyCharFormset = forms.modelformset_factory(
    Character, fields=["name", "fandom"], can_delete=True,
    extra=0)

ModifyCharlistFormset = forms.modelformset_factory(
    CharacterList, fields=MaybeAppendShowImages(["title", "controller_type"]), can_delete=True,
    extra=0)

class AddCharForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = ["characterlist", "name", "fandom"]
        widgets = {"characterlist": forms.HiddenInput()}

class AddCharlistForm(forms.ModelForm):
    class Meta:
        model = CharacterList
        fields = MaybeAppendShowImages(["owner", "title", "controller_type"])
        widgets = {"owner": forms.HiddenInput()}
