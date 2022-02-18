import csv
import datetime
import itertools
import json
import logging
import os
import requests
from collections import defaultdict, OrderedDict, Counter
from functools import wraps
from urllib.parse import unquote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.db.models import F, Q, Avg, Count
from django.forms import formset_factory, modelformset_factory
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.html import escape
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST
from django.views.static import serve

from puzzles.models import (
    Round,
    Puzzle,
    Team,
    TeamMember,
    PuzzleUnlock,
    AnswerSubmission,
    PuzzleMessage,
    Survey,
    Hint,
)

from puzzles.forms import (
    RegisterForm,
    TeamMemberForm,
    TeamMemberFormset,
    TeamMemberModelFormset,
    SubmitAnswerForm,
    RequestHintForm,
    AnswerHintForm,
    SurveyForm,
    PasswordResetForm,
)

from puzzles.hunt_config import (
    STORY_PAGE_VISIBLE,
    WRAPUP_PAGE_VISIBLE,
    INITIAL_STATS_AVAILABLE,
    SURVEYS_AVAILABLE,
    HUNT_START_TIME,
    HUNT_END_TIME,
    HUNT_CLOSE_TIME,
    MAX_MEMBERS_PER_TEAM,
    ONE_HINT_AT_A_TIME,
    INTRO_ROUND_SLUG,
    META_META_SLUG,
)

from puzzles.messaging import send_mail_wrapper, dispatch_victory_alert
from puzzles.shortcuts import dispatch_shortcut


def validate_puzzle(require_team=False):
    '''
    Indicates an endpoint that takes a single URL parameter, the slug for the
    puzzle. If the slug is invalid, report an error and redirect to /puzzles.
    If require_team is true, then the user must also be logged in.
    '''
    def decorator(f):
        @wraps(f)
        def inner(request, slug):
            puzzle = Puzzle.objects.filter(slug=slug).first()
            if not puzzle or puzzle not in request.context.unlocks:
                messages.error(request, _('Invalid puzzle name.'))
                return redirect('puzzles')
            if request.context.team:
                unlock = request.context.team.db_unlocks.get(puzzle.id)
                if unlock and not unlock.view_datetime:
                    unlock.view_datetime = request.context.now
                    unlock.save()
            elif require_team:
                messages.error(
                    request,
                    _('You must be signed in and have a registered team to '
                    'access this page.')
                )
                return redirect('puzzle', slug)
            request.context.puzzle = puzzle
            return f(request)
        return inner
    return decorator

def access_restrictor(check_request):
    '''
    Creates a decorator that indicates an endpoint that is sometimes hidden to
    all regular users. Superusers are always allowed access. Otherwise, the
    provided check_request function is called on the request first, and if it
    throws an exception or returns a non-None value, that is returned instead.
    '''

    def decorator(f):
        @wraps(f)
        def inner(request, *args, **kwargs):
            if not request.context.is_superuser:
                check_res = check_request(request)
                if check_res is not None:
                    return check_res
            return f(request, *args, **kwargs)
        return inner
    return decorator

@access_restrictor
def require_admin(request):
    raise Http404

# So it's absolutely clear, the two following decorators are
# asymmetric: the hunt can "end" before it "closes", and in the time
# between, both of these decorators will allow non-superusers.  See
# the "Timing" section of the README.
@access_restrictor
def require_after_hunt_end_or_admin(request):
    if not request.context.hunt_is_over:
        messages.error(request, _('Sorry, not available until the hunt ends.'))
        return redirect('index')

@access_restrictor
def require_before_hunt_closed_or_admin(request):
    if request.context.hunt_is_closed:
        messages.error(request, _('Sorry, the hunt is over.'))
        return redirect('index')


# These are basically static pages:

@require_GET
def index(request):
    return render(request, 'home.html')


@require_GET
def rules(request):
    return render(request, 'rules.html')


@require_GET
def faq(request):
    return render(request, 'faq.html')


@require_GET
def archive(request):
    return render(request, 'archive.html')


recaptcha_logger = logging.getLogger('puzzles.recaptcha')

@require_before_hunt_closed_or_admin
def register(request):
    team_members_formset = formset_factory(
        TeamMemberForm,
        formset=TeamMemberFormset,
        extra=0,
        min_num=1,
        max_num=MAX_MEMBERS_PER_TEAM,
        validate_max=True,
    )

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        formset = team_members_formset(request.POST)

        # The below only logs the response and doesn't do anything with it.
        # If you have spam problems, you can reject when the score is low.
        if 'g-recaptcha-response' in request.POST:
            url = 'https://www.google.com/recaptcha/api/siteverify'
            token = request.POST['g-recaptcha-response']
            try:
                response = requests.post(url, data={
                    'secret': settings.RECAPTCHA_SECRETKEY,
                    'response': token,
                }).json()
                recaptcha_logger.info(_('team [%s] token [%s]\n%s') % (
                    request.POST['team_id'], token, response))
            except Exception:
                pass

        if form.is_valid() and formset.is_valid():
            data = form.cleaned_data
            formset_data = formset.cleaned_data

            user = User.objects.create_user(
                data.get('team_id'),
                password=data.get('password'),
                first_name=data.get('team_name'),
            )
            team = Team.objects.create(
                user=user,
                team_name=data.get('team_name'),
            )
            for team_member in formset_data:
                TeamMember.objects.create(
                    team=team,
                    name=team_member.get('name'),
                    email=team_member.get('email'),
                )

            login(request, user)
            team_link = request.build_absolute_uri(
                reverse('team', args=(data.get('team_name'),))
            )
            send_mail_wrapper(
                _('Team created'), 'registration_email',
                {
                    'team_name': data.get('team_name'),
                    'team_link': team_link,
                },
                team.get_emails())
            return redirect('index')
    else:
        form = RegisterForm()
        formset = team_members_formset()

    return render(request, 'register.html', {
        'form': form,
        'team_members_formset': formset,
    })


@require_before_hunt_closed_or_admin
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)

        if form.is_valid():
            form.save()
            # Updating the password logs out all other sessions for the user
            # except the current one.
            update_session_auth_hash(request, form.user)
            return redirect('password_change_done')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'password_change.html', {'form': form})


