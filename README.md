This is a Django app for running puzzlehunts, written by several members of ✈✈✈ Galactic Trendsetters ✈✈✈ for running the [Galactic Puzzle Hunt](https://galacticpuzzlehunt.com/).

This repository is not formally maintained; expect it to be based on an export of the most recently run GPH, with any updates at other times of year being best-effort. In particular, while we've stripped out most of the hunt-specific logic, some fundamental pieces are still in place: GPH 2019 unlocked puzzles sequentially using DEEP (a combination of time and solves), while GPH 2020 had puzzles divided by round, so those conditions are reflected in the model schema and unlocking code. If you want to do something different, say an Australian-style hunt, it should still be possible, but you'll have to do some legwork.

We will try to respond to emails or pull requests when we can, but this isn't guaranteed, especially during the months when we aren't actively working on the current GPH. As several other online hunts have used this codebase, you may be able to direct questions to one of them, although at this time there does not seem to be any listing of such teams.

# Quick Start

- Set up your environment.
  - Make sure you have Python 3 and the corresponding `pip`. (This may be named `pip3` depending on your environment.)
  - We recommend that you install virtualenv: `pip install virtualenv`. This allows you to install this project's dependencies into a "virtual environment" contained in this directory.
    - You can also proceed without virtualenv (skip these steps), which will install the dependencies globally. This is not recommended if you develop in other Python projects on the same machine.
  - Create a virtualenv: `virtualenv venv`
    - If you have both Python 2 and Python 3 on your system, use the `-p` argument to `virtualenv` to point to the correct Python runtime, for example: `virtualenv venv -p python3`
    - If this doesn't work, you may have to add to your path; try `python -m virtualenv venv` instead if you don't want to do that.
  - Activate the virtualenv with `source venv/bin/activate`
    - Alternatively use `venv/bin/activate.csh` or `venv/bin/activate.fish` if you're using csh or fish.
    - Use `venv\Scripts\activate` on Windows.
    - You should run this command each time before you start working on this app.
  - Later, when you're done working on the project and want to leave the virtualenv, run `deactivate`.
- Install the required packages: `pip install -r requirements.txt`
  - Are you getting `fatal error: Python.h: No such file or directory`? Try installing `python-dev` libraries first (e.g. `sudo apt-get install python3-dev`).
- Start the development server with `./manage.py runserver`
  - If you get a warning (red text) about making migrations, stop the server, run `./manage.py migrate`, then start it again.
  - If all went well, the dev server should start, printing its local URL to stdout.

# Areas for Improvement

- We rely on Redis, specifically for WebSocket support and rate limiting. Unfortunately, our deploy configuration doesn't do a good job of ensuring a compatible Redis environment. This could use some attention from someone who understands Ansible.
- Our database writes are not atomic; if a request handler loads a model instance, does some other stuff, then calls `.save()`, that will save all the fields of the object and possibly overwrite some other handler that ran in the meantime. Our schema so happens to be set up so that (apart from Hints) we don't often have to update existing objects at all, let alone within fractions of a second of each other in a non-idempotent way. But we could address this with transactions, shortening the time between read and write, and/or limiting the fields written.
- In production we use gunicorn. It does not appear that gunicorn has a rolling restart mechanism. That is, even though it uses many worker processes, all of those workers die and restart at the same time when redeploying the server, which leads to many noticeable seconds of downtime. It would be nice to fix this.

# How Do I...?

- ...even?

  + The site is built on Django, which has a lot of features and is pretty self-contained. Usually, you will start a local server with `./manage.py runserver` and make changes within the `puzzles/` subdirectory. `runserver` will watch for code changes and automatically restart if needed.

- ...set up the database?

  + The site is set up to use a `db.sqlite3` file in the root of this repository as its database. If this doesn't exist, Django will create a new empty database when you run `./manage.py migrate`. It's perfectly fine to start with this, but you won't have any puzzles populated and you almost certainly want to create a superuser.

    If you just want to try out the website quickly with some sample data, you can run `./manage.py loaddata sample.yaml` (after `./manage.py migrate`) to load a sample hunt, an admin account (username and password `admin`), and a test account with a team (username and password `test`). You can view the templates used to render the puzzles in the [puzzles/templates/puzzle_bodies](puzzles/templates/puzzle_bodies) and [puzzles/templates/solution_bodies](puzzles/templates/solution_bodies) folders, which you can also base your puzzles/solutions off of.

- ...be a superuser?

  + Superusers are a Django concept that allows users access to the `/admin` control panel on the server. We have additionally set it to control access to certain site pages/actions, such as replying to hint requests from teams, or viewing solutions before the deadline. `./manage.py createsuperuser` will make a new superuser from the command line, but this user won't be associated with any team on the site (so it won't be able to e.g. solve puzzles). To fix this, you can either get a prepopulated `db.sqlite3` from a friend, hit the `Create team` button in the top bar on the main site to attach a new team to your user, or go into `/admin` and swap out the user on an existing team for your new one.

