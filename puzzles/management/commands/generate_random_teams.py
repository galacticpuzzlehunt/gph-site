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
wrong_answers = [x + y for x in ["RED", "WRONG", "INCORRECT"] for y in ["", "ANSWER", "SOLUTION", "HERRING"]]

def random_team_name():
    return "{}{}{} {} {} {}{}{}".format(
        random.choice(emoji),
        random.choice(emoji),
        random.choice(emoji),
        random.choice(adjectives),
        random.choice(nouns),
        random.choice(emoji),
        random.choice(emoji),
        random.choice(emoji),
    )

def random_datetime_since(start):
    now = timezone.make_aware(datetime.now())
    if start > now: return now

    delta = now - start
    ret = start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))
    print(start, now, delta, ret)
    return ret

class Command(BaseCommand):
    help = 'Randomly generate n teams for testing, complete with solves and surveys'

    def add_arguments(self, parser):
        parser.add_argument('num_teams', nargs=1, type=int)

    def handle(self, *args, **options):
        # Annotate every puzzle and every team with a rating to get a more
        # interesting and realistic scoreboard, where there are trends across
        # teams and puzzles.
        puzzles = [(p, random.random()) for p in Puzzle.objects.all()]
        n = options['num_teams'][0]
        teams = []
        for i in range(n):
            username = 'team{}'.format(random.randint(0,10**10))

            user = User.objects.create_user(
                username=username, email=username + "@example.com", password="password"
            )
            with mock.patch("django.utils.timezone.now") as mock_now:
                mock_now.return_value = random_datetime_since(HUNT_START_TIME)
                team = Team(
                    user=user,
                    team_name=random_team_name(),
                    creation_time=random_datetime_since(HUNT_START_TIME),
                )
                team.save()
            # Teams have a wider range of skill than puzzles.
            teams.append((team, random.random() * 2 + 0.05))

        for puzzle, puzzle_rating in puzzles:
            # Shuffle every time so puzzles don't all get solved by teams in a
            # consistent order and the bigboard looks nontrivial.
            random.shuffle(teams)
            for team, team_rating in teams:
                success_prob = team_rating - puzzle_rating

                if success_prob < 0: continue

                cur_time = team.creation_time

                for i in range(random.randint(0, 10)):
                    if random.random() < success_prob:
                        break
                    cur_time = random_datetime_since(cur_time)
                    with mock.patch("django.utils.timezone.now") as mock_now:
                        mock_now.return_value = cur_time
                        AnswerSubmission(
                            team=team,
                            puzzle=puzzle,
                            submitted_answer=wrong_answers[i],
                            is_correct=False,
                            used_free_answer=False,
                        ).save()

                if random.random() < success_prob:
                    cur_time = random_datetime_since(cur_time)
                    with mock.patch("django.utils.timezone.now") as mock_now:
                        mock_now.return_value = cur_time
                        AnswerSubmission(
                            team=team,
                            puzzle=puzzle,
                            submitted_answer=puzzle.normalized_answer,
                            is_correct=True,
                            used_free_answer=False,
                            submitted_datetime=cur_time,
                        ).save()

                        if random.random() < 0.75:
                            Survey(
                                team=team,
                                puzzle=puzzle,
                                fun=random.randint(1, 6),
                                difficulty=random.randint(1, 6),
                            ).save()

        self.stdout.write(self.style.SUCCESS('Randomly generated {} teams'.format(n)))
