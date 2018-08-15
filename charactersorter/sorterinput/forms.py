from django import forms

from .models import Character, CharacterList

ModifyCharFormset = forms.modelformset_factory(
    Character, fields=["name", "fandom"], can_delete=True,
    extra=0)

ModifyCharlistFormset = forms.modelformset_factory(
    CharacterList, fields=["title", "controller_type", "show_images"], can_delete=True,
    extra=0)

class AddCharForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = ["characterlist", "name", "fandom"]
        widgets = {"characterlist": forms.HiddenInput()}

class AddCharlistForm(forms.ModelForm):
    class Meta:
        model = CharacterList
        fields = ["owner", "title", "controller_type", "show_images"]
        widgets = {"owner": forms.HiddenInput()}