- ...edit the database?

  + The `/admin` control panel lets you query and modify all of the objects in the database. It should be pretty straightforward to use. It does use the same login as the main site, so you won't be able to log in as a superuser for `/admin` and a non-superuser for the main site in the same browser window.

- ...be a testsolver?

  + We have a notion of prerelease testsolver that is separate from that of superuser. Prerelease testsolvers can see all the puzzles even before the hunt starts. To make a prerelease testsolver, you can find a team in `/admin` and set the relevant checkbox there. Or, to make yourself a prerelease testsolver as a superuser, use the `Toggle testsolver` button in the top bar.

- ...set up a "real" testsolve?

  + Go to `/admin` and set a team's start offset. The greater this offset, the earlier that team will be able to start and progress in the hunt. This can be used to run a full-hunt testsolve to test the unlock structure.

- ...see some other team's view of the hunt?

  + As a superuser, go to `/teams` and click on any `Impersonate` button. Be careful with this, as you don't want to accidentally perform any actions on behalf of the team.

- ...add a "keep going" message? give a team more guesses? delete a team? etc.

  + All these things should be done through `/admin`.

- ...give myself hints for testing? reset my hints? show me a puzzle's answer? etc.

  + All these things can be done through the shortcuts menu in the top bar as a superuser (but can also be done through `/admin`).

- ...postprod a puzzle?

  + You'll need both a prerelease testsolver team, and a database Puzzle object (either create one or obtain a `db.sqlite3` with the puzzles set up) for your puzzle. The `body_template` field on the Puzzle defines which template file will be used (this doesn't have to match the `slug` field, though it may be nice if it does). Put the body of the puzzle in a file under `puzzles/templates/puzzle_bodies`. Put required static resources under `puzzles/static/puzzle_resources/$PUZZLE`. Put solutions and their resources under `puzzles/templates/solution_bodies`. See the sample files there as guides.

    Puzzles and solutions (but not other templates) support Markdown (though the library may or may not have some bugs). You'll override either `puzzle-body-md` or `puzzle-body-html` depending on whether you'd like to write Markdown or HTML. The same applies to solution bodies, author notes, and appendices.

- ...edit an email template?

  + All templates used to render email bodies have two versions, HTML and plain text, with the same filename. If you change one, be sure to change the other to match.

- ...create a new model?

  + Add a class to `models.py` on the pattern of the ones already there. To make it show up in `/admin`, add it to `admin.py` as well. Finally, if you add or change any database model or field, you'll need to run `./manage.py makemigrations` to create a migration file, then check that in.

- ...use a model?

  + The code should have plenty of examples for creating and reading database objects, and Django's online documentation is quite comprehensive. As a general tip, Django's unobtrusive syntax for database objects means it's very easy to trigger a lookup and not notice. It's mostly important to avoid doing `O(n)` (or worse) separate database lookups for one query; otherwise, don't worry about it too much. However, if you'd like to find opportunities for optimization, you can set up Django to print database queries to the console by changing the `django.db.backends` log setting.

