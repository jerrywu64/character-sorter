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

class RangeInput(forms.NumberInput):
    input_type = "range"

# Glicko tuning. Shown on both charlist forms but kept behind a disclosure,
# since the defaults are right for almost every list.
TUNING_FIELDS = [
    "initial_rd", "max_decay_rd", "rd_reset_days", "match_recency_days"]

TUNING_BOUNDS = {
    "initial_rd": (50, 700),
    "max_decay_rd": (51, 700),
    "rd_reset_days": (30, 730),
    "match_recency_days": (7, 365),
}

class TuningFormMixin(object):
    """Shared handling of the Glicko tuning fields.

    They are optional on every form: a client editing only a title must not
    have to resend them, and an omitted one leaves the model default in place.
    The bounds are applied here rather than through Meta.widgets because
    PositiveIntegerField.formfield() sets min itself and would win.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, bounds in TUNING_BOUNDS.items():
            field = self.fields.get(name)
            if field is None:
                continue
            field.required = False
            # step 1: a coarse step would snap the slider away from a value
            # typed into the number box beside it.
            field.widget.attrs.update(
                {"min": bounds[0], "max": bounds[1], "step": 1})

    def basic_fields(self):
        return [f for f in self.visible_fields()
                if f.name not in TUNING_FIELDS]

    def tuning_fields(self):
        return [f for f in self.visible_fields()
                if f.name in TUNING_FIELDS]

class TuningModelForm(TuningFormMixin, forms.ModelForm):
    """Base for any form that exposes the tuning, including the API's."""

def tuning_widgets():
    return {name: RangeInput() for name in TUNING_FIELDS}

class ModifyCharlistForm(TuningModelForm):
    class Meta:
        model = CharacterList
        fields = MaybeAppendShowImages(
            ["title", "controller_type"]) + TUNING_FIELDS
        widgets = tuning_widgets()

ModifyCharlistFormset = forms.modelformset_factory(
    CharacterList, form=ModifyCharlistForm, can_delete=True, extra=0)

class AddCharForm(forms.ModelForm):
    """characterlist is set by the view from the URL, not submitted by the
    client, so it can't be pointed at someone else's list."""
    class Meta:
        model = Character
        fields = ["name", "fandom"]

class PasteCharsForm(forms.Form):
    """Free text parsed by sorterinput.paste, not a ModelForm: one paste
    makes any number of characters."""
    paste = forms.CharField(
        label="Characters",
        help_text=("One per line, as \"Name (Fandom)\" or a \"[Fandom]\" "
                   "line followed by bare names. Duplicates are skipped."),
        widget=forms.Textarea(attrs={"rows": 8}))

class AddCharlistForm(TuningModelForm):
    """owner is set by the view from request.user; same reasoning."""
    class Meta:
        model = CharacterList
        fields = MaybeAppendShowImages(
            ["title", "controller_type"]) + TUNING_FIELDS
        widgets = tuning_widgets()
