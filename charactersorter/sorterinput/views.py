# pylint: disable-msg=too-many-ancestors
# from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views import generic

from .forms import ModifyCharFormset, AddCharForm
from .models import CharacterList, Character

class IndexView(generic.ListView):
    template_name = "sorterinput/index.html"
    context_object_name = "character_lists"

    def get_queryset(self):
        return CharacterList.objects.all()

class ViewListView(generic.DetailView):
    model = CharacterList
    template_name = "sorterinput/view.html"
    context_object_name = "charlist"

def editlist(request, list_id):
    charlist = get_object_or_404(CharacterList, pk=list_id)
    if request.method == "POST":
        modformset = ModifyCharFormset(request.POST)
        addform = AddCharForm(request.POST)
        if addform.is_valid():
            addform.save()
            return HttpResponseRedirect(reverse(
                'sorterinput:editlist', args=(list_id,)))

        if modformset.is_valid():
            modformset.save()
            return HttpResponseRedirect(reverse(
                'sorterinput:editlist', args=(list_id,)))

    else:
        modformset = ModifyCharFormset(
            queryset=Character.objects.filter(characterlist__id=list_id))
        addform = AddCharForm(initial={"characterlist": list_id})
    context = {
        "charlist": charlist,
        "modformset": modformset,
        "addform": addform,
    }
    return render(request, "sorterinput/edit.html", context)
