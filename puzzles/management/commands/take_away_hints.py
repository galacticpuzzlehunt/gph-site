from django.core.management.base import BaseCommand
from puzzles.models import Team, Hint

class Command(BaseCommand):
    help = 'Takes away all unused hints from teams'

    def handle(self, *args, **options):
        teams = Team.objects.all()
        for team in teams:
            team.total_hints_awarded -= team.num_awarded_hints_remaining
            team.save()
        self.stdout.write(self.style.SUCCESS('Successfully taken away hints'))
