import logging
from datetime import datetime

import django.urls as urls
from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import Puzzle, Team

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
            team_name="Team B",
            creation_time=datetime.fromtimestamp(0),
        )
        self.team_b.save()

        self.sample_puzzle = Puzzle(
            name="Sample",
            slug="sample",
            body_template="sample.html",
            answer="SAMPLE",
            deep=0,
        )
        self.sample_puzzle.save()
        self.sample_puzzle_2 = Puzzle(
            name="Sample II",
            slug="sample-ii",
            body_template="sample.html",
            answer="SAMPLE",
            deep=1000,
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
