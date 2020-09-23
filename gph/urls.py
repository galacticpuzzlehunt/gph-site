'''gph URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
'''

from urllib.parse import quote_plus, unquote_plus

from django.conf import settings
from django.urls import path, re_path, include, register_converter
from django.contrib import admin
from django.contrib.auth import views as auth_views

import puzzles.views as views
import puzzles.puzzlehandlers as puzzlehandlers

class QuotedStringConverter:
    regex = '[^/]+'

    def to_python(self, value):
        return unquote_plus(value)

    def to_url(self, value):
        return quote_plus(value, safe='')

register_converter(QuotedStringConverter, 'quotedstr')

urlpatterns = [
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^impersonate/', include('impersonate.urls')),

    path('', views.index, name='index'),

    path('rules', views.rules, name='rules'),
    path('faq', views.faq, name='faq'),
    path('archive', views.archive, name='archive'),
    path('register', views.register, name='register'),

    path('login',
        auth_views.LoginView.as_view(template_name='login.html'),
        name='login'),
    path('logout', auth_views.LogoutView.as_view(), name='logout'),
    path('password-change', views.password_change, name='password_change'),
    path('password-change-done',
        auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'),
        name='password_change_done'),
    path('password-reset', views.password_reset, name='password_reset'),
    path('password-reset-done',
        auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
        name='password_reset_done'),
    re_path(r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,32})/$',
        auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),
        name='password_reset_confirm'),
    path('reset/done',
        auth_views.PasswordResetCompleteView.as_view(template_name='password_change_done.html'),
        name='password_reset_complete'),

    path('teams', views.teams, name='teams'),
    path('team/<quotedstr:team_name>', views.team, name='team'),
    path('teams/unhidden', views.teams_unhidden, name='teams-unhidden'),
    path('teams/high-school', views.teams_high_school, name='teams-high-school'),
    path('teams/middle-school', views.teams_middle_school, name='teams-middle-school'),
    path('edit-team', views.edit_team, name='edit-team'),

    path('puzzles', views.puzzles, name='puzzles'),
    path('puzzle/<slug:slug>', views.puzzle, name='puzzle'),
    path('solve/<slug:slug>', views.solve, name='solve'),
    path('free-answer/<slug:slug>', views.free_answer, name='free-answer'),
    path('post-hunt-solve/<slug:slug>', views.post_hunt_solve, name='post-hunt-solve'),
    path('survey/<slug:slug>', views.survey, name='survey'),
    path('hints', views.hint_list, name='hint-list'),
    path('hints/<slug:slug>', views.hints, name='hints'),
    path('hint/<int:id>', views.hint, name='hint'),
    path('stats', views.hunt_stats, name='hunt-stats'),
    path('stats/<slug:slug>', views.stats, name='stats'),
    path('solution/<slug:slug>', views.solution, name='solution'),
    path('solution/<path:path>', views.solution_static, name='solution-static'),

    path('story', views.story, name='story'),
    path('victory', views.victory, name='victory'),
    path('errata', views.errata, name='errata'),
    path('wrapup', views.wrapup, name='wrapup'),
    path('wrapup/finishers', views.finishers, name='finishers'),

    path('bridge', views.bridge, name='bridge'),
    path('bigboard', views.bigboard, name='bigboard'),
    path('bigboard/unhidden', views.bigboard_unhidden, name='bigboard-unhidden'),
    path('bridge/guess.csv', views.guess_csv, name='guess-csv'),
    path('bridge/hint.csv', views.hint_csv, name='hint-csv'),
    path('bridge/puzzle.log', views.puzzle_log, name='puzzle-log'),
    path('shortcuts', views.shortcuts, name='shortcuts'),
]

if settings.DEBUG:
    urlpatterns.append(path('robots.txt', views.robots))
