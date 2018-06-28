from django.urls import path

from . import views

app_name = "sorterinput"
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<int:pk>/', views.ViewListView.as_view(), name='viewlist'),
    path('<int:list_id>/edit/', views.editlist, name='editlist'),
]
