import inspect
import types

from django.utils.translation import gettext as _

from puzzles import models, hunt_config

def get_shortcuts(context):
    for action, callback in Shortcuts.__dict__.items():
        if action.startswith('__'):
            continue
        params = dict.fromkeys(inspect.getfullargspec(callback).args)
        if 'puzzle' in params and context.puzzle:
            params['puzzle'] = context.puzzle
        if 'team' in params and context.team:
            params['team'] = context.team
        if 'user' in params and not context.team:
            params['user'] = context.request_user
        if 'now' in params:
            params['now'] = context.now
        if not all(params.values()):
            continue
        if hasattr(callback, 'is_heading'):
            yield {'name': callback(**params)}
        else:
            yield {
                'action': action,
                'name': callback.__doc__,
                'danger': hasattr(callback, 'is_danger'),
            }

def dispatch_shortcut(request):
    action = request.POST.get('action')
    assert action, _('Missing action')
    callback = getattr(Shortcuts, action, None)
    assert isinstance(callback, types.FunctionType), _('Invalid action %r') % action
    params = dict.fromkeys(inspect.getfullargspec(callback).args)
    if 'puzzle' in params:
        slug = request.POST.get('puzzle')
        assert slug, _('Missing puzzle')
        puzzle = models.Puzzle.objects.filter(slug=slug).first()
        assert puzzle, _('Invalid puzzle %r') % slug
        params['puzzle'] = puzzle
    if 'team' in params:
        assert request.context.team, _('Not on a team')
        params['team'] = request.context.team
    if 'user' in params:
        assert not request.context.team, _('Already on a team')
        params['user'] = request.user
    if 'now' in params:
        params['now'] = request.context.now
    callback(**params)

def heading(f):
    f.is_heading = True
    return f

def danger(f):
    f.is_danger = True
    return f

# This namespace holds convenience functions for modifying an admin team's
# state for testing purposes. Feel free to add anything you think would be
# convenient to have in development. These will be rendered in order
# (hopefully...) in a menu, with the @headings as headings.
# For i18n, the heading in __doc__ must be dynamic to get the
# translation, so it's set outside of the function to be initialized at runtime

class Shortcuts:
    def create_team(user):
        models.Team(
            user=user,
            team_name=user.username,
            is_hidden=True,
        ).save()
    create_team.__doc__ = _('Create admin team')

    def prerelease_testsolver(team):
        team.is_prerelease_testsolver ^= True
        team.save()
    prerelease_testsolver.__doc__ = _('Toggle testsolver')

    @heading
    def LINE_BREAK(team):
        return ''

    def set_offset_to_start_now(team, now):
        team.start_offset = hunt_config.HUNT_START_TIME - now
        team.save()
    set_offset_to_start_now.__doc__ = _('Offset to start now')

    if hunt_config.HINTS_ENABLED:
        @heading
        def HINTS(team):
            return _('Hints (my team)')

        def hint_1(team):
            '+1'
            team.total_hints_awarded += 1
            team.save()

        def hint_5(team):
            '+5'
            team.total_hints_awarded += 5
            team.save()

        def hint_0(team):
            '=0'
            team.total_hints_awarded -= team.num_hints_remaining
            team.save()

        def reset_hints(team):
            team.total_hints_awarded = 0
            team.save()
        reset_hints.__doc__ = _('Reset')

    if hunt_config.FREE_ANSWERS_ENABLED:
        @heading
        def FREE_ANSWERS(team):
            return _('Free answers (my team)')

        def free_answer_1(team):
            '+1'
            team.total_free_answers_awarded += 1
            team.save()

        def free_answer_5(team):
            '+5'
            team.total_free_answers_awarded += 5
            team.save()

        def free_answer_0(team):
            '=0'
            team.total_free_answers_awarded -= team.num_free_answers_remaining
            team.save()

        def reset_free_answers(team):
            team.total_free_answers_awarded = 0
            team.save()
        reset_free_answers.__doc__ = _('Reset')

    @heading
    def SOLVE(puzzle, team):
        return _('Submit answer (this puzzle)')

    def solve(puzzle, team):
        team.answersubmission_set.filter(puzzle=puzzle, is_correct=True).delete()
        team.answersubmission_set.create(
            puzzle=puzzle,
            submitted_answer=puzzle.normalized_answer,
            is_correct=True,
            used_free_answer=False,
        )
    solve.__doc__ = _('Solve')

    def free_answer(puzzle, team):
        team.answersubmission_set.filter(puzzle=puzzle, is_correct=True).delete()
        team.answersubmission_set.create(
            puzzle=puzzle,
            submitted_answer=puzzle.normalized_answer,
            is_correct=True,
            used_free_answer=True,
        )
    free_answer.__doc__ = _('Free')

    def unsolve(puzzle, team):
        team.answersubmission_set.filter(puzzle=puzzle, is_correct=True).delete()
    unsolve.__doc__ = _('Unsolve')

    @heading
    def PUZZLE_HINTS(puzzle, team):
        return _('Request hint (this puzzle)')

    def unanswered_hint(puzzle, team):
        return team.hint_set.create(
            puzzle=puzzle,
            hint_question='Halp',
        )
    unanswered_hint.__doc__ = _('Unanswered')

    def answered_hint(puzzle, team, now):
        hint = Shortcuts.unanswered_hint(puzzle, team)
        hint.answered_datetime = now
        hint.status = models.Hint.ANSWERED
        hint.response = _('Ok')
        hint.save(update_fields=('answered_datetime', 'status', 'response'))
    answered_hint.__doc__ = _('Answered')

    @heading
    def PUZZLE_GUESSES(puzzle, team):
        return _('Guesses (my team, this puzzle)')

    def guess_1(puzzle, team):
        '+1'
        grant, _ = team.extraguessgrant_set.get_or_create(puzzle=puzzle,
            defaults={'extra_guesses': 0})
        grant.extra_guesses += 1
        grant.save()

    def guess_5(puzzle, team):
        '+5'
        grant, _ = team.extraguessgrant_set.get_or_create(puzzle=puzzle,
            defaults={'extra_guesses': 0})
        grant.extra_guesses += 5
        grant.save()

    def guess_0(puzzle, team):
        '=0'
        grant, _ = team.extraguessgrant_set.get_or_create(puzzle=puzzle,
            defaults={'extra_guesses': 0})
        grant.extra_guesses -= team.guesses_remaining(puzzle)
        grant.save()

    def reset_guesses(puzzle, team):
        team.extraguessgrant_set.filter(puzzle=puzzle).delete()
    reset_guesses.__doc__ = _('Reset')

    @heading
    def DELETE(puzzle, team):
        return _('Delete all (my team, this puzzle)')

    @danger
    def delete_hints(puzzle, team):
        team.hint_set.filter(puzzle=puzzle).delete()
    delete_hints.__doc__ = _('Hints')

    @danger
    def delete_guesses(puzzle, team):
        team.answersubmission_set.filter(puzzle=puzzle).delete()
    delete_guesses.__doc__ = _('Guesses')
