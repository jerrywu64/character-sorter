from charactersorter.base_settings import *

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'uw-6#+^z)4s6sxzpqtz7+@rgj1)t2*q7^u0u=c@cjjt6x^8a%b'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

INTERNAL_IPS = ["127.0.0.1"]

# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'charactersorter',
        'USER': 'charsorter',
        'PASSWORD': 'D8DSNSsyBW4DwqsxGfQYMquj',
        'HOST': 'localhost',
        'PORT': '',
    }
}

IMAGE_SEARCH_CX = ""
