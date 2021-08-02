from django.core.management.base import BaseCommand
from django.utils.text import slugify
import puzzles.models as models

tables = (
    models.Round,
    models.Puzzle,
    models.PuzzleUnlock,
    models.AnswerSubmission,
    models.ExtraGuessGrant,
    models.PuzzleMessage,
    models.Erratum,
    models.Survey,
    models.Hint,
)

class Command(BaseCommand):
    help = 'Create rounds and puzzles from a TSV'

    def add_arguments(self, parser):
        parser.add_argument('filename', nargs=1, type=str)

    def handle(self, *args, **options):
        self.stdout.write(self.style.ERROR('These will be deleted:'))
        for model in tables:
            self.stdout.write(self.style.WARNING('%d %s' %
                (model.objects.count(), model.__name__)))
        input(self.style.ERROR('Enter to continue: '))
        for model in tables:
            model.objects.all().delete()

        round_counter = 0
        puzzle_counter = 0
        round = None
        for line in open(options['filename'][0]):
            (round_title, title, slug, emoji, answer, unlock_hours,
                unlock_global, unlock_local) = line.strip('\n').split('\t')[:8]
            if round_title:
                round_counter += 1
                puzzle_counter = 0
                round = models.Round(
                    name=round_title,
                    slug=slugify(round_title),
                    order=round_counter,
                )
                round.save()
            is_meta = title.endswith(' (Meta)')
            title = title.replace(' (Meta)', '')
            puzzle_counter += 1
            puzzle = models.Puzzle(
                name=title,
                slug=slug,
                answer=answer or 'TESTING',
                round=round,
                order=puzzle_counter,
                is_meta=is_meta,
                emoji=emoji or ':question:',
            )
            if unlock_hours: puzzle.unlock_hours = int(unlock_hours)
            if unlock_global: puzzle.unlock_global = int(unlock_global)
            if unlock_local: puzzle.unlock_local = int(unlock_local)
            puzzle.clean()
            puzzle.save()
            if is_meta:
                round.meta = puzzle
                round.save()
            self.stdout.write(self.style.SUCCESS('Imported %s' % puzzle))
