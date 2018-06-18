from django.urls import path

from . import views

app_name = "sorterinput"
urlpatterns = [
    path('', views.index, name='index'),
    path('<int:list_id>/', views.viewlist, name='viewlist'),
    path('<int:list_id>/edit/', views.editlist, name='editlist'),
]
