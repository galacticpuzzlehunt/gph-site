from .base import *

DEBUG = False

IS_TEST = False

# Used for constructing URLs; include the protocol and trailing
# slash (e.g. 'https://galacticpuzzlehunt.com/')
DOMAIN = 'FIXME'

# List of places you're serving from, e.g.
# ['galacticpuzzlehunt.com', 'gph.example.com']; or just ['*']
ALLOWED_HOSTS = ['*']

RECAPTCHA_SCORE_THRESHOLD = 0.5

# Google Analytics
GA_CODE = '''
<script>
  /* FIXME */
</script>
'''
