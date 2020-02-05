from django.core.management.base import BaseCommand
from puzzles.models import PuzzleUnlock, Team, TeamMember

class Command(BaseCommand):
    help = 'List all email addresses of players on teams that have unlocked a certain puzzle'

    def add_arguments(self, parser):
        parser.add_argument('puzzle_slug', nargs=1, type=str)

    def handle(self, *args, **options):
        slug = options['puzzle_slug'][0]
        self.stdout.write('Getting email addresses for puzzle {}...\n\n'.format(slug))
        unlocks = PuzzleUnlock.objects.filter(puzzle__slug=slug)#.select_related("team")
        members = []
        teams = [x.team for x in unlocks]
        for team in teams:
            for member in TeamMember.objects.filter(team=team):
                members.append(member.email)
        if len(members) > 0:
            self.stdout.write(', '.join(members))
            self.stdout.write(self.style.SUCCESS('\n\nFound {} team members.'.format(len(members))))
        else:
            self.stdout.write(self.style.FAILURE('Found {} team members.'.format(len(members))))