@require_before_hunt_closed_or_admin
def password_reset(request):
    if request.method == 'POST':
        form = PasswordResetForm(data=request.POST)

        if form.is_valid():
            team = form.cleaned_data.get('team')
            uid = urlsafe_base64_encode(force_bytes(team.user.pk))
            token = default_token_generator.make_token(team.user)
            reset_link = request.build_absolute_uri(reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uid, 'token': token},
            ))

            send_mail_wrapper(
                _('Password reset'), 'password_reset_email',
                {'team_name': team.team_name, 'reset_link': reset_link},
                team.get_emails())
            return redirect('password_reset_done')
    else:
        form = PasswordResetForm()

    return render(request, 'password_reset.html', {'form': form})

@require_GET
def team(request, team_name):
    '''List stats for a single team.'''
    user_team = request.context.team

    is_own_team = user_team is not None and user_team.team_name == team_name
    can_view_info = is_own_team or request.context.is_superuser
    team_query = Team.objects.filter(team_name=team_name)
    if not can_view_info:
        team_query = team_query.exclude(is_hidden=True)
    team = team_query.first()
    if not team:
        messages.error(request, _('Team \u201c{}\u201d not found.').format(team_name))
        return redirect('teams')

    # This Team.leaderboard_teams() call is expensive, but is
    # the only way right now to calculate rank accurately.
    # Hopefully it is not an issue in practice (especially
    # after all this database optimization --beta)
    leaderboard_ids = Team.leaderboard_teams(user_team).values_list('id', flat=True)
    rank = None
    for i, leaderboard_id in enumerate(leaderboard_ids):
        if team.id == leaderboard_id:
            rank = i + 1 # ranks are 1-indexed
            break

    guesses = defaultdict(int)
    correct = {}
    unlock_time_map = {
        puzzle_id: unlock.unlock_datetime
        for (puzzle_id, unlock) in team.db_unlocks.items()
    }

    for submission in team.submissions:
        if submission.is_correct:
            correct[submission.puzzle_id] = {
                'submission': submission,
                'unlock_time': unlock_time_map.get(submission.puzzle_id),
                'solve_time': submission.submitted_datetime,
                'open_duration':
                    (submission.submitted_datetime - unlock_time_map[submission.puzzle_id])
                    .total_seconds() if submission.puzzle_id in unlock_time_map else None,
            }
        else:
            guesses[submission.puzzle_id] += 1
    submissions = []
    for puzzle in correct:
        correct[puzzle]['guesses'] = guesses[puzzle]
        submissions.append(correct[puzzle])
    submissions.sort(key=lambda s: s['solve_time'])
    solves = [HUNT_START_TIME] + [s['solve_time'] for s in submissions]
    if solves[-1] >= HUNT_END_TIME:
        solves.append(min(request.context.now, HUNT_CLOSE_TIME))
    else:
        solves.append(HUNT_END_TIME)
    chart = {
        'hunt_length': (solves[-1] - HUNT_START_TIME).total_seconds(),
        'solves': [{
            'before': (solves[i - 1] - HUNT_START_TIME).total_seconds(),
            'after': (solves[i] - HUNT_START_TIME).total_seconds(),
        } for i in range(1, len(solves))],
        'metas': [
            (s['solve_time'] - HUNT_START_TIME).total_seconds()
            for s in submissions if s['submission'].puzzle.is_meta
        ],
        'end': (HUNT_END_TIME - HUNT_START_TIME).total_seconds(),
    }

    return render(request, 'team.html', {
        'view_team': team,
        'submissions': submissions,
        'chart': chart,
        'solves': sum(1 for s in submissions if not s['submission'].used_free_answer),
        'modify_info_available': is_own_team and not request.context.hunt_is_closed,
        'view_info_available': can_view_info,
        'rank': rank,
    })

def teams_generic(request, hide_hidden):
    '''List all teams on a leaderboard.'''
    team_name = request.GET.get('team')
    user_team = request.context.team

    return render(request, 'teams.html', {
        'teams': Team.leaderboard(user_team, hide_hidden=hide_hidden),
        'current_team': user_team,
    })

@require_GET
def teams(request):
    '''List all teams on the leaderboard.'''
    return teams_generic(request, hide_hidden=True)

@require_GET
@require_admin
def teams_unhidden(request):
    '''List all teams on the leaderboard, including hidden teams.'''
    return teams_generic(request, hide_hidden=False)

@require_before_hunt_closed_or_admin
def edit_team(request):
    team = request.context.team
    if team is None:
        messages.error(request, _('You\u2019re not logged in.'))
        return redirect('login')
    team_members_formset = modelformset_factory(
        TeamMember,
        formset=TeamMemberModelFormset,
        fields=('name', 'email'),
        extra=0,
        min_num=1,
        max_num=MAX_MEMBERS_PER_TEAM,
        validate_max=True,
    )

    if request.method == 'POST':
        # The below works because Django expects "form-INITIAL_FORMS" number of
        # forms to have valid model IDs, but if we delete some number of rows
        # and add more rows simultaneously, every new row has no model ID, so
        # there will be fewer forms with model IDs than the expected number.
        post_data_copy = request.POST.copy()
        num_forms = 0
        for i in range(int(post_data_copy['form-TOTAL_FORMS'])):
            if post_data_copy.get('form-{}-id'.format(i)):
                num_forms += 1
        post_data_copy['form-INITIAL_FORMS'] = str(num_forms)
        post_data_copy['team'] = team
        formset = team_members_formset(post_data_copy)

        if formset.is_valid():
            # Delete team member objects whose form in the formset disappeared
            team_member_ids = set(team.teammember_set.values_list('id', flat=True))
            for form in formset.forms:
                if form.cleaned_data and form.cleaned_data['id'] is not None:
                    team_member_ids.remove(form.cleaned_data['id'].id)
            TeamMember.objects.filter(id__in=team_member_ids).delete()

            # Commit new and edited forms. We must save with commit=False, so
            # we can set the team foreign key on new team members first
            team_member_instances = formset.save(commit=False)
            for team_member in team_member_instances:
                team_member.team = team
                team_member.save()
            messages.success(request, _('Team updated!'))
            return redirect('edit-team')

        if len(formset) == 0: # Another hack, to avoid showing an empty form
            errors = formset.non_form_errors()
            formset = team_members_formset(queryset=team.teammember_set.all())
            formset.non_form_errors().extend(errors)
    else:
        formset = team_members_formset(queryset=team.teammember_set.all())

    return render(request, 'edit_team.html', {'team_members_formset': formset})


@require_GET
def puzzles(request):
    '''List all unlocked puzzles.

    Includes solved puzzles and displays their answer.

    Most teams will visit this page a lot.'''

    if request.context.hunt_has_started:
        return render(request, 'puzzles.html', {'rounds': render_puzzles(request)})
    elif request.context.hunt_has_almost_started:
        return render(request, 'countdown.html', {'start': request.context.start_time})
    else:
        raise Http404


