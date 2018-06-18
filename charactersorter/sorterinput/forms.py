from django import forms

from .models import Character

ModifyCharFormset = forms.modelformset_factory(
    Character, fields=["name", "fandom"], can_delete=True,
    extra=0)

class AddCharForm(forms.ModelForm):
    class Meta:
        model = Character
        fields = ["characterlist", "name", "fandom"]
        widgets = {"characterlist": forms.HiddenInput()}
