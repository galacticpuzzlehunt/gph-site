import traceback
import json
from django.views.decorators.http import require_POST
from puzzles.messaging import log_puzzle_info

@require_POST
def submit(request):
    "A crude example of an interactive puzzle handler."

    # Note that this example handler is completely stateless; it doesn't
    # remember anything about past interactions or requests. Some ways to add
    # state to an interactive puzzle:
    #
    # 1. Keep this handler stateless, persist the state on the client, and send
    # the entire state back and forth for every request. You can use local
    # storage on the client to persist the state between reloads. You can
    # additionally encrypt/decrypt the state on the server if you don't want
    # users to be able to introspect or tamper with it. Of course, this option
    # requires that the state be fairly compact and cheaply
    # serializable/deserializable. (Remember, kids: depickling untrusted
    # sources can lead to arbitrary code execution!)
    #
    # 2. Persist it on the server. You can just add a puzzle-specific model
    # with a foreign key to Team. If you have strong performance needs and are
    # feeling adventurous, you might even add an in-memory store like Redis or
    # something.
    #
    # 3. Use websockets. This is beyond the scope of this file; check the
    # README and messaging.py.
    #
    # Advantages of 1: No database migrations or load; responses can often be
    # faster. Lets team members have separate state, which is desirable for
    # some puzzles. Works for solvers even if they're logged out or don't even
    # have an account.
    #
    # Advantages of 2: Easy to share state between team members. Don't need
    # additional complexity to prevent client-side tampering with state. Easier
    # to collect statistics about solving after the fact. If you don't get
    # client-side state right the first time, fixing it after some solvers have
    # made partial progress can be a pain; server-side state lets you at least
    # keep the possibility of manually introspecting or fixing it as needed.

    try:
        body = json.loads(request.body)

        # This code should be written somewhat defensively to not leak secrets
        # or worse, even for arbitrary requests.
        index = int(body['index'])
        guess = body['guess'].upper()
        if not (len(guess) == 1 and 'A' <= guess <= 'Z'):
            return {
                'error': 'Please guess a letter from A to Z.',
                'correct': False,
            }
        # (This is buggy, can you see why?)
        correct = "INTERACTIVE"[index-1] == guess

        # Purely optional logging. You might use this to gather statistics
        # about how often teams interacted with the puzzle in some specific
        # way.
        if correct:
            team = request.context.team
            name = team.team_name if team else "<noname>"
            log_puzzle_info("Interactive Demo", name, f"Guessed {index} correctly")

        return {'correct': correct}
    except (KeyError, AttributeError):
        # This error handling is pretty rough.
        return {
            'error': 'Please submit a well-formed response.',
            'correct': False,
        }
    except (ValueError, IndexError):
        return {
            'error': 'Please submit an integer between 1 and 11 for the index.',
            'correct': False,
        }
    except:
        traceback.print_exc()

        # You may wish to provide more details or a call to action. Do you want
        # the solvers to retry, or email you?
        return {'error': 'An error occurred!', 'correct': False}