@require_GET
def round(request, slug):
    round = Round.objects.filter(slug=slug).first()
    if round:
        rounds = render_puzzles(request)
        if slug in rounds:
            request.context.round = round
            template_name = 'round_bodies/{}.html'.format(slug)
            try:
                return render(request, template_name, {'round': rounds[slug]})
            except (TemplateDoesNotExist, IsADirectoryError):
                # A plausible cause of it being a directory is that the slug
                # is blank.
                return redirect('puzzles')
    messages.error(request, _('Invalid round name.'))
    return redirect('puzzles')


def render_puzzles(request):
    team = request.context.team
    solved = {}
    hints = {}
    if team is not None:
        solved = team.solves
        hints = Counter(hint.puzzle_id for hint in team.asked_hints)

    correct = defaultdict(int)
    guesses = defaultdict(int)
    teams = defaultdict(set)
    full_stats = request.context.is_superuser or request.context.hunt_is_over
    if full_stats or INITIAL_STATS_AVAILABLE:
        for submission in AnswerSubmission.objects.filter(
            used_free_answer=False,
            team__is_hidden=False,
            submitted_datetime__lt=HUNT_END_TIME,
        ):
            if submission.is_correct:
                correct[submission.puzzle_id] += 1
            guesses[submission.puzzle_id] += 1
            teams[submission.puzzle_id].add(submission.team_id)

    fields = Survey.fields()
    survey_averages = dict() # puzzle.id -> [average rating for field in fields]
    if request.context.is_superuser:
        surveyed_puzzles = Puzzle.objects.annotate(**{
            field.name: Avg('survey__' + field.name)
            for field in fields
        }).values_list('id', *(field.name for field in fields))
        for sp in surveyed_puzzles:
            if all(a is not None for a in sp[1:]):
                survey_averages[sp[0]] = sp[1:]

    rounds = OrderedDict()
    for puzzle in request.context.unlocks:
        if puzzle.round.slug not in rounds:
            rounds[puzzle.round.slug] = {
                'round': puzzle.round,
                'puzzles': [],
                'unlocked_slugs': [],
            }
        rounds[puzzle.round.slug]['unlocked_slugs'].append(puzzle.slug)
        data = {'puzzle': puzzle}
        if puzzle.id in solved:
            data['answer'] = puzzle.answer
            if puzzle.is_meta:
                rounds[puzzle.round.slug]['meta_answer'] = puzzle.answer
        if puzzle.id in hints:
            data['hints'] = hints[puzzle.id]
        data['full_stats'] = full_stats
        if puzzle.id in guesses:
            data['solve_stats'] = {
                'correct': correct[puzzle.id],
                'guesses': guesses[puzzle.id],
                'teams': len(teams[puzzle.id]),
            }
        if puzzle.id in survey_averages:
            data['survey_stats'] = [{
                'average': average,
                'adjective': field.adjective,
                'max_rating': field.max_rating,
            } for (field, average) in zip(fields, survey_averages[puzzle.id])]
        data['new'] = (team and puzzle.id in team.db_unlocks and
            not team.db_unlocks[puzzle.id].view_datetime)
        rounds[puzzle.round.slug]['puzzles'].append(data)
    return rounds


@require_GET
@validate_puzzle()
def puzzle(request):
    '''View a single puzzle's content.'''
    team = request.context.team
    template_name = 'puzzle_bodies/{}'.format(request.context.puzzle.body_template)
    data = {
        'can_view_hints':
            team and not request.context.hunt_is_closed and (
                team.num_hints_total > 0 or
                team.num_free_answers_total > 0
            ),
        'can_ask_for_hints':
            team and not request.context.hunt_is_over and (
                team.num_hints_remaining > 0 or
                team.num_free_answers_remaining > 0
            ),
    }
    try:
        return render(request, template_name, data)
    except (TemplateDoesNotExist, IsADirectoryError):
        # A plausible cause of it being a directory is that the slug
        # is blank.
        data['template_name'] = template_name
        return render(request, 'puzzle.html', data)


@validate_puzzle(require_team=True)
@require_before_hunt_closed_or_admin
def solve(request):
    '''Submit an answer for a puzzle, and check if it's correct.'''

    puzzle = request.context.puzzle
    team = request.context.team
    form = None
    survey = None

    if request.method == 'POST' and 'answer' in request.POST:
        if request.context.puzzle_answer:
            messages.error(request, _('You\u2019ve already solved this puzzle!'))
            return redirect('solve', puzzle.slug)
        if request.context.guesses_remaining <= 0:
            messages.error(request, _('You have no more guesses for this puzzle!'))
            return redirect('solve', puzzle.slug)

        semicleaned_guess = PuzzleMessage.semiclean_guess(request.POST.get('answer'))
        normalized_answer = Puzzle.normalize_answer(request.POST.get('answer'))
        puzzle_messages = [
            message for message in puzzle.puzzlemessage_set.all()
            if semicleaned_guess == message.semicleaned_guess
        ]
        tried_before = any(
            normalized_answer == submission.submitted_answer
            for submission in request.context.puzzle_submissions
        )
        is_correct = normalized_answer == puzzle.normalized_answer

        form = SubmitAnswerForm(request.POST)
        if puzzle_messages:
            for message in puzzle_messages:
                form.add_error(None, message.response)
        elif not normalized_answer:
            form.add_error(None, _('All puzzle answers will have '
                'at least one letter A through Z (case does not matter).'))
        elif tried_before:
            form.add_error(None, _('You\u2019ve already tried calling in the '
                'answer \u201c%s\u201d for this puzzle.') % normalized_answer)
        elif form.is_valid():
            AnswerSubmission(
                team=team,
                puzzle=puzzle,
                submitted_answer=normalized_answer,
                is_correct=is_correct,
                used_free_answer=False,
            ).save()

            if is_correct:
                if not request.context.hunt_is_over:
                    team.last_solve_time = request.context.now
                    team.save()
                messages.success(request, _('%s is correct!') % puzzle.answer)
                if puzzle.slug == META_META_SLUG:
                    dispatch_victory_alert(
                        _('Team %s has finished the hunt!') % team +
                        _('\n**Emails:** <%s>') % request.build_absolute_uri(reverse('finishers')))
                    return redirect('victory')
            else:
                messages.error(request, _('%s is incorrect.') % normalized_answer)
            return redirect('solve', puzzle.slug)

    elif request.method == 'POST':
        if not request.context.puzzle_answer or not SURVEYS_AVAILABLE:
            raise Http404
        survey = SurveyForm(request.POST)
        if survey.is_valid():
            Survey.objects.update_or_create(
                puzzle=puzzle, team=team, defaults=survey.cleaned_data)
            messages.success(request, _('Thanks!'))
            return redirect('solve', puzzle.slug)

    if survey is None and SURVEYS_AVAILABLE:
        survey = SurveyForm(
            instance=Survey.objects.filter(puzzle=puzzle, team=team).first())
    return render(request, 'solve.html', {
        'form': form or SubmitAnswerForm(),
        'survey': survey,
    })


