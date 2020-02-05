from django.core.management.base import BaseCommand
from puzzles.models import Team

class Command(BaseCommand):
    help = 'Awards all teams a certain number of hints'

    def add_arguments(self, parser):
        parser.add_argument('num_hints', nargs=1, type=int)

    def handle(self, *args, **options):
        teams = Team.objects.all()
        for team in teams:
            team.total_hints_awarded += options['num_hints'][0]
            team.save()
        self.stdout.write(self.style.SUCCESS('Successfully awarded hints'))