"""JSON API. ROADMAP.md carries the endpoint table and the design notes.

Lives in its own module and urlconf so that adding it changes no existing
view; the only edit outside /api/ is the include in charactersorter/urls.py.
"""
import json
from functools import wraps

from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.forms.models import model_to_dict
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

import controller.models
from .forms import MaybeAppendShowImages
from .models import Character, CharacterList
from .views import get_char_image

# The only values process_record can read: it maps them to win/tie/loss.
COMPARISON_VALUES = (-1, 0, 1)

CharacterForm = forms.modelform_factory(Character, fields=["name", "fandom"])

CharacterListForm = forms.modelform_factory(
    CharacterList, fields=MaybeAppendShowImages(["title", "controller_type"]))

def api_error(status, message, fields=None):
    payload = {"error": message}
    if fields is not None:
        payload["fields"] = fields
    return JsonResponse(payload, status=status)

class ApiError(Exception):
    """Raised anywhere inside an api_view to return an error response."""

    def __init__(self, status, message, fields=None):
        super().__init__(message)
        self.response = api_error(status, message, fields)

def api_view(*methods):
    """Wraps a JSON endpoint: method check, authentication, error shape.

    Deliberately not csrf_exempt. These views authenticate from the session,
    so Django's CSRF protection is what stops a cross-site write and a browser
    client must send X-CSRFToken.
    """
    def decorate(view):
        checked = require_http_methods(list(methods))(view)

        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return api_error(401, "Authentication required.")
            try:
                return checked(request, *args, **kwargs)
            except ApiError as err:
                return err.response
            except (Http404, ObjectDoesNotExist):
                return api_error(404, "No such object.")
        return wrapped
    return decorate

def owned_list(request, list_id):
    """The API's only authorization gate.

    Every object an endpoint touches is reached through the list this returns,
    so an id belonging to someone else raises DoesNotExist rather than being
    trusted. Unlike the HTML views, superusers get no bypass here.
    """
    return get_object_or_404(CharacterList, pk=list_id, owner=request.user)

def controller_for(charlist):
    return controller.models.CONTROLLER_TYPES[
        charlist.get_controller_class_name()]()

def json_body(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "Request body is not valid JSON.")
    if not isinstance(data, dict):
        raise ApiError(400, "Request body must be a JSON object.")
    return data

def int_field(data, name):
    try:
        return int(data[name])
    except KeyError:
        raise ApiError(400, "Missing field: {}.".format(name))
    except (TypeError, ValueError):
        raise ApiError(400, "Field {} must be an integer.".format(name))

def comparison_value(data):
    value = int_field(data, "value")
    if value not in COMPARISON_VALUES:
        raise ApiError(400, "Field value must be one of -1, 0 or 1.")
    return value

def client_timestamp(value):
    """SortRecord.timestamp is auto_now_add, so a client-supplied one has to
    be written over the record after save().

    A future one is refused because the Glicko maths measures elapsed days
    from it; a negative interval takes the square root of a negative and
    breaks every page that ranks the list until wall-clock time catches up.
    """
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        raise ApiError(400, "Field timestamp must be an ISO 8601 datetime.")
    if timezone.is_naive(parsed):
        raise ApiError(400, "Field timestamp must carry a UTC offset.")
    if parsed > timezone.now():
        raise ApiError(400, "Field timestamp must not be in the future.")
    return parsed

def bind_form(form_cls, data, instance=None, partial=False):
    """Validates data and returns the unsaved instance.

    Keys the form does not declare are dropped rather than rejected, so an
    "owner" or "characterlist" in the body has nothing to bind to.
    """
    fields = list(form_cls.base_fields)
    values = model_to_dict(instance, fields=fields) if partial else {}
    values.update({k: v for k, v in data.items() if k in fields})
    form = form_cls(values, instance=instance)
    if not form.is_valid():
        raise ApiError(
            400, "Invalid fields.",
            {name: list(errs) for name, errs in form.errors.items()})
    return form.save(commit=False)

def list_json(charlist):
    return {
        "id": charlist.id,
        "title": charlist.title,
        "controller_type": charlist.controller_type,
        "show_images": charlist.show_images,
    }

def char_json(char, show_images=False):
    data = {"id": char.id, "name": char.name, "fandom": char.fandom}
    if show_images:
        data["image"] = get_char_image(char)
    return data

def comparison_json(record):
    return {
        "id": record.id,
        "char1": record.char1_id,
        "char2": record.char2_id,
        "value": record.value,
        "timestamp": record.timestamp,
    }

def ranking_json(charlist):
    controller_obj = controller_for(charlist)
    annotations = controller_obj.get_annotations(charlist)
    by_id = {char.id: char for char in charlist.character_set.all()}
    ranked = []
    for rank, char_id in enumerate(controller_obj.get_sorted_chars(charlist)):
        entry = char_json(by_id[char_id])
        entry["rank"] = rank + 1
        entry["annotation"] = annotations.get(char_id)
        ranked.append(entry)
    data = list_json(charlist)
    data["progress"] = controller_obj.get_progress_info(charlist)
    data["characters"] = ranked
    return data