- ...create a new view?

  + Add a function to `views.py` that returns a response object (usually by rendering a template, but you can also create one and write to it directly). Check if you want to gate it behind any of the decorators used in the file. You will need to add your view to `urls.py` as well to make it accessible. The name you put in `urls.py` should be used with functions like `{% url %}` (in templates) or `reverse` and `redirect` (in Python) to generate the URL for your page whenever you need to output it.

- ...create a view called by a puzzle?

  + If your view is for a specific puzzle, you should put it in `puzzlehandlers/`. That directory also contains helpers for rate limiting so teams can't brute-force your puzzle. Then in your puzzle template, you can include Javascript or forms that call your new view however you wish.

- ...add CSS?

  + If the element you're styling is in `base.html` or appears in multiple separate pages, put it in `base.css`. Otherwise, just put it inline in your template.

- ...add template context?

  + Context parameters are how to pass information from Python into templates. Similar to the above, if you want to use the same data in more than one page, consider putting it in `context.py`, which defines context shared between all page templates. Otherwise, put it in a dict passed to `render` in your `view.py` function.

- ...add template functions?

  + To create a custom tag or filter that's callable from templates (for example, we have one that takes a timestamp and formats it), you have to put it in `templatetags/`. (This is enforced by Django for some reason.) Then, in the template file you're changing, include `{% load puzzle_tags %}` at the top.

- ...set up the unlock structure?

  + The unlock threshold for each puzzle is defined in its database entry. Most other parameters and logic are in `hunt_config.py`. You will probably just have to edit these case by case, but note that e.g. it is not necessary to make code changes in order to update puzzle unlock thresholds.

- ...enable the story or wrapup page?

  + In addition to making the necessary template changes, in order to make these pages visible, you have to set the `*_PAGE_VISIBLE` flags in `hunt_config.py` to true.

- ...do analysis of what teams do during the hunt?

  + Use the shortcuts menu to download a hint log, guess log, and puzzle log. The first two are generated from the database; the latter from whatever calls `messaging.log_puzzle_info`. For example, if you have a puzzle that's a game, you can set up an endpoint to log whenever a team wins. You can also set up whatever additional logs you wish (and if you want, expose them using a new view over the bridge). Then you can write your own scripts or spreadsheets to analyze them.

- ...time zones?

  + For reasons that I'm sure made sense at the time (heh), Django stores timestamps as UTC in the database and converts them to the currently set time zone (i.e. Eastern) when _rendering templates_. This means that you don't need to worry if you include a timestamp in a template file, but if you're trying to render it in Python (_including_ in `templatetags/`), you may have to adjust its time zone explicitly to prevent it from showing as UTC.

- ...issue errata?

  + Errata are stored in the database. You can go to `/errata` as a superuser to create one. Errata can be shown on the puzzle page, the top-level updates page, or both; you can also create a general announcement that's not associated with a puzzle. If you save an erratum as unpublished, you can see how it looks before revealing it to solvers. The updates page won't be available to solvers until there's something they can see there.

- ...answer hints?

  + You can find the hint interface at `/hints`, through links in Discord hint messages, or via the red hint icon that appears for superusers browsing the site when there are unanswered hints. The interface lets you claim a hint, write a response, and send it off to the team. If a hint is marked as obsolete, that means the team solved the puzzle while it was open; if refunded, then the responder decided not to charge them a hint token. If a hint is a followup, that means it's part of a conversation thread with the team and doesn't cost a token either.

- ... use websockets?

  + We now have somewhat experimental websocket support! Take a look at the consumer classes in `messaging.py`; there are prototypes for two-way communication with a single browser tab, or for broadcasting to all members of a team or all logged-in admins. If you want something different, say for a "Teamwork Time" puzzle where team members interact with each other, it shouldn't be hard to add. Then add your consumer to `routing.py` and use `openSocket` in JS to connect to it.

