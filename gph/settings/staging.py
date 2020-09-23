from .base import *

import os, sys
import dj_database_url

DEBUG = True

IS_TEST = False

# Used for constructing URLs; include the protocol and trailing
# slash (e.g. 'https://galacticpuzzlehunt.com/')
DOMAIN = 'FIXME'

# List of places you're serving from, e.g.
# ['galacticpuzzlehunt.com', 'gph.example.com']; or just ['*']
ALLOWED_HOSTS = ['FIXME']

EMAIL_SUBJECT_PREFIX = '[\u2708\u2708\u2708STAGING\u2708\u2708\u2708] '

# Google Analytics
GA_CODE = '''
<script>
  /* FIXME */
</script>
'''

DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True),
}


# https://docs.djangoproject.com/en/3.1/topics/logging/

# Loggers and handlers both have a log level; handlers ignore messages at lower
# levels. This is useful because a logger can have multiple handlers with
# different handlers.

# The levels are DEBUG < INFO < WARNING < ERROR < CRITICAL.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'django': {
            'format': '%(asctime)s [%(levelname)s] %(module)s\n%(message)s'
        },
        'puzzles': {
            'format': '%(asctime)s [%(levelname)s] %(message)s'
        },
    },
    # FIXME you may want to change the filenames to something like
    # /srv/logs/django.log or similar
    'handlers': {
        'django': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'django',
        },
        'puzzle': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'puzzles',
        },
        'request': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'puzzles',
        },
        'messaging': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'puzzles',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['django'],
            'level': 'INFO',
            'propagate': True,
        },
        'puzzles.puzzle': {
            'handlers': ['puzzle'],
            'level': 'INFO',
            'propagate': False,
        },
        'puzzles.request': {
            'handlers': ['request'],
            'level': 'INFO',
            'propagate': False,
        },
        'puzzles.messaging': {
            'handlers': ['messaging'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
