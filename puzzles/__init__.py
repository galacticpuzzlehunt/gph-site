from django.apps import AppConfig
import sys


# Generally speaking, it's possible that the server will appear to start up
# using Python 2, but non-obvious things like Unicode literals will be
# completely broken. Make sure we're using Python 3.
assert sys.version_info.major == 3, 'Use Python 3'

class PuzzlesConfig(AppConfig):
    name = 'puzzles'

default_app_config = 'puzzles.PuzzlesConfig'