@validate_puzzle(require_team=True)
@require_before_hunt_closed_or_admin
def free_answer(request):
    '''Use a free answer on a puzzle.'''

    puzzle = request.context.puzzle
    team = request.context.team
    if request.method == 'POST':
        if puzzle.is_meta:
            messages.error(request, _('You can\u2019t use a free answer on a metapuzzle.'))
        elif request.context.puzzle_answer:
            messages.error(request, _('You\u2019ve already solved this puzzle!'))
        elif team.num_free_answers_remaining <= 0:
            messages.error(request, _('You have no free answers to use.'))
        elif request.POST.get('use') == 'Yes':
            AnswerSubmission(
                team=team,
                puzzle=puzzle,
                submitted_answer=puzzle.normalized_answer,
                is_correct=True,
                used_free_answer=True,
            ).save()
            messages.success(request, _('Free answer used!'))
        return redirect('solve', puzzle.slug)
    return render(request, 'free_answer.html')


@validate_puzzle()
@require_after_hunt_end_or_admin
def post_hunt_solve(request):
    '''Check an answer client-side for a puzzle after the hunt ends.'''

    puzzle = request.context.puzzle
    answer = Puzzle.normalize_answer(request.GET.get('answer'))
    is_correct = answer == puzzle.normalized_answer
    return render(request, 'post_hunt_solve.html', {
        'is_correct': answer is not None and is_correct,
        'is_wrong': answer is not None and not is_correct,
        'form': SubmitAnswerForm(),
    })


@require_GET
@validate_puzzle()
@require_admin
def survey(request):
    '''For admins. See survey results.'''

    surveys = [
        {'survey': survey, 'ratings': []} for survey in
        request.context.puzzle.survey_set.select_related('team').order_by('id')
    ]
    fields = [
        {'field': field, 'total': 0, 'count': 0, 'max': field.max_rating}
        for field in Survey.fields()
    ]
    for field in fields:
        for survey in surveys:
            rating = field['field'].value_from_object(survey['survey'])
            if not survey['survey'].team.is_hidden:
                field['total'] += rating
                field['count'] += 1
            survey['ratings'].append((rating, field['field'].max_rating))
        field['average'] = field['total'] / field['count'] if field['count'] else 0
    return render(request, 'survey.html', {'fields': fields, 'surveys': surveys})


@require_GET
@require_admin
def hint_list(request):
    '''For admins. By default, list popular and outstanding hint requests.
    With query options, list hints satisfying some query.'''

    if 'team' in request.GET or 'puzzle' in request.GET:
        hints = (
            Hint.objects
            .select_related()
            .order_by('-submitted_datetime')
        )
        query_description = _("Hints")
        if 'team' in request.GET:
            team = Team.objects.get(id=request.GET['team'])
            hints = hints.filter(team=team)
            query_description += _(" from ") + team.team_name
        if 'puzzle' in request.GET:
            puzzle = Puzzle.objects.get(id=request.GET['puzzle'])
            hints = hints.filter(puzzle=puzzle)
            query_description += _(" on ") + puzzle.name
        return render(request, 'hint_list_query.html', {
            'query_description': query_description,
            'hints': hints,
        })
    else:
        unanswered = (
            Hint.objects
            .select_related()
            .filter(status=Hint.NO_RESPONSE)
            .order_by('submitted_datetime')
        )
        popular = list(
            Hint.objects
            .values('puzzle_id')
            .annotate(count=Count('team_id', distinct=True))
            .order_by('-count')
        )
        claimers = list(
            Hint.objects
            .values('claimer')
            .annotate(count=Count('*'))
            .order_by('-count')
        )
        puzzles = {puzzle.id: puzzle for puzzle in request.context.all_puzzles}
        for aggregate in popular:
            aggregate['puzzle'] = puzzles[aggregate['puzzle_id']]
        return render(request, 'hint_list.html', {
            'unanswered': unanswered,
            'stats': itertools.zip_longest(popular, claimers),
        })


@validate_puzzle(require_team=True)
@require_before_hunt_closed_or_admin
def hints(request):
    '''List or submit hint requests for a puzzle.'''

    puzzle = request.context.puzzle
    team = request.context.team
    open_hints = []
    if ONE_HINT_AT_A_TIME:
        open_hints = [hint for hint in team.asked_hints if hint.status == Hint.NO_RESPONSE]
    relevant_hints_remaining = (team.num_hints_remaining
        if puzzle.round.slug == INTRO_ROUND_SLUG
        else team.num_nonintro_hints_remaining)
    puzzle_hints = [hint for hint in reversed(team.asked_hints) if hint.puzzle == puzzle]
    can_followup = bool(puzzle_hints) and puzzle_hints[0].status == Hint.ANSWERED

    error = None
    if request.context.hunt_is_over:
        error = _('Sorry, hints are closed.')
        can_followup = False
    elif team.num_hints_remaining <= 0 and team.num_free_answers_remaining <= 0:
        error = _('You have no hints available!')
    elif relevant_hints_remaining <= 0 and team.num_free_answers_remaining <= 0:
        error = _('You have no hints that can be used on this puzzle.')
    elif open_hints:
        error = (_('You already have a hint open (on %s)! '
            'You can have one hint open at a time.') % open_hints[0].puzzle)
        can_followup = False

    if request.method == 'POST':
        is_followup = can_followup and bool(request.POST.get('is_followup'))
        if error and not is_followup:
            messages.error(request, error)
            return redirect('hints', puzzle.slug)
        form = RequestHintForm(team, request.POST)
        if form.is_valid():
            if relevant_hints_remaining <= 0 and not is_followup:
                team.total_hints_awarded += 1
                team.total_free_answers_awarded -= 1
                team.save()
            Hint(
                team=team,
                puzzle=puzzle,
                hint_question=form.cleaned_data['hint_question'],
                notify_emails=form.cleaned_data['notify_emails'],
                is_followup=is_followup,
            ).save()
            messages.success(request, _(
                'Your request for a hint has been submitted and the puzzle '
                'hunt staff has been notified\u2014we will respond to it soon!'
            ))
            return redirect('hints', puzzle.slug)
    else:
        form = RequestHintForm(team)

    return render(request, 'hints.html', {
        'hints': puzzle_hints,
        'error': error,
        'form': form,
        'intro_count': sum(1 for p in request.context.all_puzzles if p.round.slug == INTRO_ROUND_SLUG),
        'relevant_hints_remaining': relevant_hints_remaining,
        'can_followup': can_followup,
    })


