# Note: for simplicity, we don't try to check uniqueness constraints when
# randomly generating stuff. If we get unlucky and generate something
# non-unique, just try again.
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from datetime import datetime
from puzzles.models import Puzzle, Round
import random

# random "green paint" answers // many words from https://github.com/glitchdotcom/friendly-words
adjectives = "AERIAL ALPINE AMAZING AMBER AWESOME BEST BIG BLUE BRAVE BRIGHT CALM CHILL CLEAN CLEAR COLD COMMON COOL COSMIC CRIMSON CRYSTAL CUTE CYAN CYCLIC DAPPER DARK EAGER ELITE FAIR FANTASY FAST FIRE FLAME FLYING FREE FRESH FURRY FUTURE GIANT GOLD GOOD GRAY GREAT GREEN HAPPY HEAVY HONEY HOT HYPER ICY INDIGO LARGE LEMON LIME LUCKY MAGENTA MAGICAL MELLOW MIGHTY MIRROR MODERN NAVY NEAT NICE NOISY OPAQUE ORANGE PACIFIC PERIDOT PLAIN PURPLE QUICK RAPID RED RIGHT ROBUST ROUND SHARP SHORT SILICON SMALL SMART SOFT SOLAR SOLID SPIRAL SUNNY SUPER SWEET SWIFT TIDAL TIN TINY TOPAZ TOUGH ULTRA VIOLET VIVID WATER WILD YELLOW ZANY".split()
nouns = "ACORN ANIMAL ANT APPLE ARROW BADGE BAG BAGEL BANK BASIL BASIN BAT BEAR BEARD BEAST BED BEE BIRD BOA BOAR BOAT BONE BOOK BOOT BOW BOWL BOX BREAD BUG BUS CABIN CAKE CAMP CANDY CAR CARD CARP CAT CHIP CITY CORK COW CROW CUP DEER DINGO DOG DOLL DONUT DRAGON DUCK EAGLE EARTH EEL EGG EMU FAIRY FEAST FISH FLY FOX FRUIT GEM GERBIL GOAT GOOSE GOPHER GRAPE GROUSE HERO HORSE HYENA ICE LAKE LAMB LAMP LAND LEAF LEMON LOCK LOG MANGO MARTEN MASK MEADOW MELON METEOR MOLE MOON MOTH MULE NEST ONION OWL OX OYSTER PAINT PAPER PARROT PASTRY PEAR PEARL PHONE PIANO PICKLE PIGEON PILLOW PILOT PLANE PLUM POET PONY POTATO PUPPY QUARK RABBIT RAVEN ROBIN ROCK ROCKET SEAL SHADOW SHARK SHIELD SHIP SHOVEL SNAKE SOCK SPHERE TURTLE WALRUS WHALE WIZARD WOLF ZEBRA".split()

answerphrases = [
    "9 out of 10 Doctors Say It's {}",
    "Answer {}",
    "Answer's {}",
    "Call In {}",
    "Guess {}",
    "Have You Tried Submitting {}?",
    "It's {}",
    "Just Submit {} Already",
    "Puzzle with the Answer {}",
    "Solution {}",
    "Submit {}",
    "The Answer Is {}",
    "The Answer to This Puzzle Is {}",
    "The Solution Is {}",
    "{} Is It",
    "{} Is the Answer",
    "{} Is the Solution",
]

def random_answer():
    return "{} {}".format(random.choice(adjectives), random.choice(nouns))

class Command(BaseCommand):
    help = 'Randomly generate n puzzles for testing'

    def add_arguments(self, parser):
        parser.add_argument('num_puzzles', nargs=1, type=int)

    def handle(self, *args, **options):
        n = options['num_puzzles'][0]
        limit = 0
        round_order = 0

        for i in range(n):
            if i == limit:
                title = 'Intro' if i == 0 else random.choice(nouns).title()
                slug = slugify(title)
                round_order += 1
                puzzle_order = 0
                limit += random.randint(4, 10)

                round = Round(
                    name=title,
                    slug=slug,
                    order=round_order,
                )
                round.save()

            answer = random_answer()
            title = random.choice(answerphrases).format(answer)
            slug = slugify(title)
            puzzle_order += 1

            Puzzle(
                name=title,
                slug=slug,
                body_template=slug + '.html',
                answer=answer,
                round=round,
                order=puzzle_order,
            ).save()

        self.stdout.write(self.style.SUCCESS('Randomly generated {} puzzles'.format(n)))
