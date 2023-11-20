from .base import *

DEBUG = True

IS_TEST = False

# Used for constructing URLs; include the protocol and trailing
# slash (e.g. 'https://galacticpuzzlehunt.com/')
DOMAIN = 'FIXME'

# List of places you're serving from, e.g.
# ['galacticpuzzlehunt.com', 'gph.example.com']; or just ['*']
ALLOWED_HOSTS = ['FIXME']

EMAIL_SUBJECT_PREFIX = '[\u2708\u2708\u2708STAGING\u2708\u2708\u2708] '

HUNT_START_TIME = timezone.make_aware(datetime.datetime(
    year=9000,
    month=1,
    day=1,
    hour=0,
    minute=0,
))