@require_admin
def hint(request, id):
    '''For admins. Handle a particular hint.'''

    hint = Hint.objects.select_related().filter(id=id).first()
    if not hint:
        raise Http404
    form = AnswerHintForm(instance=hint)
    form.cleaned_data = {}

    if request.method == 'POST' and request.POST.get('action') == 'unclaim':
        if hint.status == Hint.NO_RESPONSE:
            hint.claimed_datetime = None
            hint.claimer = ''
            hint.save()
            messages.warning(request, _('Unclaimed.'))
        return redirect('hint-list')
    elif request.method == 'POST':
        form = AnswerHintForm(request.POST)
        if hint.status != request.POST.get('initial_status'):
            form.add_error(None, _('Oh no! The status of this hint changed. '
                'Likely either someone else answered it, or the team solved '
                'the puzzle. You may wish to copy your text and reload.'))
        elif form.is_valid():
            hint.answered_datetime = request.context.now
            hint.status = form.cleaned_data['status']
            hint.response = form.cleaned_data['response']
            hint.save(update_fields=('answered_datetime', 'status', 'response'))
            messages.success(request, _('Hint saved.'))
            return redirect('hint-list')

    claimer = request.COOKIES.get('claimer')
    if claimer:
        claimer = unquote(claimer)
    if hint.status != Hint.NO_RESPONSE:
        if hint.claimer:
            form.add_error(None, _('This hint has been answered by {}!').format(hint.claimer))
        else:
            form.add_error(None, _('This hint has been answered!'))
    elif hint.claimed_datetime:
        if hint.claimer != claimer:
            if hint.claimer:
                form.add_error(None, _('This hint is currently claimed by {}!').format(hint.claimer))
            else:
                form.add_error(None, _('This hint is currently claimed!'))
    elif request.GET.get('claim'):
        if claimer:
            hint.claimed_datetime = request.context.now
            hint.claimer = claimer
            hint.save()
            messages.success(request, _('You have claimed this hint!'))
        else:
            messages.error(request, _('Please set your name before claiming hints! '
                '(If you just set your name, you can refresh or click Claim.)'))

    limit = request.META.get('QUERY_STRING', '')
    limit = int(limit) if limit.isdigit() else 20
    previous_same_team = (
        Hint.objects
        .select_related()
        .filter(team=hint.team, puzzle=hint.puzzle, status__in=(Hint.ANSWERED, Hint.REFUNDED))
        .exclude(id=hint.id)
        .order_by('answered_datetime')
    )
    previous_all_teams = (
        Hint.objects
        .select_related()
        .filter(puzzle=hint.puzzle, status__in=(Hint.ANSWERED, Hint.REFUNDED))
        .exclude(team=hint.team)
        .order_by('-answered_datetime')
    )[:limit]
    form['status'].field.widget.is_followup = hint.is_followup
    request.context.puzzle = hint.puzzle
    return render(request, 'hint.html', {
        'hint': hint,
        'previous_same_team': previous_same_team,
        'previous_all_teams': previous_all_teams,
        'form': form,
    })


@require_GET
@require_after_hunt_end_or_admin
def hunt_stats(request):
    '''After hunt ends, view stats for the entire hunt.'''

    total_teams = Team.objects.exclude(is_hidden=True).count()
    total_participants = TeamMember.objects.exclude(team__is_hidden=True).count()

    def is_forward_solve(puzzle, team_id):
        return (puzzle.is_meta or
            solve_times[puzzle.id, team_id] <=
            solve_times[puzzle.round.meta_id, team_id] - datetime.timedelta(minutes=5))

    total_hints = 0
    hints_by_puzzle = defaultdict(int)
    hint_counts = defaultdict(int)
    for hint in Hint.objects.exclude(team__is_hidden=True):
        total_hints += 1
        hints_by_puzzle[hint.puzzle_id] += 1
        if hint.consumes_hint:
            hint_counts[hint.puzzle_id, hint.team_id] += 1

    total_guesses = 0
    total_solves = 0
    total_metas = 0
    guesses_by_puzzle = defaultdict(int)
    solves_by_puzzle = defaultdict(int)
    guess_teams = defaultdict(set)
    solve_teams = defaultdict(set)
    solve_times = defaultdict(lambda: HUNT_CLOSE_TIME)
    for submission in (
        AnswerSubmission.objects
        .filter(used_free_answer=False, team__is_hidden=False, submitted_datetime__lt=HUNT_END_TIME)
    ):
        total_guesses += 1
        guesses_by_puzzle[submission.puzzle_id] += 1
        guess_teams[submission.puzzle_id].add(submission.team_id)
        if submission.is_correct:
            total_solves += 1
            solves_by_puzzle[submission.puzzle_id] += 1
            solve_teams[submission.puzzle_id].add(submission.team_id)
            solve_times[submission.puzzle_id, submission.team_id] = submission.submitted_datetime

    data = []
    for puzzle in request.context.all_puzzles:
        if puzzle.is_meta:
            total_metas += solves_by_puzzle[puzzle.id]
        data.append({'puzzle': puzzle, 'numbers': [
            solves_by_puzzle[puzzle.id],
            guesses_by_puzzle[puzzle.id],
            hints_by_puzzle[puzzle.id],
            len([1 for team_id in solve_teams[puzzle.id] if is_forward_solve(puzzle, team_id)]),
            len([1 for team_id in solve_teams[puzzle.id] if is_forward_solve(puzzle, team_id) and hint_counts[puzzle.id, team_id] < 1]),
            len([1 for team_id in solve_teams[puzzle.id] if is_forward_solve(puzzle, team_id) and hint_counts[puzzle.id, team_id] == 1]),
            len([1 for team_id in solve_teams[puzzle.id] if is_forward_solve(puzzle, team_id) and hint_counts[puzzle.id, team_id] > 1]),
            len([1 for team_id in solve_teams[puzzle.id] if not is_forward_solve(puzzle, team_id)]),
            len(guess_teams[puzzle.id] - solve_teams[puzzle.id]),
        ]})

    return render(request, 'hunt_stats.html', {
        'total_teams': total_teams,
        'total_participants': total_participants,
        'total_hints': total_hints,
        'total_guesses': total_guesses,
        'total_solves': total_solves,
        'total_metas': total_metas,
        'data': data,
    })


