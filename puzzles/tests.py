import logging
from datetime import datetime

import django.urls as urls
from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import Puzzle, Round, Team, AnswerSubmission

# wow, we log a lot of things as INFO
logging.disable(logging.INFO)

def create_user(name):
    return User.objects.create_user(
        username=name, email=name + "@example.com", password=name + "secret"
    )


class Misc(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="a", email="a@example.com", password="secret"
        )
        self.user_b = User.objects.create_user(
            username="b", email="b@example.com", password="password"
        )
        self.team_a = Team(
            user=self.user_a,
            team_name="Team A",
            creation_time=datetime.fromtimestamp(0),
        )
        self.team_a.save()
        self.team_b = Team(
            user=self.user_b,
            team_name="Team 🐉 B+B/B <script>&mdash;",
            creation_time=datetime.fromtimestamp(0),
            is_prerelease_testsolver=True,
        )
        self.team_b.save()

        self.sample_round = Round(
            name="Sample Round",
            slug="sample",
        )
        self.sample_round.save()
        self.sample_puzzle = Puzzle(
            name="Sample",
            slug="sample",
            body_template="sample.html",
            answer="SAMPLE ANSWER",
            round=self.sample_round,
            unlock_global=0,
        )
        self.sample_puzzle.save()
        self.sample_puzzle_2 = Puzzle(
            name="Sample II",
            slug="sample-ii",
            body_template="sample.html",
            answer="SAMPLE",
            round=self.sample_round,
            unlock_global=1000,
        )
        self.sample_puzzle_2.save()

    def test_index(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("index"))
        self.assertEqual(response.status_code, 200)

    def test_teams(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("teams"))
        self.assertEqual(response.status_code, 200)

    def test_puzzles(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("round", args=(self.sample_round.slug,)))
        self.assertEqual(response.status_code, 200)

        puzzles = response.context[0]['round']['puzzles']
        # self.assertEqual(len(puzzles), 1)
        puzzle = puzzles[0]
        self.assertEqual(puzzle['puzzle'].name, "Sample")
        self.assertEqual(puzzle.get('answer'), None)

    def test_solve_puzzle(self):
        answer = AnswerSubmission(
            team=self.team_b,
            puzzle=self.sample_puzzle,
            submitted_answer="SAMPLEANSWER",
            is_correct=True,
            submitted_datetime=datetime.fromtimestamp(0),
            used_free_answer=False
        )
        answer.save()

        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("round", args=(self.sample_round.slug,)))
        self.assertEqual(response.status_code, 200)

        puzzles = response.context[0]['round']['puzzles']
        # self.assertEqual(len(puzzles), 1)
        puzzle = puzzles[0]
        self.assertEqual(puzzle['puzzle'].name, "Sample")
        self.assertEqual(puzzle['answer'], "SAMPLE ANSWER")

    def test_team_page(self):
        c = Client()
        c.login(username="b", password="password")

        response = c.get(urls.reverse("team", args=(self.team_b.team_name,)))
        self.assertEqual(response.status_code, 200)
