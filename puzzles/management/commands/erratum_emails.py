from django.core.management.base import BaseCommand
from puzzles.models import PuzzleUnlock, TeamMember

class Command(BaseCommand):
    help = 'List all email addresses of players on teams that have unlocked a certain puzzle'

    def add_arguments(self, parser):
        parser.add_argument('puzzle_slug', nargs=1, type=str)

    def handle(self, *args, **options):
        slug = options['puzzle_slug'][0]
        self.stdout.write('Getting email addresses for puzzle {}...\n\n'.format(slug))
        teams = PuzzleUnlock.objects.filter(puzzle__slug=slug).values_list('team_id', flat=True)
        members = TeamMember.objects.filter(team_id__in=teams).exclude(email='').values_list('email', flat=True)
        if members:
            self.stdout.write(', '.join(members))
            self.stdout.write(self.style.SUCCESS('\nFound {} team members.'.format(len(members))))
        else:
            self.stdout.write(self.style.ERROR('Found nothing.'))