@require_GET
@validate_puzzle()
@require_after_hunt_end_or_admin
def stats(request):
    '''After hunt ends, view stats for a specific puzzle.'''

    puzzle = request.context.puzzle
    team = request.context.team
    q = Q(team__is_hidden=False)
    if team:
        q |= Q(team__id=team.id)
    puzzle_submissions = (
        puzzle.answersubmission_set
        .filter(q, used_free_answer=False, submitted_datetime__lt=HUNT_END_TIME)
        .order_by('submitted_datetime')
        .select_related('team')
    )

    solve_time_map = {}
    total_guesses_map = defaultdict(int)
    solvers_map = {}
    unlock_time_map = {
        unlock.team_id: unlock.unlock_datetime
        for unlock in puzzle.puzzleunlock_set.all()
    }
    incorrect_guesses = Counter()
    guess_time_map = {}
    for submission in puzzle_submissions:
        team_id = submission.team_id
        total_guesses_map[team_id] += 1
        if submission.is_correct:
            solve_time_map[team_id] = submission.submitted_datetime
            solvers_map[team_id] = submission.team
        else:
            incorrect_guesses[submission.submitted_answer] += 1
            guess_time_map[team_id, submission.submitted_answer] = submission.submitted_datetime
    wrong = '(?)'
    if incorrect_guesses:
        (wrong, _), = incorrect_guesses.most_common(1)
    solvers = [{
        'team': solver,
        'is_current': solver == team,
        'unlock_time': unlock_time_map.get(solver.id),
        'solve_time': solve_time_map[solver.id],
        'wrong_duration':
            (solve_time_map[solver.id] - guess_time_map[solver.id, wrong])
            .total_seconds() if (solver.id, wrong) in guess_time_map else None,
        'open_duration':
            (solve_time_map[solver.id] - unlock_time_map[solver.id])
            .total_seconds() if solver.id in unlock_time_map else None,
        'total_guesses': total_guesses_map[solver.id] - 1,
    } for solver in solvers_map.values()]
    solvers.sort(key=lambda d: d['solve_time'])

    return render(request, 'stats.html', {
        'solvers': solvers,
        'solves': len(solvers_map),
        'guesses': sum(total_guesses_map.values()),
        'answers_tried': incorrect_guesses.most_common(),
        'wrong': wrong,
    })


@require_GET
@validate_puzzle()
@require_after_hunt_end_or_admin
def solution(request):
    '''After hunt ends, view a puzzle's solution.'''

    template_name = 'solution_bodies/{}'.format(request.context.puzzle.body_template)
    try:
        return render(request, template_name, {})
    except TemplateDoesNotExist:
        return render(request, 'solution.html', {'template_name': template_name})


@require_GET
@require_after_hunt_end_or_admin
def solution_static(request, path):
    return serve(request, path, document_root=settings.SOLUTION_STATIC_ROOT)


@require_GET
def story(request):
    '''View your team's story page based on your current progress.'''

    # FIXME: This will depend a lot on your hunt. It might not make any sense
    # at all.
    if not STORY_PAGE_VISIBLE:
        raise Http404
    story_points = OrderedDict((
        ('pre_hunt', not request.context.hunt_has_almost_started),
        ('round1_open', request.context.hunt_has_almost_started), ('meta1_done', False),
        ('round2_open', False), ('meta2_done', False),
    ))
    if request.context.hunt_has_started:
        for puzzle in request.context.unlocks:
            story_points['round%d_open' % puzzle.round.order] = True
        if request.context.team:
            for puzzle in request.context.team.solves.values():
                if puzzle.is_meta:
                    story_points['meta%d_done' % puzzle.round.order] = True
    story_points = [key for (key, visible) in story_points.items() if visible]
    if not request.context.hunt_is_over:
        story_points.reverse()
    return render(request, 'story.html', {'story_points': story_points})


@require_GET
def victory(request):
    '''View your team's victory page, if you've finished the hunt.'''

    team = request.context.team
    if not request.context.hunt_is_over and not request.context.is_superuser:
        if not team or not request.context.hunt_has_started:
            raise Http404
        finished = any(puzzle.slug == META_META_SLUG for puzzle in team.solves.values())
        if not finished:
            raise Http404
    return render(request, 'victory.html')


@require_GET
def errata(request):
    if not request.context.errata_page_visible:
        raise Http404
    return render(request, 'errata.html')


@require_GET
def wrapup(request):
    if not WRAPUP_PAGE_VISIBLE:
        raise Http404
    return render(request, 'wrapup.html')


@require_GET
@require_after_hunt_end_or_admin
def finishers(request):
    unlocks = OrderedDict()
    solves_by_team = defaultdict(list)
    metas_by_team = defaultdict(list)
    wrong_times = {}

    for submission in AnswerSubmission.objects.filter(
        puzzle__slug=META_META_SLUG,
        team__is_hidden=False,
        submitted_datetime__lt=HUNT_END_TIME,
    ).order_by('submitted_datetime'):
        if submission.is_correct:
            unlocks[submission.team_id] = None
        else:
            wrong_times[submission.team_id] = submission.submitted_datetime
    for unlock in PuzzleUnlock.objects.select_related().filter(
        team__id__in=unlocks,
        puzzle__slug=META_META_SLUG,
    ):
        unlocks[unlock.team_id] = unlock
    for solve in AnswerSubmission.objects.select_related().filter(
        team__id__in=unlocks,
        used_free_answer=False,
        is_correct=True,
        submitted_datetime__lt=HUNT_END_TIME,
    ).order_by('submitted_datetime'):
        solves_by_team[solve.team_id].append(solve.submitted_datetime)
        if solve.puzzle.is_meta:
            metas_by_team[solve.team_id].append(solve.submitted_datetime)

    data = []
    for team_id, unlock in unlocks.items():
        solves = [HUNT_START_TIME] + solves_by_team[team_id] + [HUNT_END_TIME]
        solves = [{
            'before': (solves[i - 1] - HUNT_START_TIME).total_seconds(),
            'after': (solves[i] - HUNT_START_TIME).total_seconds(),
        } for i in range(1, len(solves))]
        metas = metas_by_team[team_id]
        times = [unlock.unlock_datetime, wrong_times.get(team_id), metas[-1]]
        last_time = times[0]
        milestones = []
        for i in range(1, len(times)):
            if times[i]:
                milestones.append((times[i], (times[i] - last_time).total_seconds()))
                last_time = times[i]
            else:
                milestones.append((times[i], None))
        data.append({
            'team': unlock.team,
            'unlock_time': times[0],
            'solve_time': times[-1],
            'milestones': milestones,
            'total_time': (times[-1] - times[0]).total_seconds(),
            'hunt_length': (HUNT_END_TIME - HUNT_START_TIME).total_seconds(),
            'solves': solves,
            'metas': [(ts - HUNT_START_TIME).total_seconds() for ts in metas],
        })
    if request.context.is_superuser:
        data.reverse()
    return render(request, 'finishers.html', {'data': data})

