"""charactersorter URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls import url
from django.contrib.auth import views as auth_views
from core import views as core_views
import sorterinput

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sorterinput/', include('sorterinput.urls')),
    url("login/", auth_views.login, {'template_name': 'core/login.html'}, name="login"),
    url("logout/", auth_views.logout, {'next_page': '/'}, name='logout'),
    url("signup/", core_views.signup, name='signup'),
    path("", sorterinput.views.IndexView.as_view())
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
