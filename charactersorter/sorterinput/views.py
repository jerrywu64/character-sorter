# from django.shortcuts import render
from django.shortcuts import render, get_object_or_404

from .models import CharacterList

def index(request):
    character_lists = CharacterList.objects.all()
    context = {
        "character_lists": character_lists,
    }
    return render(request, "sorterinput/index.html", context)

def viewlist(request, list_id):
    charlist = get_object_or_404(CharacterList, pk=list_id)
    context = {
        "charlist": charlist,
    }
    return render(request, "sorterinput/view.html", context)

def editlist(request, list_id):
    charlist = get_object_or_404(CharacterList, pk=list_id)
    context = {
        "charlist": charlist,
    }
    return render(request, "sorterinput/edit.html", context)
