# Roughly speaking, this module is most important for implementing "global
# variables" that are available in every template with the Django feature of
# "context processors". But it also does some stuff with caching computed
# properties of teams (the caching is only within a single request (?)). See
# https://docs.djangoproject.com/en/3.1/ref/templates/api/#using-requestcontext
import datetime
import inspect
import types

from django.utils import timezone

from puzzles.hunt_config import (
    HUNT_TITLE,
    HUNT_ORGANIZERS,
    STORY_PAGE_VISIBLE,
    ERRATA_PAGE_VISIBLE,
    WRAPUP_PAGE_VISIBLE,
    HUNT_START_TIME,
    HUNT_END_TIME,
    HUNT_CLOSE_TIME,
    HINTS_ENABLED,
    HINTS_PER_DAY,
    DAYS_BEFORE_HINTS,
    DEEP_MAX,
    CONTACT_EMAIL,
    MAX_MEMBERS_PER_TEAM,
    MAX_GUESSES_PER_PUZZLE,
)

from puzzles.shortcuts import get_shortcuts

from puzzles import models


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
# The properties here are accessible both from views and from templates. If
# you're adding something with complicated logic, prefer to put most of it in
# a model method and just leave a stub call here.

# In theory, `BaseContext` properties are things that make sense if all the info
# you have is an optional team (e.g. you don't know about a specific puzzle, or
# a user who might not be specified by the team). (But TODO(gph): this setup
# may currently be overengineered.)
class BaseContext:
    def hunt_title(self):
        return HUNT_TITLE

    def hunt_organizers(self):
        return HUNT_ORGANIZERS

    def now(self):
        return timezone.localtime()

    def start_time(self):
        return HUNT_START_TIME - self.team.start_offset if self.team else HUNT_START_TIME

    def end_time(self):
        return HUNT_END_TIME

    def close_time(self):
        return HUNT_CLOSE_TIME

    def is_story_page_visible(self):
        return STORY_PAGE_VISIBLE

    def is_errata_page_visible(self):
        return ERRATA_PAGE_VISIBLE

    def is_wrapup_page_visible(self):
        return WRAPUP_PAGE_VISIBLE

    def hints_per_day(self):
        if HINTS_ENABLED:
            return HINTS_PER_DAY
        else:
            return 0

    def hint_time(self):
        if HINTS_ENABLED:
            return self.start_time + datetime.timedelta(days=DAYS_BEFORE_HINTS)
        else:
            return None

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

    def num_canned_hints_released(self):
        if self.hunt_is_prereleased:
            return 2

        elapsed = self.now - self.start_time
        if elapsed >= datetime.timedelta(days=2):
            return 2
        elif elapsed >= datetime.timedelta(days=1):
            return 1
        return 0

    def deep(self):
        return models.Team.compute_deep(self)

    def display_deep(self):
        return '\u221e' if self.deep == DEEP_MAX else int(self.deep)

    def contact_email(self):
        return CONTACT_EMAIL

    def max_members_per_team(self):
        return MAX_MEMBERS_PER_TEAM

    def max_guesses_per_puzzle(self):
        return MAX_GUESSES_PER_PUZZLE

# In theory, `Context` properties are things that don't make sense if all the
# info you have is a team. They might make sense for a specific Django request
# that specifies a puzzle.
@context_cache
class Context:
    def __init__(self, request):
        self.request = request

    def is_superuser(self):
        return self.request.user.is_superuser

    def team(self):
        return getattr(self.request.user, 'team', None)

    def shortcuts(self):
        return tuple(get_shortcuts(self))

    def num_hints_remaining(self):
        return self.team.num_hints_remaining if self.team else 0

    def num_free_answers_remaining(self):
        return self.team.num_free_answers_remaining if self.team else 0

    def submissions(self):
        return self.team.submissions if self.team else []

    def unlocks(self):
        return models.Team.compute_unlocks(self)

    def all_puzzles(self):
        return tuple(models.Puzzle.objects.order_by('deep', 'order'))

    def unclaimed_hints(self):
        return models.Hint.objects.filter(status=models.Hint.NO_RESPONSE, claimer=None).count()

    def puzzle(self):
        return None  # set by validate_puzzle

    def puzzle_answer(self):
        return self.team and self.puzzle and self.team.puzzle_answer(self.puzzle)

    def guesses_remaining(self):
        return self.team and self.puzzle and self.team.guesses_remaining(self.puzzle)

    def puzzle_submissions(self):
        return self.team and self.puzzle and self.team.puzzle_submissions(self.puzzle)
