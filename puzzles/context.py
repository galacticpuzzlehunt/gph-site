# Roughly speaking, this module is most important for implementing "global
# variables" that are available in every template with the Django feature of
# "context processors". But it also does some stuff with caching computed
# properties of teams (the caching is only within a single request (?)). See
# https://docs.djangoproject.com/en/3.1/ref/templates/api/#using-requestcontext
import datetime
import inspect
import types

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from puzzles import hunt_config
from puzzles.hunt_config import HUNT_START_TIME, HUNT_END_TIME, HUNT_CLOSE_TIME
from puzzles import models
from puzzles.shortcuts import get_shortcuts


def context_middleware(get_response):
    def middleware(request):
        request.context = Context(request)
        return get_response(request)
    return middleware

# A context processor takes a request and returns a dictionary of (key: value)s
# to merge into the request's context.
def context_processor(request):
    def thunk(name):
        return lambda: getattr(request.context, name)
    return {name: thunk(name) for name in request.context._cached_names}

# Construct a get/set property from a name and a function to compute a value.
# Doing this with name="foo" causes accesses to self.foo to call fn and cache
# the result.
def wrap_cacheable(name, fn):
    def fget(self):
        if not hasattr(self, '_cache'):
            self._cache = {}
        if name not in self._cache:
            self._cache[name] = fn(self)
        return self._cache[name]
    def fset(self, value):
        if not hasattr(self, '_cache'):
            self._cache = {}
        self._cache[name] = value
    return property(fget, fset)

# Decorator for a class, like the `Context` class below but also the `Team`
# model, that replaces all non-special methods that take no arguments other
# than `self` with a get/set property as constructed above, and also gather
# their names into the property `_cached_names`.
def context_cache(cls):
    cached_names = []
    for c in (BaseContext, cls):
        for name, fn in c.__dict__.items():
            if (
                not name.startswith('__') and
                isinstance(fn, types.FunctionType) and
                inspect.getfullargspec(fn).args == ['self']
            ):
                setattr(cls, name, wrap_cacheable(name, fn))
                cached_names.append(name)
    cls._cached_names = tuple(cached_names)
    return cls


# This object is a request-scoped cache containing data calculated for the
# current request. As a motivating example: showing current DEEP in the top
# bar and rendering the puzzles page both need the list of puzzles the current
# team has solved. This object ensures it only needs to be computed once,
# without explicitly having to pass it around from one place to the other.

# There are currently two types of contexts: request Contexts (below) and Team
# models (in models.py). Simple properties that are generally useful to either
# can go in BaseContext. The fact that Teams are contexts enables the above
# caching benefits when calculating things like a team's solves, unlocked
# puzzles, or remaining hints -- whether you're looking at your own logged-in
# team or another team's details page.
class BaseContext:
    def now(self):
        return timezone.localtime()

    def start_time(self):
        return HUNT_START_TIME - self.team.start_offset if self.team else HUNT_START_TIME

    def time_since_start(self):
        return self.now - self.start_time

    def end_time(self):
        return HUNT_END_TIME

    def close_time(self):
        return HUNT_CLOSE_TIME

    # XXX do NOT name this the same as a field on the actual Team model or
    # you'll silently be unable to update that field because you'll be writing
    # to this instead of the actual model field!
    def hunt_is_prereleased(self):
        return self.team and self.team.is_prerelease_testsolver

    def hunt_has_started(self):
        return self.hunt_is_prereleased or self.now >= self.start_time

    def hunt_has_almost_started(self):
        return self.start_time - self.now < datetime.timedelta(hours=1)

    def hunt_is_over(self):
        return self.now >= self.end_time

    def hunt_is_closed(self):
        return self.now >= self.close_time

# Also include the constants from hunt_config.
for (key, value) in hunt_config.__dict__.items():
    if key.isupper() and key not in ('HUNT_START_TIME', 'HUNT_END_TIME', 'HUNT_CLOSE_TIME'):
        (lambda v: setattr(BaseContext, key.lower(), lambda self: v))(value)

# Also include select constants from settings.
for key in ('RECAPTCHA_SITEKEY', 'GA_CODE', 'DOMAIN'):
    (lambda v: setattr(BaseContext, key.lower(), lambda self: v))(getattr(settings, key))


# The properties of a request Context are accessible both from views and from
# templates. If you're adding something with complicated logic, prefer to put
# most of it in a model method and just leave a stub call here.
@context_cache
class Context:
    def __init__(self, request):
        self.request = request

    def request_user(self):
        return self.request.user

    def is_superuser(self):
        return self.request_user.is_superuser

    def team(self):
        return getattr(self.request_user, 'team', None)

    def shortcuts(self):
        return tuple(get_shortcuts(self))

    def num_hints_remaining(self):
        return self.team.num_hints_remaining if self.team else 0

    def num_free_answers_remaining(self):
        return self.team.num_free_answers_remaining if self.team else 0

    def unlocks(self):
        return models.Team.compute_unlocks(self)

    def all_puzzles(self):
        return tuple(models.Puzzle.objects.select_related('round').order_by('round__order', 'order'))

    def unclaimed_hints(self):
        return models.Hint.objects.filter(status=models.Hint.NO_RESPONSE, claimer='').count()

    def visible_errata(self):
        return models.Erratum.get_visible_errata(self)

    def errata_page_visible(self):
        return self.is_superuser or any(erratum.updates_text for erratum in self.visible_errata)

    def puzzle(self):
        return None  # set by validate_puzzle

    def puzzle_answer(self):
        return self.team and self.puzzle and self.team.puzzle_answer(self.puzzle)

    def guesses_remaining(self):
        return self.team and self.puzzle and self.team.guesses_remaining(self.puzzle)

    def puzzle_submissions(self):
        return self.team and self.puzzle and self.team.puzzle_submissions(self.puzzle)

    def round(self):
        return self.puzzle.round if self.puzzle else None

    # The purpose of this logic is to keep archive links current. For example,
    # https://2019.galacticpuzzlehunt.com/archive is a page that exists but only
    # links to the 2017, 2018, and 2019 GPHs. We're not going to keep updating
    # that page for all future GPHs. Instead, we'd like to link to
    # https://galacticpuzzlehunt.com/archive, which we've set up to redirect to
    # the most recent GPH, so it'll show all GPHs run so far. If you don't have
    # an archive, you don't have to bother with this.
    def archive_link(self):
        return reverse('archive') if settings.DEBUG else 'https://FIXME/archive'
