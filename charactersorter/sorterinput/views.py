# pylint: disable-msg=too-many-ancestors
# from django.shortcuts import render
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views import generic
from django.conf import settings
import requests

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

def get_list_and_controller(list_id):
    charlist = get_object_or_404(CharacterList, pk=list_id)
    controller_cls_name = charlist.get_controller_class_name()
    controller_obj = (controller.models.CONTROLLER_TYPES[controller_cls_name])()
    return charlist, controller_obj

def get_char_image(character):
    """searches for the specified character on Google Images with a custom
    search engine. See
    https://developers.google.com/custom-search/json-api/v1/reference/cse/list
    """
    uri = "https://www.googleapis.com/customsearch/v1"
    payload = {
        "key": settings.IMAGE_SEARCH_KEY,
        "cx": settings.IMAGE_SEARCH_CX,
        "q" : "{} from {}".format(character.name, character.fandom),
        "num": 1,
        "searchType": "image",
    }
    print(payload)
    r = requests.get(uri, params=payload)
    j = r.json()
    print(j["items"][0])
    return j["items"][0]["image"]

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
    charlist, controller_obj = get_list_and_controller(list_id)
    sorted_char_ids = controller_obj.get_sorted_chars(charlist)
    chars = Character.objects.filter(id__in=sorted_char_ids)
    chars_by_id = {char.id: char for char in chars}
    sorted_chars = [chars_by_id[char_id] for char_id in sorted_char_ids]
    annotations = controller_obj.get_annotations(charlist)
    graph_info = controller_obj.get_graph_info(charlist)
    progress_info = controller_obj.get_progress_info(charlist)
    context = {
        "charlist": charlist,
        "sortedchars": sorted_chars,
        "annotations": annotations,
        "has_graph": graph_info is not None,
        "progress_info": progress_info
    }
    return render(request, "sorterinput/view.html", context)

@requires_list_owner
def graphlist(request, list_id):
    charlist, controller_obj = get_list_and_controller(list_id)
    graph_info = controller_obj.get_graph_info(charlist)
    if graph_info is None:
        return render(request, "sorterinput/nograph.html", {})
    else:
        context = {
            "charlist": charlist,
            "graph_info": graph_info
        }
        return render(request, "sorterinput/graph.html", context)

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
    charlist, controller_obj = get_list_and_controller(list_id)
    error_msg = None
    if request.method == "POST":
        try:
            result = int(request.POST["sort"])
            controller_obj.register_comparison(
                charlist,
                request.POST["char1"], request.POST["char2"],
                result)
            return HttpResponseRedirect(reverse(
                'sorterinput:sortlist', args=(list_id,)))
        except KeyError:
            error_msg = "You didn't select a choice."
    comparison = controller_obj.get_next_comparison(charlist)
    if comparison is None:
        char1, char2 = None, None
        img1, img2 = None, None
    else:
        char1, char2 = comparison
        char1 = Character.objects.get(pk=char1)
        img1 = get_char_image(char1)
        char2 = Character.objects.get(pk=char2)
        img2 = get_char_image(char2)
    try:
        lastsort = controller.models.SortRecord.objects.filter(
            charlist=charlist).order_by("-timestamp", "-id")[0]
    except IndexError:
        lastsort = None
    progress_info = controller_obj.get_progress_info(charlist)
    context = {
        "charlist": charlist,
        "progress_info": progress_info,
        "char1": char1,
        "img1": img1,
        "char2": char2,
        "img2": img2,
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
