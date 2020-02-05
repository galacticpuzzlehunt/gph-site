from django.contrib import admin
from django import forms

from puzzles.models import (
    Puzzle,
    Team,
    TeamMember,
    PuzzleUnlock,
    AnswerSubmission,
    ExtraGuessGrant,
    PuzzleMessage,
    Survey,
    Hint,
)

class PuzzleMessageInline(admin.TabularInline):
    model = PuzzleMessage

class PuzzleAdmin(admin.ModelAdmin):
    inlines = [PuzzleMessageInline]
    ordering = ('deep', 'name')
    list_display = ('name', 'slug', 'deep', 'emoji', 'is_meta')
    list_filter = ('is_meta',)

class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'team')
    list_filter = ('team',)
    search_fields = ('name', 'email')

class TeamMemberInline(admin.TabularInline):
    model = TeamMember

class TeamAdmin(admin.ModelAdmin):
    inlines = [TeamMemberInline]
    list_display = ('team_name', 'creation_time', 'is_hidden')
    list_filter = ('is_prerelease_testsolver', 'is_hidden')
    search_fields = ('team_name',)

class PuzzleUnlockAdmin(admin.ModelAdmin):
    list_display = ('team', 'puzzle', 'unlock_datetime')
    list_filter = ('puzzle', 'team')

class AnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = ('team', 'puzzle', 'submitted_answer', 'submitted_datetime', 'is_correct', 'used_free_answer')
    list_filter = ('is_correct', 'used_free_answer', 'puzzle', 'team')
    search_fields = ('submitted_answer',)

class ExtraGuessGrantAdmin(admin.ModelAdmin):
    list_display = ('team', 'puzzle', 'extra_guesses')
    list_filter = ('puzzle', 'team')

class SurveyAdmin(admin.ModelAdmin):
    list_display = ('team', 'puzzle')
    list_filter = ('puzzle', 'team')
    search_fields = ('comments',)

class HintAdmin(admin.ModelAdmin):
    list_display = ('team', 'puzzle', 'submitted_datetime', 'claimer', 'claimed_datetime', 'status', 'answered_datetime')
    list_filter = ('status', 'claimed_datetime', 'answered_datetime', 'puzzle', 'team', 'claimer')
    search_fields = ('hint_question', 'response')

admin.site.register(Puzzle, PuzzleAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(TeamMember, TeamMemberAdmin)
admin.site.register(PuzzleUnlock, PuzzleUnlockAdmin)
admin.site.register(AnswerSubmission, AnswerSubmissionAdmin)
admin.site.register(ExtraGuessGrant, ExtraGuessGrantAdmin)
admin.site.register(Survey, SurveyAdmin)
admin.site.register(Hint, HintAdmin)
