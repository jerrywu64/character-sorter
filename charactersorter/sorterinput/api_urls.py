from django.urls import path

from . import api

app_name = "api"
urlpatterns = [
    path("lists", api.lists, name="lists"),
    path("lists/<int:list_id>", api.list_detail, name="list_detail"),
    path("lists/<int:list_id>/characters", api.characters, name="characters"),
    path("lists/<int:list_id>/characters/<int:char_id>",
         api.character_detail, name="character_detail"),
    path("lists/<int:list_id>/characters/<int:char_id>/history",
         api.character_history, name="character_history"),
    path("lists/<int:list_id>/next", api.next_comparison, name="next"),
    path("lists/<int:list_id>/comparisons", api.comparisons,
         name="comparisons"),
    path("lists/<int:list_id>/comparisons/<int:rec_id>",
         api.comparison_detail, name="comparison_detail"),
    path("lists/<int:list_id>/graph", api.graph, name="graph"),
]
