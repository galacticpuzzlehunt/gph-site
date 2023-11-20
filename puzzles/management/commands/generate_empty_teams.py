# Note: for simplicity, we don't try to check uniqueness constraints when
# randomly generating stuff. If we get unlucky and generate something
# non-unique, just try again.
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from puzzles.models import Team, Puzzle, AnswerSubmission, Survey
from puzzles.hunt_config import HUNT_START_TIME
from unittest import mock
import random

# for flavor, and to test unicode // http://racepics.weihwa.com/
emoji = "💥💫🐒🦍🐕🐺🦊🐈🦁🐅🐆🐎🦄🦌🐂🐃🐄🐖🐗🐏🐑🐐🐪🐘🦏🐁🐀🐹🐇🐿🦇🐻🐨🐼🐾🦃🐔🐓🐤🐦🐧🕊🦅🦆🦉🐸🐊🐢🦎🐍🐉🐳🐋🐬🐟🐠🐡🦈🐙🐚🐌🦋🐛🐜🐝🐞🕷🕸🦂💐🌸💮🌹🌺🌻🌼🌷🌱🌲🌳🌴🌵🌾🌿☘🍀🍁🍃🍄🌰🦀🦐🦑🌐🌙⭐🌈⚡🔥🌊✨🎮🎲🧩♟🎭🎨🧵🎤🎧🎷🎸🎹🎺🎻🥁🎬🏹🌋🏖🏜🏝🏠🏤🏥🏦🏫🌃🏙🌅🌇🚆🚌🚕🚗🚲⚓✈🚁🚀🛸🎆"
adjectives = "Alien Alpha Aquatic Avian Bio-Hazard Blaster Comet Contact Deep-Space Deficit Deserted Destroyed Distant Empath Epsilon Expanding Expedition Galactic Gambling Gem Genetics Interstellar Lost Malevolent Military Mining Mining New Old Outlaw Pan-Galactic Pilgrimage Pirate Plague Pre-Sentient Prosperous Public Radioactive Rebel Replicant Reptilian Research Scout Terraformed Terraforming Uplift".split()
nouns = "Alliance Bankers Base Battle Bazaar Cache Center Code Colony Consortium Developers Earth Economy Engineers Exchange Factory Federation Fleet Fortress Guild Imperium Institute Lab Lair League Lifeforms Mercenaries Monolith Order Outpost Pact Port Program Project Prospectors Renaissance Repository Resort Robots Shop Sparta Stronghold Studios Survey Symbionts Sympathizers Technology Trendsetters Troops Warlord Warship World".split()

def random_team_name(name_prefix):
    return "{} {}{}{} {} {} {}{}{}".format(
        name_prefix,
        random.choice(emoji),
        random.choice(emoji),
        random.choice(emoji),
        random.choice(adjectives),
        random.choice(nouns),
        random.choice(emoji),
        random.choice(emoji),
        random.choice(emoji),
    )

class Command(BaseCommand):
    help = 'Generate teams with empty progress.'

    def add_arguments(self, parser):
        parser.add_argument('num_teams', nargs=1, type=int)
        parser.add_argument('username_prefix', nargs=1, type=str)
        parser.add_argument('name_prefix', nargs=1, type=str)
        parser.add_argument(
            "-y",
            action="store_true",
            help="Automatically input \"yes\" to all confirmation prompts",
        )

    def handle(self, *args, **options):
        n = options['num_teams'][0]
        username_prefix = options['username_prefix'][0]
        name_prefix = options['name_prefix'][0]
        teams = []
        existing_users = User.objects.all().filter(username__startswith=username_prefix)
        existing_teams = Team.objects.all().filter(user__username__startswith=username_prefix)
        self.stdout.write(self.style.ERROR('These will be deleted:'))
        self.stdout.write(self.style.WARNING('%d %s' % (existing_users.count(), 'users')))
        self.stdout.write(self.style.WARNING('%d %s' % (existing_teams.count(), 'teams')))
        if not options["y"]:
            input(self.style.ERROR('Enter to continue: '))
        existing_teams.delete()
        existing_users.delete()

        for i in range(n):
            username = '{}_{}'.format(username_prefix, i)

            user = User.objects.create_user(
                username=username, password="pw"
            )
            team = Team(
                user=user,
                team_name=random_team_name(name_prefix),
                creation_time=datetime.now(),
            )
            team.save()
            teams.append(team)

        self.stdout.write(self.style.SUCCESS('Generated {} teams'.format(n)))
