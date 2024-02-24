from .base import *

DEBUG = False

IS_TEST = False

# Used for constructing URLs; include the protocol and trailing
# slash (e.g. 'https://galacticpuzzlehunt.com/')
DOMAIN = 'http://104.247.79.63:8000/'

# List of places you're serving from, e.g.
# ['galacticpuzzlehunt.com', 'gph.example.com']; or just ['*']
ALLOWED_HOSTS = ['*']

HUNT_START_TIME = timezone.make_aware(datetime.datetime(
    year=2024,
    month=2,
    day=22,
    hour=20,
    minute=0,
))

RECAPTCHA_SCORE_THRESHOLD = 0.5

# Google Analytics
GA_CODE = '''
<script>
  /* FIXME */
</script>
'''
