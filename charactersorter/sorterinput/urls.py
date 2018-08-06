from django.urls import path

from . import views

app_name = "sorterinput"
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('editlists/', views.editcharlists, name='editcharlists'),
    path('<int:list_id>/', views.viewlist, name='viewlist'),
    path('<int:list_id>/graph/', views.graphlist, name='graphlist'),
    path('<int:list_id>/edit/', views.editlist, name='editlist'),
    path('<int:list_id>/sort/', views.sortlist, name='sortlist'),
    path('<int:list_id>/undo/', views.undo, name='undo'),

]
