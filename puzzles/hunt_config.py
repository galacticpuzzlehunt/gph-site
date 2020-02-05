import datetime
from django.conf import settings
from django.utils import timezone
from puzzles.messaging import send_mail_wrapper

# Change this to True to reveal the story page to everyone.
STORY_PAGE_VISIBLE = False
# Change this to True if any errata are added to errata.html.
ERRATA_PAGE_VISIBLE = False
# Change this to True when the wrapup exists.
WRAPUP_PAGE_VISIBLE = False
# Change this to True to start showing post-solve surveys to teams.
SURVEYS_AVAILABLE = True

HUNT_START_TIME = timezone.make_aware(datetime.datetime(
    year=2020,
    month=3,
    day=13,
    hour=18,
    minute=28,
))

HUNT_END_TIME = timezone.make_aware(datetime.datetime(
    year=2020,
    month=3,
    day=23,
    hour=6,
    minute=28,
))

HUNT_CLOSE_TIME = timezone.make_aware(datetime.datetime(
    year=2020,
    month=4,
    day=20,
    hour=18,
    minute=28,
))

MAX_GUESSES_PER_PUZZLE = 20
MAX_MEMBERS_PER_TEAM = 10
DAYS_BEFORE_HINTS = 3
DAYS_BEFORE_FREE_ANSWERS = 6

# DEEP value used to indicate that you can see everything, e.g. the hunt is over.
DEEP_MAX = float('inf')
# Slug for the intro meta.
INTRO_META_SLUG = 'intro-meta'
# Slug for the metameta.
META_META_SLUG = 'meta-meta'
# Free answers are given out each day after helpers.DAYS_BEFORE_FREE_ANSWERS.
FREE_ANSWERS_PER_DAY = [1, 2, 2]