- ... provide the site in my language?

  + Generate the translations placeholders for your language `lang_COUNTRY` (e.g. en_US):
    + `django-admin makemessages -e html,txt,py,svg -l lang_COUNTRY`
    + `django-admin makemessages -d djangojs -l lang_COUNTRY`
  + add your translations in msgstr in the django.po and djangojs.po files under locale/`lang_COUNTRY`
  + Compile the translations:
    + `django-admin compilemessages`
  + create a gph/formats/`lang` (e.g. en) folder and copy an existing one (e.g. en to be translated, see https://docs.djangoproject.com/en/4.0/ref/settings/#std:setting-FORMAT_MODULE_PATH). This contains the date/time formats used in django templates (see https://docs.djangoproject.com/en/4.0/ref/templates/builtins/#std:templatefilter-date)
  + set LANGUAGE_CODE in base/settings.py as `lang-country` (e.g. en-us)
  + See https://docs.djangoproject.com/en/4.0/topics/i18n/ for more info


# Repository Details

The GPH server is built on Django. We use Ansible to manage deploys to our cloud VMs and nginx as the web server in production, but you're free to use whatever web server setup makes sense for you.

- `db.sqlite3`: This is the database used by Django. An empty one is automatically created if you start the server without it, but for testing many features, you may wish to get one with teams, puzzles, etc. populated.
- `manage.py`: This is Django's way of administering the server from the command line. It includes help features that will tell you the things it can do. Common commands are `createsuperuser`, `shell`/`dbshell`, `migrate`/`makemigrations`, and `runserver`. There are also custom commands, defined in `puzzles/management/commands`.
- `README.md`: You're reading me.
- `requirements.txt`: A file that `pip` can read to install the Python packages needed by the server. If you want to add one, put it in the file. Locally, you'll need to run `pip install -r requirements.txt` to pick it up (inside the virtualenv if you're using one). The production server will pick it up when it next gets deployed.
- `gph/`: A catch-all for various configuration.
  - `wsgi.py`: Boilerplate for hooking Django up to a web server in production.
  - `settings/`: Here are a few sets of Django settings depending on environment. Most of the options are built-in to Django, so you can consult the docs. You can also put new things here if they should be global or differ by environment. They'll be accessible anywhere in the Django project.
  - `urls.py`: Routing configuration for the server. If you add a new page in `views.py`, you'll need to add it here as well.
- `logs/`: Holds logs written by the server while it runs.
- `static/`: If you run `collectstatic`, which you probably should in production, Django gathers files from `puzzles/static` and puts them here. If you're seeing weird static file caching behavior or files you thought you'd deleted still showing up, try clearing this out.
- `venv/`: Contains the virtualenv if you're using one, including all the Python packages you installed for this project.

## Puzzles

This directory contains all of the business logic for the site.

- `admin.py`: Sets up custom logic for the interface on `/admin` for managing the database objects defined in `models.py`. If you add a new model, add it here too.
- `context.py`: This file defines an object that gets attached to the request, encompassing data that can be calculated when responding to the request as well as accessed inside rendered templates.
- `forms.py`: Configuration for various user-visible forms found throughout the site, including validation functions.
- `hunt_config.py`: Intended to encapsulate all the numbers and details for one year's hunt progression, including the date and time for the start and end of hunt.
- `messaging.py`: Functions for sending email and Discord messages.
- `models.py`: Defines database objects.
  - `Puzzle`: A puzzle.
  - `Team`: A team corresponds to a Django user, since it has a single login, but a team can list multiple names and emails. TeamMember objects are essentially just for display and email purposes.
  - `PuzzleUnlock`: Represents a team having access to a puzzle. Since this needs to be recalculated all the time anyway as teams progress, it's not that useful as a caching mechanism. It mostly allows analysis and statistics of when exactly unlocks happened.
  - `AnswerSubmission`: A guess by a team on a puzzle, either right or wrong.
  - `Hint`: A hint request initiated by a team. Has special listeners to send email and Discord messages when one is received or answered.