@require_GET
@require_admin
def bridge(request):
    recipients = TeamMember.objects.values_list('email', flat=True)
    recipients = list(filter(None, recipients))
    recipient_count = len(recipients)
    recipients_list = '\n'.join(recipients)
    return render(request, 'bridge.html', {
        'recipient_count': recipient_count,
        'recipients_list': recipients_list,
    })

def bigboard_generic(request, hide_hidden):
    puzzles = request.context.all_puzzles
    puzzle_map = {}
    puzzle_metas = {}
    meta_meta_id = None
    for puzzle in puzzles:
        puzzle_map[puzzle.id] = puzzle
        if puzzle.slug == META_META_SLUG:
            meta_meta_id = puzzle.id
        if not puzzle.is_meta:
            puzzle_metas[puzzle.id] = puzzle.round.meta_id

    wrong_guesses_map = defaultdict(int) # key (team, puzzle)
    wrong_guesses_by_team_map = defaultdict(int) # key team
    solve_position_map = dict() # key (team, puzzle); value n if team is nth to solve this puzzle
    solve_count_map = defaultdict(int) # puzzle -> number of counts
    total_guess_map = defaultdict(int) # puzzle -> number of guesses
    used_hints_map = defaultdict(int) # (team, puzzle) -> number of hints
    used_hints_by_team_map = defaultdict(int) # team -> number of hints
    used_hints_by_puzzle_map = defaultdict(int) # puzzle -> number of hints
    solves_map = defaultdict(dict) # team -> {puzzle id -> puzzle}
    meta_solves_map = defaultdict(int) # team -> number of meta solves
    solve_time_map = defaultdict(dict) # team -> {puzzle id -> solve time}
    during_hunt_solve_time_map = defaultdict(dict) # team -> {puzzle id -> solve time}
    free_answer_map = defaultdict(set) # team -> {puzzle id}
    free_answer_by_puzzle_map = defaultdict(int) # puzzle -> number of free answers

    correct_q = Q(is_correct=True)
    incorrect_q = Q(is_correct=False)
    if hide_hidden:
        correct_q &= Q(team__is_hidden=False)
        incorrect_q &= Q(team__is_hidden=False)

    for team_id, puzzle_id, used_free_answer, submitted_datetime in (
        AnswerSubmission.objects
        .filter(correct_q)
        .order_by('submitted_datetime')
        .values_list('team_id', 'puzzle_id', 'used_free_answer', 'submitted_datetime')
    ):
        total_guess_map[puzzle_id] += 1
        if used_free_answer:
            free_answer_map[team_id].add(puzzle_id)
            free_answer_by_puzzle_map[puzzle_id] += 1
        else:
            solve_count_map[puzzle_id] += 1
            solve_position_map[(team_id, puzzle_id)] = solve_count_map[puzzle_id]
            solve_time_map[team_id][puzzle_id] = submitted_datetime
            if submitted_datetime < HUNT_END_TIME:
                during_hunt_solve_time_map[team_id][puzzle_id] = submitted_datetime
        solves_map[team_id][puzzle_id] = puzzle_map[puzzle_id]
        if puzzle_id not in puzzle_metas:
            meta_solves_map[team_id] += 1

    for aggregate in (
        AnswerSubmission.objects
        .filter(incorrect_q)
        .values('team_id', 'puzzle_id')
        .annotate(count=Count('*'))
    ):
        team_id = aggregate['team_id']
        puzzle_id = aggregate['puzzle_id']
        total_guess_map[puzzle_id] += aggregate['count']
        wrong_guesses_map[(team_id, puzzle_id)] += aggregate['count']
        wrong_guesses_by_team_map[team_id] += aggregate['count']

    for aggregate in (
        Hint.objects
        .filter(status=Hint.ANSWERED, is_followup=False)
        .values('team_id', 'puzzle_id')
        .annotate(count=Count('*'))
    ):
        team_id = aggregate['team_id']
        puzzle_id = aggregate['puzzle_id']
        used_hints_map[(team_id, puzzle_id)] += aggregate['count']
        used_hints_by_team_map[team_id] += aggregate['count']
        used_hints_by_puzzle_map[puzzle_id] += aggregate['count']

    if hide_hidden:
        teams = Team.objects.filter(is_hidden=False)
    else:
        teams = Team.objects.all()

    # Reproduce Team.leaderboard behavior for ignoring solves after hunt end,
    # but not _teams_ created after hunt end. They'll just all be at the bottom.
    leaderboard = sorted(teams, key=lambda team: (
        during_hunt_solve_time_map[team.id].get(meta_meta_id, HUNT_END_TIME),
        -len(during_hunt_solve_time_map[team.id]),
        team.last_solve_time or team.creation_time,
    ))
    limit = request.META.get('QUERY_STRING', '')
    limit = int(limit) if limit.isdigit() else 0
    if limit:
        leaderboard = leaderboard[:limit]
    unlocks = set(PuzzleUnlock.objects.values_list('team_id', 'puzzle_id'))
    unlock_count_map = defaultdict(int)

    def classes_of(team_id, puzzle_id):
        unlocked = (team_id, puzzle_id) in unlocks
        if unlocked:
            unlock_count_map[puzzle_id] += 1
        solve_time = solve_time_map[team_id].get(puzzle_id)
        if puzzle_id in free_answer_map[team_id]:
            yield 'F' # free answer
        elif solve_time:
            yield 'S' # solved
        elif wrong_guesses_map.get((team_id, puzzle_id)):
            yield 'W' # wrong
        elif unlocked:
            yield 'U' # unlocked
        if used_hints_map.get((team_id, puzzle_id)):
            yield 'H' # hinted
        if solve_time and solve_time > HUNT_END_TIME:
            yield 'P' # post-hunt solve
        if solve_time and puzzle_id in puzzle_metas:
            meta_time = solve_time_map[team_id].get(puzzle_metas[puzzle_id])
            if meta_time and solve_time > meta_time - datetime.timedelta(minutes=5):
                yield 'B' # backsolved

    board = []
    for team in leaderboard:
        board.append({
            'team': team,
            'last_solve_time': max([team.creation_time, *solve_time_map[team.id].values()]),
            'total_solves': len(solve_time_map[team.id]),
            'free_solves': len(free_answer_map[team.id]),
            'wrong_guesses': wrong_guesses_by_team_map[team.id],
            'used_hints': used_hints_by_team_map[team.id],
            'finished': solve_position_map.get((team.id, meta_meta_id)),
            'meta_solves': meta_solves_map[team.id],
            'entries': [{
                'wrong_guesses': wrong_guesses_map[(team.id, puzzle.id)],
                'solve_position': solve_position_map.get((team.id, puzzle.id)),
                'hints': used_hints_map[(team.id, puzzle.id)],
                'cls': ' '.join(classes_of(team.id, puzzle.id)),
            } for puzzle in puzzles]
        })

    annotated_puzzles = [{
        'puzzle': puzzle,
        'solves': solve_count_map[puzzle.id],
        'free_solves': free_answer_by_puzzle_map[puzzle.id],
        'total_guesses': total_guess_map[puzzle.id],
        'total_unlocks': unlock_count_map[puzzle.id],
        'hints': used_hints_by_puzzle_map[puzzle.id],
    } for puzzle in puzzles]

    return render(request, 'bigboard.html', {
        'board': board,
        'puzzles': annotated_puzzles,
    })

