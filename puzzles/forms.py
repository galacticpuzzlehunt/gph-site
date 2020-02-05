from django import forms
from django.contrib.auth.models import User
from django.core.validators import validate_email

from puzzles.models import (
    Team,
    TeamMember,
    Survey,
    Hint,
)


class RegisterForm(forms.Form):
    team_id = forms.CharField(
        label='Team Username',
        max_length=100,
        help_text=(
            'This is the private username your team will use when logging in. '
            'It should be short and not contain special characters.'
        ),
    )
    team_name = forms.CharField(
        label='Team Name',
        max_length=200,
        help_text=(
            'This is how your team name will appear on the public leaderboard.'
        ),
    )
    password = forms.CharField(
        label='Team Password',
        widget=forms.PasswordInput,
        help_text='You\u2019ll probably share this with your team.',
    )
    password2 = forms.CharField(
        label='Retype Password',
        widget=forms.PasswordInput,
    )

    def clean(self):
        cleaned_data = super(RegisterForm, self).clean()
        team_id = cleaned_data.get('team_id')
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')
        team_name = cleaned_data.get('team_name')

        if password != password2:
            raise forms.ValidationError(
                'Passwords don\u2019t match.'
            )

        if User.objects.filter(username=team_id).exists():
            raise forms.ValidationError(
                'That login username has already been taken by a different '
                'team.'
            )

        if Team.objects.filter(team_name=team_name).exists():
            raise forms.ValidationError(
                'That public team name has already been taken by a different '
                'team.'
            )

        return cleaned_data


def validate_team_member_email_unique(email):
    if TeamMember.objects.filter(email=email).exists():
        raise forms.ValidationError(
            'Someone with that email is already registered as a member on a '
            'different team.'
        )

class TeamMemberForm(forms.Form):
    name = forms.CharField(label='Name (required)', max_length=200)
    email = forms.EmailField(
        label='Email (optional)',
        max_length=200,
        required=False,
        validators=[validate_email, validate_team_member_email_unique],
    )


def validate_team_emails(formset):
    emails = []
    for form in formset.forms:
        if not form.cleaned_data.get('name'):
            raise forms.ValidationError('All team members must have names.')
        email = form.cleaned_data.get('email')
        if email:
            emails.append(email)
    if not emails:
        raise forms.ValidationError('You must list at least one email address.')
    if len(emails) != len(set(emails)):
        raise forms.ValidationError('All team members must have unique emails.')
    return emails

class TeamMemberFormset(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        validate_team_emails(self)

class TeamMemberModelFormset(forms.models.BaseModelFormSet):
    def clean(self):
        if any(self.errors):
            return
        emails = validate_team_emails(self)
        if (
            TeamMember.objects
            .exclude(team=self.data['team'])
            .filter(email__in=emails)
            .exists()
        ):
            raise forms.ValidationError(
                'One of the emails you listed is already on a different team.'
            )


class SubmitAnswerForm(forms.Form):
    answer = forms.CharField(
        label='Enter your guess:',
        max_length=500,
    )


class RequestHintForm(forms.Form):
    hint_question = forms.CharField(
        label=(
            'Describe everything you\u2019ve tried on this puzzle. We will '
            'provide a hint to help you move forward. The more detail you '
            'provide, the less likely it is that we\u2019ll tell you '
            'something you already know.'
        ),
        widget=forms.Textarea,
    )

    def __init__(self, team, *args, **kwargs):
        super(RequestHintForm, self).__init__(*args, **kwargs)
        notif_choices = [('all', 'Everyone'), ('none', 'No one')]
        notif_choices.extend(team.get_emails(with_names=True))
        self.fields['notify_emails'] = forms.ChoiceField(
            label='When the hint is answered, send an email to:',
            choices=notif_choices
        )


class AnswerHintForm(forms.ModelForm):
    class Meta:
        model = Hint
        fields = ['response', 'status']


class SurveyForm(forms.ModelForm):
    class Meta:
        model = Survey
        exclude = ['team', 'puzzle']


# This form is a customization of forms.PasswordResetForm
class PasswordResetForm(forms.Form):
    team_id = forms.CharField(label='Team Username', max_length=100)

    def clean(self):
        cleaned_data = super(PasswordResetForm, self).clean()
        team_id = cleaned_data.get('team_id')
        team = Team.objects.filter(user__username=team_id).first()
        if team is None:
            raise forms.ValidationError('That username doesn\u2019t exist.')
        cleaned_data['team'] = team
        return cleaned_data
