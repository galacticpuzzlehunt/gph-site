from .base import *

DEBUG = True

IS_TEST = True

DOMAIN = 'http://localhost:8000/'

ALLOWED_HOSTS = ['*']

EMAIL_SUBJECT_PREFIX = ''

STATIC_ROOT = 'static'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'django-file': {
            'format': '%(asctime)s (PID %(process)d) [%(levelname)s] %(module)s\n%(message)s'
        },
        'puzzles-file': {
            'format': '%(asctime)s (PID %(process)d) [%(levelname)s] %(name)s %(message)s'
        },
        'django-console': {
            'format': '\033[34;1m%(asctime)s \033[35;1m[%(levelname)s] \033[34;1m%(module)s\033[0m\n%(message)s'
        },
        'puzzles-console': {
            'format': '\033[36;1m%(asctime)s \033[35;1m[%(levelname)s] \033[36;1m%(name)s\033[0m %(message)s'
        },
    },
    'handlers': {
        'django': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOGS_DIR, 'django.log'),
            'formatter': 'django-file',
        },
        'general': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOGS_DIR, 'general.log'),
            'formatter': 'puzzles-file',
        },
        'puzzle': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOGS_DIR, 'puzzle.log'),
            'formatter': 'puzzles-file',
        },
        'request': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOGS_DIR, 'request.log'),
            'formatter': 'puzzles-file',
        },
        'django-console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'django-console',
        },
        'puzzles-console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'puzzles-console',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['django', 'django-console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.db.backends': {
            'level': 'INFO',
            'handlers': ['django', 'django-console'],
            'propagate': False,
        },
        'django.server': {
            'level': 'INFO',
            'handlers': ['django'],
            'propagate': False,
        },
        'django.utils.autoreload': {
            'level': 'INFO',
            'propagate': True,
        },
        'puzzles': {
            'handlers': ['general', 'puzzles-console'],
            'level': 'INFO',
            'propagate': True,
        },
        'puzzles.puzzle': {
            'handlers': ['puzzle', 'puzzles-console'],
            'level': 'INFO',
            'propagate': False,
        },
        'puzzles.request': {
            'handlers': ['request'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