@require_GET
@require_after_hunt_end_or_admin
def bigboard(request):
    return bigboard_generic(request, hide_hidden=True)

@require_GET
@require_admin
def bigboard_unhidden(request):
    return bigboard_generic(request, hide_hidden=False)

@require_GET
@require_after_hunt_end_or_admin
def biggraph(request):
    puzzles = request.context.all_puzzles
    puzzle_map = {}
    meta_meta_id = None
    for puzzle in puzzles:
        puzzle_map[puzzle.id] = puzzle
        if puzzle.slug == META_META_SLUG:
            meta_meta_id = puzzle.id

    during_hunt_solve_time_map = defaultdict(dict) # team -> {puzzle id -> solve time}
    team_point_changes = defaultdict(list)
    team_score = defaultdict(int) # ???

    for team_id, puzzle_id, submitted_datetime in (
        AnswerSubmission.objects
        .filter(is_correct=True, team__is_hidden=False, used_free_answer=False)
        .order_by('submitted_datetime')
        .values_list('team_id', 'puzzle_id', 'submitted_datetime')
    ):
        team_score[team_id] += 1
        puzzle = puzzle_map[puzzle_id]
        team_point_changes[team_id].append((
            submitted_datetime.timestamp() * 1000,
            team_score[team_id],
            puzzle.name,
            puzzle.is_meta,
        ))
        if submitted_datetime < HUNT_END_TIME:
            during_hunt_solve_time_map[team_id][puzzle_id] = submitted_datetime

    teams = Team.objects.filter(is_hidden=False)
    leaderboard = sorted(teams, key=lambda team: (
        during_hunt_solve_time_map[team.id].get(meta_meta_id, HUNT_END_TIME),
        -len(during_hunt_solve_time_map[team.id]),
        team.last_solve_time or team.creation_time,
    ))

    limit = request.META.get('QUERY_STRING', '')
    limit = int(limit) if limit.isdigit() else 30
    if limit:
        leaderboard = leaderboard[:limit]

    for team in leaderboard:
        nh = 0
        for c in team.team_name:
            nh = (31 * nh + ord(c)) & 0xffffffff;
        team.color = 'hsl({}, {}%, {}%)'.format(nh % 360, 77 + nh % 23, 41 + nh % 19)
        team.graph_data = team_point_changes[team.id]

    return render(request, 'biggraph.html', {
        'teams': leaderboard
    })

@require_GET
@require_after_hunt_end_or_admin
def guess_csv(request):
    response = HttpResponse(content_type='text/csv')
    fname = 'gph_guesslog_{}.csv'.format(request.context.now.strftime('%Y%m%dT%H%M%S'))
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(fname)
    writer = csv.writer(response)
    for ans in (
        AnswerSubmission.objects
        .annotate(team_name=F('team__team_name'), puzzle_name=F('puzzle__name'))
        .order_by('submitted_datetime')
        .exclude(team__is_hidden=True)
    ):
        writer.writerow([
            ans.submitted_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            ans.team_name,
            ans.puzzle_name,
            ans.submitted_answer,
            'F' if ans.used_free_answer else ('Y' if ans.is_correct else 'N')])
    return response


@require_GET
@require_admin
def hint_csv(request):
    response = HttpResponse(content_type='text/csv')
    fname = 'gph_hintlog_{}.csv'.format(request.context.now.strftime('%Y%m%dT%H%M%S'))
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(fname)
    writer = csv.writer(response)
    for hint in (
        Hint.objects
        .annotate(team_name=F('team__team_name'), puzzle_name=F('puzzle__name'))
        .order_by('submitted_datetime')
        .exclude(team__is_hidden=True)
    ):
        writer.writerow([
            hint.submitted_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            None if hint.answered_datetime is None else (
                hint.answered_datetime.strftime('%Y-%m-%d %H:%M:%S')
            ),
            hint.team_name,
            hint.puzzle_name,
            hint.response])
    return response


@require_GET
@require_admin
def puzzle_log(request):
    return serve(request, os.path.join(settings.BASE_DIR,
        settings.LOGGING['handlers']['puzzle']['filename']), document_root='/')


@require_POST
@require_admin
@xframe_options_sameorigin
def shortcuts(request):
    response = HttpResponse(content_type='text/html')
    try:
        dispatch_shortcut(request)
    except Exception as e:
        response.write('<script>top.toastr.error(%s)</script>' % (
            json.dumps('<br>'.join(escape(str(part)) for part in e.args))))
    else:
        response.write('<script>top.location.reload()</script>')
    return response


def robots(request):
    response = HttpResponse(content_type='text/plain')
    if settings.DEBUG:
        response.write('User-agent: *\nDisallow: /\n')
    else:
        response.write('User-agent: *\nDisallow: /solution/\n')
    return response
