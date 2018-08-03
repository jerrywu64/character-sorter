# pylint: disable-msg=too-many-ancestors
# from django.shortcuts import render
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views import generic

import controller.models
from .forms import \
    ModifyCharFormset, AddCharForm, ModifyCharlistFormset, AddCharlistForm
from .models import CharacterList, Character

def requires_list_owner(f):
    def checked_f(request, list_id, *args):
        if request.user.is_authenticated:
            charlist = get_object_or_404(CharacterList, pk=list_id)
            if charlist.owner.id == request.user.id or request.user.is_superuser:
                return f(request, list_id, *args)
        raise Http404("No CharacterList matches the given query.")
    return checked_f

class IndexView(generic.ListView):
    template_name = "sorterinput/index.html"
    context_object_name = "character_lists"

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return None
        return CharacterList.objects.filter(owner=self.request.user)

def get_list_and_class(list_id):
    charlist = get_object_or_404(CharacterList, pk=list_id)
    controller_cls_name = charlist.get_controller_class_name()
    controller_cls = controller.models.CONTROLLER_TYPES[controller_cls_name]
    return charlist, controller_cls

def editcharlists(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('login'))

    if request.method == "POST":
        modformset = ModifyCharlistFormset(
            request.POST,
            queryset=CharacterList.objects.filter(owner=request.user))
        addform = AddCharlistForm(request.POST)
        if addform.is_valid():
            addform.save()
            return HttpResponseRedirect(reverse(
                'sorterinput:editcharlists'))

        if modformset.is_valid():
            modformset.save()
            return HttpResponseRedirect(reverse(
                'sorterinput:editcharlists'))

    else:
        modformset = ModifyCharlistFormset(
            queryset=CharacterList.objects.filter(owner=request.user))
        addform = AddCharlistForm(initial={"owner": request.user})
    context = {
        "modformset": modformset,
        "addform": addform,
    }
    return render(request, "sorterinput/editlists.html", context)

@requires_list_owner
def viewlist(request, list_id):
    charlist, controller_cls = get_list_and_class(list_id)
    sorted_char_ids = controller_cls.get_sorted_chars(charlist)
    chars = Character.objects.filter(id__in=sorted_char_ids)
    chars_by_id = {char.id: char for char in chars}
    sorted_chars = [chars_by_id[char_id] for char_id in sorted_char_ids]
    annotations = controller_cls.get_annotations(charlist)
    context = {
        "charlist": charlist,
        "sortedchars": sorted_chars,
        "annotations": annotations,
    }
    return render(request, "sorterinput/view.html", context)

@requires_list_owner
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

@requires_list_owner
def sortlist(request, list_id):
    charlist, controller_cls = get_list_and_class(list_id)
    error_msg = None
    if request.method == "POST":
        try:
            result = int(request.POST["sort"])
            controller_cls.register_comparison(
                charlist,
                request.POST["char1"], request.POST["char2"],
                result)
            return HttpResponseRedirect(reverse(
                'sorterinput:sortlist', args=(list_id,)))
        except KeyError:
            error_msg = "You didn't select a choice."
    comparison = controller_cls.get_next_comparison(charlist)
    if comparison is None:
        char1, char2 = None, None
    else:
        char1, char2 = comparison
        char1 = Character.objects.get(pk=char1)
        char2 = Character.objects.get(pk=char2)
    try:
        lastsort = controller.models.SortRecord.objects.filter(
            charlist=charlist).order_by("-timestamp", "-id")[0]
    except IndexError:
        lastsort = None
    context = {
        "charlist": charlist,
        "char1": char1,
        "char2": char2,
        "done": comparison is None,
        "lastsort": lastsort,
        "error_message": error_msg
    }
    return render(request, "sorterinput/sort.html", context)

@requires_list_owner
def undo(request, list_id):
    lastsort = get_object_or_404(
        controller.models.SortRecord, pk=int(request.POST["last"]))
    lastsort.delete()
    return HttpResponseRedirect(reverse(
        'sorterinput:sortlist', args=(list_id,)))
