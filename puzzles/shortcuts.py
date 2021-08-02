import inspect
import types

from puzzles import models


def get_shortcuts(context):
    heading = None
    for action, callback in Shortcuts.__dict__.items():
        if action.startswith('__'):
            continue
        if isinstance(callback, types.FunctionType):
            params = set(inspect.getfullargspec(callback).args)
            if 'puzzle' in params and not context.puzzle:
                continue
            if 'team' in params and not context.team:
                continue
            if 'user' in params and context.team:
                continue
            if heading is not None:
                yield {'name': heading}
                heading = None
            yield {'action': action, 'name': callback.__doc__}
        else:
            heading = callback

def dispatch_shortcut(request):
    action = request.POST.get('action')
    assert action, 'Missing action'
    callback = getattr(Shortcuts, action, None)
    assert isinstance(callback, types.FunctionType), 'Invalid action %r' % action
    params = dict.fromkeys(inspect.getfullargspec(callback).args)
    if 'puzzle' in params:
        slug = request.POST.get('puzzle')
        assert slug, 'Missing puzzle'
        puzzle = models.Puzzle.objects.filter(slug=slug).first()
        assert puzzle, 'Invalid puzzle %r' % slug
        params['puzzle'] = puzzle
    if 'team' in params:
        assert request.context.team, 'Not on a team'
        params['team'] = request.context.team
    if 'user' in params:
        assert not request.context.team, 'Already on a team'
        params['user'] = request.user
    if 'now' in params:
        params['now'] = request.context.now
    callback(**params)


# This namespace holds convenience functions for modifying an admin team's
# state for testing purposes. Feel free to add anything you think would be
# convenient to have in development. These will be rendered in order
# (hopefully...) in a menu, with the strings as headings.

class Shortcuts:
    def create_team(user):
        'Create team'
        models.Team(
            user=user,
            team_name=user.username,
            is_hidden=True,
        ).save()

    def prerelease_testsolver(team):
        'Toggle testsolver'
        team.is_prerelease_testsolver ^= True
        team.save()

    HINTS = 'Hints (my team)'

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
        'Reset'
        team.total_hints_awarded = 0
        team.save()

    FREE_ANSWERS = 'Free answers (my team)'

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
        'Reset'
        team.total_free_answers_awarded = 0
        team.save()

    PUZZLE = 'This puzzle'

    def show_answer(puzzle):
        'Show answer'
        raise Exception(puzzle.answer)

    def show_order(puzzle):
        'Show order'
        raise Exception(puzzle.order)

    SOLVE = 'Solve this puzzle'

    def solve(puzzle, team):
        'Solve'
        if not team.answersubmission_set.filter(puzzle=puzzle, is_correct=True).exists():
            team.answersubmission_set.create(
                puzzle=puzzle,
                submitted_answer=puzzle.normalized_answer,
                is_correct=True,
                used_free_answer=False,
            )

    def free_answer(puzzle, team):
        'Free'
        if not team.answersubmission_set.filter(puzzle=puzzle, is_correct=True).exists():
            team.answersubmission_set.create(
                puzzle=puzzle,
                submitted_answer=puzzle.normalized_answer,
                is_correct=True,
                used_free_answer=True,
            )

    def unsolve(puzzle, team):
        'Unsolve'
        team.answersubmission_set.filter(puzzle=puzzle, is_correct=True).delete()

    PUZZLE_HINTS = 'Request hint on this puzzle'

    def unanswered_hint(puzzle, team):
        'Unanswered'
        return team.hint_set.create(
            puzzle=puzzle,
            hint_question='Halp',
        )

    def answered_hint(puzzle, team, now):
        'Answered'
        hint = Shortcuts.unanswered_hint(puzzle, team)
        hint.answered_datetime = now
        hint.status = models.Hint.ANSWERED
        hint.response = 'Ok'
        hint.save(update_fields=('answered_datetime', 'status', 'response'))

    PUZZLE_GUESSES = 'Guesses (on this puzzle)'

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
        'Reset'
        team.extraguessgrant_set.filter(puzzle=puzzle).delete()

    DELETE = 'Delete all my (on this puzzle)'

    def delete_hints(puzzle, team):
        'Hints'
        team.hint_set.filter(puzzle=puzzle).delete()

    def delete_guesses(puzzle, team):
        'Guesses'
        team.answersubmission_set.filter(puzzle=puzzle).delete()
