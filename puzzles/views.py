import csv
import datetime
import json
import os
from collections import defaultdict, OrderedDict, Counter
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.db.models import F, Q, Count
from django.forms import formset_factory, modelformset_factory
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.html import escape
from django.utils.http import urlsafe_base64_encode, urlencode
from django.views.decorators.http import require_GET, require_POST
from django.views.static import serve

from puzzles.models import (
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
    ERRATA_PAGE_VISIBLE,
    WRAPUP_PAGE_VISIBLE,
    SURVEYS_AVAILABLE,
    HUNT_START_TIME,
    HUNT_END_TIME,
    HUNT_CLOSE_TIME,
    MAX_MEMBERS_PER_TEAM,
    DEEP_MAX,
    INTRO_META_SLUG,
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
            if not puzzle or puzzle.id not in request.context.unlocks['ids']:
                messages.error(request, 'Invalid puzzle name.')
                return redirect('puzzles')
            if require_team and not request.context.team:
                messages.error(
                    request,
                    'You must be signed in and have a registered team to '
                    'access this page.'
                )
                return redirect('puzzle', slug)
            request.context.puzzle = puzzle
            return f(request)
        return inner
    return decorator


def restrict_access(after_hunt_end=None):
    '''
    Indicates an endpoint that is hidden to all regular users. Superusers are
    always allowed access. Behavior depends on after_hunt_end:
    - if None, the page is admin-only.
    - if True, the page becomes visible when the hunt ends.
    - if False, the page becomes inaccessible when the hunt closes.
    '''
    def decorator(f):
        @wraps(f)
        def inner(request, *args, **kwargs):
            if not request.context.is_superuser:
                if after_hunt_end is None:
                    raise Http404
                elif after_hunt_end and not request.context.hunt_is_over:
                    messages.error(request, 'Sorry, not available until the hunt ends.')
                    return redirect('index')
                elif not after_hunt_end and request.context.hunt_is_closed:
                    messages.error(request, 'Sorry, the hunt is over.')
                    return redirect('index')
            return f(request, *args, **kwargs)
        return inner
    return decorator

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


@restrict_access(after_hunt_end=False)
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
            send_mail_wrapper(
                'Team created', 'registration_email',
                {
                    'team_name': data.get('team_name'),
                    'team_link':
                        request.build_absolute_uri(reverse('teams')) +
                        '?' + urlencode({'team': data.get('team_name')}),
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


@restrict_access(after_hunt_end=False)
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


@restrict_access(after_hunt_end=False)
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
                'Password reset', 'password_reset_email',
                {'team_name': team.team_name, 'reset_link': reset_link},
                team.get_emails())
            return redirect('password_reset_done')
    else:
        form = PasswordResetForm()

    return render(request, 'password_reset.html', {'form': form})


@require_GET
def teams(request):
    '''List all teams on a leaderboard.'''
    team_name = request.GET.get('team')
    user_team = request.context.team

    if team_name:
        is_own_team = user_team is not None and user_team.team_name == team_name
        can_view_info = is_own_team or request.context.is_superuser
        team_query = Team.objects.filter(team_name=team_name)
        if not can_view_info:
            team_query = team_query.exclude(is_hidden=True)
        team = team_query.first()
        if not team:
            messages.error(request, 'Team \u201c{}\u201d not found.'.format(team_name))
            return redirect('teams')

        # This Team.leaderboard() call is expensive, but is the only way
        # right now to calculate rank accurately. Hopefully it is not an
        # issue in practice.
        leaderboard = Team.leaderboard(user_team)
        rank = None
        for i, leaderboard_team in enumerate(leaderboard):
            if team.team_name == leaderboard_team['team_name']:
                rank = i + 1 # ranks are 1-indexed
                break

        guesses = defaultdict(int)
        correct = {}
        team_solves = {}
        unlock_time_map = {
            unlock.puzzle_id: unlock.unlock_datetime
            for unlock in team.db_unlocks
        }
        for submission in team.submissions:
            if submission.is_correct:
                team_solves[submission.puzzle_id] = submission.puzzle
                correct[submission.puzzle_id] = {
                    'slug': submission.puzzle.slug,
                    'name': submission.puzzle.name,
                    'is_meta': submission.puzzle.is_meta,
                    'answer': submission.submitted_answer,
                    'unlock_time': unlock_time_map.get(submission.puzzle_id),
                    'solve_time': submission.submitted_datetime,
                    'used_free_answer': submission.used_free_answer,
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
        submissions.sort(key=lambda submission: submission['solve_time'])
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
                for s in submissions if s['is_meta']
            ],
            'end': (HUNT_END_TIME - HUNT_START_TIME).total_seconds(),
        }
        team.solves = team_solves

        return render(request, 'team.html', {
            'view_team': team,
            'submissions': submissions,
            'chart': chart,
            'solves': sum(1 for s in submissions if not s['used_free_answer']),
            'modify_info_available': is_own_team and not request.context.hunt_is_closed,
            'view_info_available': can_view_info,
            'rank': rank,
        })

    return render(request, 'teams.html', {'teams': Team.leaderboard(user_team)})


@restrict_access(after_hunt_end=False)
def edit_team(request):
    team = request.context.team
    if team is None:
        messages.error(request, 'You\u2019re not logged in.')
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
            messages.success(request, 'Team updated!')
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
        pass
    elif request.context.hunt_has_almost_started:
        return render(request, 'countdown.html', {'start': HUNT_START_TIME})
    else:
        raise Http404
    team = request.context.team

    solved = {}
    hints = {}
    if team is not None:
        solved = team.solves
        hints = Counter(team.hint_set.values_list('puzzle__id', flat=True))

    correct = defaultdict(int)
    guesses = defaultdict(int)
    teams = defaultdict(set)
    full_stats = request.context.is_superuser or request.context.hunt_is_over
    for submission in (
        AnswerSubmission.objects
        .filter(used_free_answer=False, team__is_hidden=False, submitted_datetime__lt=HUNT_END_TIME)
    ):
        if submission.is_correct:
            correct[submission.puzzle_id] += 1
        guesses[submission.puzzle_id] += 1
        teams[submission.puzzle_id].add(submission.team_id)

    fields = Survey.fields()
    surveys = defaultdict(lambda: {'count': 0, 'totals': [0 for _ in fields]})
    if SURVEYS_AVAILABLE:
        # We can consider adding a threshold for e.g. only showing these
        # results once at least N teams have filled out the survey.
        for survey in Survey.objects.filter(team__is_hidden=False):
            surveys[survey.puzzle_id]['count'] += 1
            for i, field in enumerate(fields):
                surveys[survey.puzzle_id]['totals'][i] += field.value_from_object(survey)

    unlocks = request.context.unlocks
    for data in unlocks['puzzles']:
        puzzle_id = data['puzzle'].id
        if puzzle_id in solved:
            data['answer'] = solved[puzzle_id].normalized_answer
        if puzzle_id in hints:
            data['hints'] = hints[puzzle_id]
        data['full_stats'] = full_stats
        data['solve_stats'] = {
            'correct': correct[puzzle_id],
            'guesses': guesses[puzzle_id],
            'teams': len(teams[puzzle_id]),
        }
        if puzzle_id in surveys:
            data['survey_stats'] = [{
                'average': total / surveys[puzzle_id]['count'],
                'adjective': field.adjective,
                'max_rating': field.max_rating,
            } for (field, total) in zip(fields, surveys[puzzle_id]['totals'])]

    return render(request, 'puzzles.html')


@require_GET
@validate_puzzle()
def puzzle(request):
    '''View a single puzzle's content.'''
    team = request.context.team
    template_name = 'puzzle_bodies/{}'.format(request.context.puzzle.body_template)
    data = {
        'template_name': template_name,
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
    except TemplateDoesNotExist:
        return render(request, 'puzzle.html', data)


@validate_puzzle(require_team=True)
@restrict_access(after_hunt_end=False)
def solve(request):
    '''Submit an answer for a puzzle, and check if it's correct.'''

    puzzle = request.context.puzzle
    team = request.context.team
    form = None
    survey = None

    if request.method == 'POST' and 'answer' in request.POST:
        if request.context.puzzle_answer:
            messages.error(request, 'You\u2019ve already solved this puzzle!')
            return redirect('solve', puzzle.slug)
        if request.context.guesses_remaining <= 0:
            messages.error(request, 'You have no more guesses for this puzzle!')
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
            form.add_error(None, 'All puzzle answers will have '
                'at least one letter A through Z (case does not matter).')
        elif tried_before:
            form.add_error(None, 'You\u2019ve already tried calling in the '
                'answer \u201c%s\u201d for this puzzle.' % normalized_answer)
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
                if puzzle.slug == META_META_SLUG:
                    return redirect('victory')
                else:
                    messages.success(request, '%s is correct!' % normalized_answer)
            else:
                messages.error(request, '%s is incorrect.' % normalized_answer)
            return redirect('solve', puzzle.slug)

    elif request.method == 'POST':
        if not request.context.puzzle_answer or not SURVEYS_AVAILABLE:
            raise Http404
        survey = SurveyForm(request.POST)
        if survey.is_valid():
            Survey.objects.update_or_create(
                puzzle=puzzle, team=team, defaults=survey.cleaned_data)
            messages.success(request, 'Thanks!')
            return redirect('solve', puzzle.slug)

    if survey is None and SURVEYS_AVAILABLE:
        survey = SurveyForm(
            instance=Survey.objects.filter(puzzle=puzzle, team=team).first())
    return render(request, 'solve.html', {
        'form': form or SubmitAnswerForm(),
        'survey': survey,
    })


@validate_puzzle(require_team=True)
@restrict_access(after_hunt_end=False)
def free_answer(request):
    '''Use a free answer on a puzzle.'''

    puzzle = request.context.puzzle
    team = request.context.team
    if request.method == 'POST':
        if puzzle.is_meta:
            messages.error(request, 'You can\u2019t use a free answer on a metapuzzle.')
        elif request.context.puzzle_answer:
            messages.error(request, 'You\u2019ve already solved this puzzle!')
        elif team.num_free_answers_remaining <= 0:
            messages.error(request, 'You have no free answers to use.')
        elif request.POST.get('use') == 'Yes':
            AnswerSubmission(
                team=team,
                puzzle=puzzle,
                submitted_answer=puzzle.normalized_answer,
                is_correct=True,
                used_free_answer=True,
            ).save()
            messages.success(request, 'Free answer used!')
        return redirect('solve', puzzle.slug)
    return render(request, 'free_answer.html')


@validate_puzzle()
@restrict_access(after_hunt_end=True)
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
@restrict_access()
def survey(request):
    '''For admins. See survey reuslts.'''

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
@restrict_access()
def hint_list(request):
    '''For admins. List popular and outstanding hint requests.'''

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
    puzzles = {puzzle.id: puzzle for puzzle in request.context.all_puzzles}
    for aggregate in popular:
        aggregate['puzzle'] = puzzles[aggregate['puzzle_id']]
    return render(request, 'hint_list.html', {
        'popular': popular,
        'unanswered': unanswered,
    })


@validate_puzzle(require_team=True)
@restrict_access(after_hunt_end=False)
def hints(request):
    '''List or submit hint requests for a puzzle.'''

    puzzle = request.context.puzzle
    team = request.context.team

    if request.method == 'POST':
        if request.context.puzzle_answer is not None:
            messages.error(request, 'You have already solved this puzzle!')
            return redirect('hints', puzzle.slug)
        if team.num_hints_remaining <= 0 and team.num_free_answers_remaining <= 0:
            messages.error(request, 'You have no more hints available!')
            return redirect('hints', puzzle.slug)
        form = RequestHintForm(team, request.POST)

        if form.is_valid():
            hint_question = form.cleaned_data['hint_question']
            notify_emails = form.cleaned_data['notify_emails']

            if Hint.objects.filter(
                    team=team,
                    puzzle=puzzle,
                    hint_question=hint_question).exists():
                messages.error(
                    request,
                    'You\u2019ve already asked the exact same hint question!',
                )
                return redirect('hints', puzzle.slug)

            if team.num_hints_remaining <= 0:
                team.total_hints_awarded += 1
                team.total_free_answers_awarded -= 1
                team.save()

            Hint(
                team=team,
                puzzle=puzzle,
                hint_question=hint_question,
                notify_emails=notify_emails,
            ).save()

            messages.success(request, (
                'Your request for a hint has been submitted and the puzzle '
                'hunt staff has been notified\u2014we will respond to it soon!'
            ))
            return redirect('hints', puzzle.slug)
    else:
        form = RequestHintForm(team)

    return render(request, 'hints.html', {
        'hints': Hint.objects.filter(team=team, puzzle=puzzle),
        'form': form,
    })


@restrict_access()
def hint(request, id):
    '''For admins. Handle a particular hint.'''

    hint = Hint.objects.select_related().filter(id=id).first()
    if not hint:
        raise Http404
    form = AnswerHintForm(instance=hint)
    form.cleaned_data = {}

    if request.method == 'POST' and request.POST.get('action') == 'Unclaim':
        if hint.status == Hint.NO_RESPONSE:
            hint.claimed_datetime = None
            hint.claimer = None
            hint.save()
            messages.warning(request, 'Unclaimed.')
        return redirect('hint-list')
    elif request.method == 'POST':
        form = AnswerHintForm(request.POST)
        if form.is_valid():
            hint.answered_datetime = request.context.now
            hint.status = form.cleaned_data['status']
            hint.response = form.cleaned_data['response']
            hint.save(update_fields=('answered_datetime', 'status', 'response'))
            messages.success(request, 'Hint saved.')
            return redirect('hint-list')

    claimer = request.COOKIES.get('claimer', '')
    if hint.status != Hint.NO_RESPONSE:
        form.add_error(None, 'This hint has been answered{}!'.format(
            ' by ' + hint.claimer if hint.claimer else ''))
    elif hint.claimed_datetime:
        if hint.claimer != claimer:
            form.add_error(None, 'This hint is currently claimed{}!'.format(
                ' by ' + hint.claimer if hint.claimer else ''))
    else:
        hint.claimed_datetime = request.context.now
        hint.claimer = claimer or 'anonymous'
        hint.save()
        messages.success(request, 'You have claimed this hint!')

    limit = request.META.get('QUERY_STRING', '')
    limit = int(limit) if limit.isdigit() else 20
    previous = (
        Hint.objects
        .select_related()
        .filter(puzzle=hint.puzzle, status=Hint.ANSWERED)
        .order_by('-answered_datetime')
    )[:limit]
    request.context.puzzle = hint.puzzle
    return render(request, 'hint.html', {
        'hint': hint,
        'previous': previous,
        'form': form,
    })


@require_GET
@restrict_access(after_hunt_end=True)
def hunt_stats(request):
    '''After hunt ends, view stats for the entire hunt.'''

    total_teams = Team.objects.exclude(is_hidden=True).count()
    total_participants = TeamMember.objects.exclude(team__is_hidden=True).count()

    def is_forward_solve(puzzle, team_id):
        return puzzle.is_meta or all(
            solve_times[puzzle.id, team_id] <=
            solve_times[meta.id, team_id] - datetime.timedelta(minutes=5)
            for meta in puzzle.metas.all()
        )

    total_hints = 0
    hints_by_puzzle = defaultdict(int)
    hint_counts = defaultdict(int)
    for hint in Hint.objects.exclude(team__is_hidden=True):
        total_hints += 1
        hints_by_puzzle[hint.puzzle_id] += 1
        if hint.status != Hint.OBSOLETE:
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
@restrict_access(after_hunt_end=True)
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
@restrict_access(after_hunt_end=True)
def solution(request):
    '''After hunt ends, view a puzzle's solution.'''

    template_name = 'solution_bodies/{}'.format(request.context.puzzle.body_template)
    data = {'template_name': template_name}
    try:
        return render(request, template_name, data)
    except TemplateDoesNotExist:
        return render(request, 'solution.html', data)


@require_GET
@restrict_access(after_hunt_end=True)
def solution_static(request, path):
    return serve(request, path, document_root=settings.SOLUTION_STATIC_ROOT)


@require_GET
def story(request):
    '''View your team's story page based on your current progress.'''

    # FIXME: This will depend a lot on your hunt. It might not make any sense
    # at all.
    if not STORY_PAGE_VISIBLE:
        raise Http404
    story_points = {
        'show_prehunt': STORY_PAGE_VISIBLE,
        'show_started': False,
        'meta0_open': False, 'meta0_done': False,
        'meta1_open': False, 'meta1_done': False,
    }
    if request.context.hunt_has_started:
        story_points['show_started'] = True
        metas = [INTRO_META_SLUG, META_META_SLUG]
        team = request.context.team
        for data in request.context.unlocks['puzzles']:
            slug = data['puzzle'].slug
            if slug in metas:
                story_points['meta%d_open' % metas.index(slug)] = True
        if team:
            for submission in team.submissions:
                slug = submission.puzzle.slug
                if submission.is_correct and slug in metas:
                    story_points['meta%d_done' % metas.index(slug)] = True
    return render(request, 'story.html', story_points)


@require_GET
def victory(request):
    '''View your team's victory page, if you've finished the hunt.'''

    team = request.context.team
    if request.context.hunt_is_over:
        return render(request, 'victory.html', {'hunt_finished': True})
    if not team or not request.context.hunt_has_started:
        raise Http404
    solved_metameta = any(
        submission.puzzle.slug == META_META_SLUG and submission.is_correct
        for submission in team.submissions
    )
    if solved_metameta:
        dispatch_victory_alert(
            'Team %s has finished the hunt!' % team +
            '\n**Emails:** ' + request.build_absolute_uri(reverse('finishers')))
    return render(request, 'victory.html', {
        'hunt_finished': request.context.is_superuser or solved_metameta,
    })


@require_GET
def errata(request):
    if not ERRATA_PAGE_VISIBLE:
        raise Http404
    return render(request, 'errata.html')


@require_GET
def wrapup(request):
    if not WRAPUP_PAGE_VISIBLE:
        raise Http404
    return render(request, 'wrapup.html')


@require_GET
@restrict_access(after_hunt_end=True)
def finishers(request):
    teams = OrderedDict()
    solves_by_team = defaultdict(list)
    metas_by_team = defaultdict(list)
    unlock_times = defaultdict(lambda: HUNT_END_TIME)
    wrong_times = {}

    for submission in (
        AnswerSubmission.objects
        .filter(puzzle__slug=META_META_SLUG, team__is_hidden=False, submitted_datetime__lt=HUNT_END_TIME)
        .order_by('submitted_datetime')
    ):
        if submission.is_correct:
            teams[submission.team_id] = None
        else:
            wrong_times[submission.team_id] = submission.submitted_datetime
    for unlock in (
        PuzzleUnlock.objects
        .filter(team__id__in=teams, puzzle__slug=META_META_SLUG)
    ):
        unlock_times[unlock.team_id] = unlock.unlock_datetime
    for solve in (
        AnswerSubmission.objects
        .select_related()
        .filter(team__id__in=teams, used_free_answer=False, is_correct=True, submitted_datetime__lt=HUNT_END_TIME)
    ):
        solves_by_team[solve.team_id].append(solve.submitted_datetime)
        if solve.puzzle.is_meta:
            metas_by_team[solve.team_id].append(solve.submitted_datetime)
        if solve.puzzle.slug == META_META_SLUG:
            teams[solve.team_id] = (solve.team, unlock_times[solve.team_id])

    data = []
    for team_id, (team, unlock) in teams.items():
        solves = [HUNT_START_TIME] + solves_by_team[team_id] + [HUNT_END_TIME]
        solves = [{
            'before': (solves[i - 1] - HUNT_START_TIME).total_seconds(),
            'after': (solves[i] - HUNT_START_TIME).total_seconds(),
        } for i in range(1, len(solves))]
        metas = metas_by_team[team_id]
        data.append({
            'team': team,
            'mm1_time': unlock,
            'mm2_time': metas[-1],
            'duration': (metas[-1] - unlock).total_seconds(),
            'wrong_duration':
                (metas[-1] - wrong_times[team_id])
                .total_seconds() if team_id in wrong_times else None,
            'hunt_length': (HUNT_END_TIME - HUNT_START_TIME).total_seconds(),
            'solves': solves,
            'metas': [(ts - HUNT_START_TIME).total_seconds() for ts in metas],
        })
    if request.context.is_superuser:
        data.reverse()
    return render(request, 'finishers.html', {'data': data})


@require_GET
@restrict_access(after_hunt_end=True)
def bigboard(request):
    puzzles = request.context.all_puzzles
    puzzle_map = {}
    puzzle_metas = defaultdict(set)
    intro_meta_id = None
    meta_meta_id = None
    for puzzle in puzzles:
        puzzle_map[puzzle.id] = puzzle
        if puzzle.slug == INTRO_META_SLUG:
            intro_meta_id = puzzle.id
        if puzzle.slug == META_META_SLUG:
            meta_meta_id = puzzle.id
        if not puzzle.is_meta:
            for meta in puzzle.metas.all():
                puzzle_metas[puzzle.id].add(meta.id)

    wrong_guesses_map = defaultdict(int) # key (team, puzzle)
    wrong_guesses_by_team_map = defaultdict(int) # key team
    solve_position_map = dict() # key (team, puzzle); value n if team is nth to solve this puzzle
    solve_count_map = defaultdict(int) # puzzle -> number of counts
    total_guess_map = defaultdict(int) # puzzle -> number of guesses
    used_hints_map = defaultdict(int) # (team, puzzle) -> number of hints
    used_hints_by_team_map = defaultdict(int) # team -> number of hints
    used_hints_by_puzzle_map = defaultdict(int) # puzzle -> number of hints
    solves_map = defaultdict(dict) # team -> {puzzle id -> puzzle}
    intro_solves_map = defaultdict(int) # team -> number of puzzle solves
    jungle_solves_map = defaultdict(int) # team -> number of puzzle solves
    meta_solves_map = defaultdict(int) # team -> number of meta solves
    solve_time_map = defaultdict(dict) # team -> {puzzle id -> solve time}
    during_hunt_solve_time_map = defaultdict(dict) # team -> {puzzle id -> solve time}
    free_answer_map = defaultdict(set) # team -> {puzzle id}
    free_answer_by_puzzle_map = defaultdict(int) # puzzle -> number of free answers

    for team_id, puzzle_id, used_free_answer, submitted_datetime in (
        AnswerSubmission.objects
        .filter(team__is_hidden=False, is_correct=True)
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
        elif intro_meta_id in puzzle_metas[puzzle_id]:
            intro_solves_map[team_id] += 1
        else:
            jungle_solves_map[team_id] += 1

    for aggregate in (
        AnswerSubmission.objects
        .filter(team__is_hidden=False, is_correct=False)
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
        .filter(status=Hint.ANSWERED)
        .values('team_id', 'puzzle_id')
        .annotate(count=Count('*'))
    ):
        team_id = aggregate['team_id']
        puzzle_id = aggregate['puzzle_id']
        used_hints_map[(team_id, puzzle_id)] += aggregate['count']
        used_hints_by_team_map[team_id] += aggregate['count']
        used_hints_by_puzzle_map[puzzle_id] += aggregate['count']

    # Reproduce Team.leaderboard behavior for ignoring solves after hunt end,
    # but not _teams_ created after hunt end. They'll just all be at the bottom.
    leaderboard = sorted(Team.objects.filter(is_hidden=False), key=lambda team: (
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
        if solve_time and puzzle_metas.get(puzzle_id):
            metas_before = 0
            metas_after = 0
            for meta_id in puzzle_metas[puzzle_id]:
                meta_time = solve_time_map[team_id].get(meta_id)
                if meta_time and solve_time > meta_time - datetime.timedelta(minutes=5):
                    metas_before += 1
                else:
                    metas_after += 1
            if metas_after == 0:
                yield 'B' # backsolved from all metas
            elif metas_before != 0:
                yield 'b' # backsolved from some metas

    board = []
    for team in leaderboard:
        team.solves = solves_map[team.id]
        board.append({
            'team': team,
            'last_solve_time': max([team.creation_time, *solve_time_map[team.id].values()]),
            'total_solves': len(solve_time_map[team.id]),
            'free_solves': len(free_answer_map[team.id]),
            'wrong_guesses': wrong_guesses_by_team_map[team.id],
            'used_hints': used_hints_by_team_map[team.id],
            'total_hints': team.num_hints_total,
            'finished': solve_position_map.get((team.id, meta_meta_id)),
            'deep': team.display_deep,
            'intro_solves': intro_solves_map[team.id],
            'jungle_solves': jungle_solves_map[team.id],
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
@restrict_access(after_hunt_end=True)
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
@restrict_access()
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
@restrict_access()
def puzzle_log(request):
    return serve(request, os.path.join(settings.BASE_DIR,
        settings.LOGGING['handlers']['puzzle']['filename']), document_root='/')


@require_POST
@restrict_access()
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
    response.write('User-agent: *\nDisallow: /\n')
    return response