@api_view("GET", "POST")
def lists(request):
    if request.method == "POST":
        charlist = bind_form(CharacterListForm, json_body(request))
        charlist.owner = request.user
        charlist.save()
        return JsonResponse(list_json(charlist), status=201)
    owned = CharacterList.objects.filter(owner=request.user).order_by("id")
    return JsonResponse({"lists": [list_json(cl) for cl in owned]})

@api_view("GET", "PATCH", "DELETE")
def list_detail(request, list_id):
    charlist = owned_list(request, list_id)
    if request.method == "DELETE":
        charlist.delete()
        return HttpResponse(status=204)
    if request.method == "PATCH":
        charlist = bind_form(
            CharacterListForm, json_body(request), charlist, partial=True)
        charlist.save()
        return JsonResponse(list_json(charlist))
    return JsonResponse(ranking_json(charlist))

@api_view("GET", "POST")
def characters(request, list_id):
    charlist = owned_list(request, list_id)
    if request.method == "POST":
        char = bind_form(CharacterForm, json_body(request))
        char.characterlist = charlist
        char.save()
        return JsonResponse(char_json(char), status=201)
    return JsonResponse({"characters": [
        char_json(char)
        for char in charlist.character_set.all().order_by("id")]})

@api_view("PATCH", "DELETE")
def character_detail(request, list_id, char_id):
    charlist = owned_list(request, list_id)
    char = charlist.character_set.get(id=char_id)
    if request.method == "DELETE":
        char.delete()
        return HttpResponse(status=204)
    char = bind_form(CharacterForm, json_body(request), char, partial=True)
    char.save()
    return JsonResponse(char_json(char))

@api_view("GET")
def next_comparison(request, list_id):
    charlist = owned_list(request, list_id)
    controller_obj = controller_for(charlist)
    pair = controller_obj.get_next_comparison(charlist)
    data = {
        "done": pair is None,
        "char1": None,
        "char2": None,
        "progress": controller_obj.get_progress_info(charlist),
    }
    if pair is not None:
        by_id = {char.id: char
                 for char in charlist.character_set.filter(id__in=pair)}
        data["char1"] = char_json(by_id[pair[0]], charlist.show_images)
        data["char2"] = char_json(by_id[pair[1]], charlist.show_images)
    return JsonResponse(data)

@api_view("POST")
def comparisons(request, list_id):
    charlist = owned_list(request, list_id)
    data = json_body(request)
    # Through the list, not globally: register_comparison guards this with an
    # assert, and python -O strips asserts.
    char1 = charlist.character_set.get(id=int_field(data, "char1"))
    char2 = charlist.character_set.get(id=int_field(data, "char2"))
    if char1.id == char2.id:
        raise ApiError(400, "A character cannot be compared with itself.")
    value = comparison_value(data)
    stamp = (None if data.get("timestamp") is None
             else client_timestamp(data["timestamp"]))
    # Everything the body controls is validated above, so a rejected request
    # leaves no half-formed record for a retrying client to duplicate.
    with transaction.atomic():
        record = controller_for(charlist).register_comparison(
            charlist, char1.id, char2.id, value)
        if stamp is not None:
            record.timestamp = stamp
            record.save()
    return JsonResponse(comparison_json(record), status=201)

@api_view("DELETE")
def comparison_detail(request, list_id, rec_id):
    charlist = owned_list(request, list_id)
    charlist.sortrecord_set.get(id=rec_id).delete()
    return HttpResponse(status=204)

@api_view("GET")
def character_history(request, list_id, char_id):
    charlist = owned_list(request, list_id)
    char = charlist.character_set.get(id=char_id)
    controller_obj = controller_for(charlist)
    history = controller_obj.get_rating_history(charlist, char.id)
    if history is None:
        raise ApiError(404, "This list's controller has no ratings.")
    data = char_json(char, charlist.show_images)
    # The raw pair, as /graph reports it. The ranking's annotation is neither:
    # it is rating - 2 * rd, so a caller wanting that must subtract.
    data["rating"] = history["rating"]
    data["rd"] = history["rd"]
    data["history"] = [{
        "timestamp": point["timestamp"],
        "rating": point["rating"],
        "rd": point["rd"],
        "opponent": char_json(point["opponent"]),
        "value": point["value"],
    } for point in history["history"]]
    return JsonResponse(data)

@api_view("GET")
def graph(request, list_id):
    charlist = owned_list(request, list_id)
    info = controller_for(charlist).get_graph_info(charlist)
    if info is None:
        raise ApiError(404, "This list's controller has no graph.")
    return JsonResponse({
        "graph_type": info["graph_type"],
        "characters": json.loads(info["characters"]),
        "ratings": json.loads(info["ratings_raw"]),
        "double_rds": json.loads(info["double_rds"]),
    })