- `shortcuts.py`: Defines a number of one-click actions available to superusers for use while developing the site.
- `views.py`: Defines the handlers serving each page on the site. Makes heavy use of decorators for access control.
- `management/`: Defines custom commands for `manage.py`; see below. Generally, this includes any sort of administrative action you might want to automate with access to the database.
- `migrations/`: If you ever change `models.py` by deleting, removing, or modifying a database type or its fields, run `./manage.py makemigrations` to autogenerate a migration file that makes necessary changes to the database. This runs during deployment, or run `./manage.py migrate` locally.
- `puzzlehandlers/`: If you write a puzzle that requires server code, put it in a new file here (and refer to it in `views.py` and/or `urls.py`). You can wrap it in a rate limiter and export it from `__init__.py`.
- `static/`: Any files to be served directly to the user's browser. Note: do NOT put anything used by a puzzle solution in here, as they should be locked until the hunt ends.
- `templates/`: Generally, these get rendered from `views.py`. Contains not only HTML files but also plain-text email bodies (side-by-side with HTML versions) and inline SVGs.
  - `puzzle_bodies/`: All templates for individual puzzles. Put any static resources in `static/puzzle_resources/$PUZZLE/`.
  - `solution_bodies/`: All templates for individual solutions. Put any static resources in `templates/solution_bodies/$PUZZLE/`.
- `templatetags/`: If you want to define a function callable from within a template, put it in `puzzle_tags.py`. This is for stuff like formatting timestamps.

# Deployment

If you are new to web development and deployment, you can check out [DEPLOY.md](DEPLOY.md) for some **work in progress** suggestions on places to deploy this site and instructions on how to deploy them. Otherwise, here is a short list of things you should fix

(The most accurate way is probably just to grep for the string `FIXME`.

**Required:**

- **Set the SECRET_KEY in gph/settings/base.py** to a secure random key. (TODO: what's actually the best way to do this? Should we use an environment variable?) Also probably set up the email credentials and titles.
- Change all the settings in `puzzles/hunt_config.py`: hunt times, title, organizers, email, etc.
- Set the domain in `gph/settings/prod.py` and `gph/settings/staging.py` if you're using that.

Optional:

- Configure the paths where logs are stored in `settings/base.py`.
- Put the text you want in the home page and other static pages via the templates. (See [CONTENT.md](CONTENT.md))
- `puzzles/messaging.py` contains some configurable settings for Discord webhooks.

# Hunt Administration

Your main tool will be the Django admin panel, at `/admin` on either a local or production server. Logging in with an admin account will let you edit any database object. Convenience commands are available in the shortcuts menu on the main site.

`manage.py` is a command-line management tool. We've added some custom commands in `puzzles/management/`. If you're running the site in a production environment, you'll need SSH access to the relevant server.

If something goes very wrong, you can try SSHing to the server and editing files or using Git commands directly. We recommend taking regular backups of the database that you can restore from if need be. We also recommend controlling which commits make it to the live site during the hunt, by creating a separate `production` Git branch that lags behind `master`, and verifying all changes on a staging deploy.

# Timing

In addition to the hunt start and end time, there's also a somewhat non-obvious "hunt close time" in `hunt_config.py`. Here's how it works:

- When the hunt *ends*, the leaderboard freezes, hint requests are disabled, and solutions are published, but account signups and progressing through the hunt are still allowed. The idea is to give people extra time to finish the hunt at their own pace if they want, but without any of the maintenance costs of actually staffing the hunt (responding to hint requests, avoiding spoilers for competition fairness).
- When the hunt *closes*, account registration and log ins are actually disabled.

You can, of course, set the hunt close time to be equal to the hunt end time to skip the in-between stage.
