# Deployment

**Draft** instructions for setting this website up on some relatively easy platforms. If you have any experience with deploying, you probably don't need to read this document.

## PythonAnywhere

PythonAnywhere is a Python hosting service that has a reasonably powerful free tier, and is overall pretty beginner-friendly, but if you do know your way around computers you might have a bit more trouble. (For example, being able to SSH from your own computer appears to be a paid feature.) The instructions below are mostly cribbed from:

- [Deploying an existing Django project on PythonAnywhere](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject)
- [How to setup static files in Django](https://help.pythonanywhere.com/pages/DjangoStaticFiles)

### Getting the code in

Follow the instructions on PythonAnywhere to create a website. Open a shell by clicking `$ Bash`. When you see a prompt, paste or type the following two lines:

```
git clone https://github.com/galacticpuzzlehunt/gph-site
mkvirtualenv venv --python=/usr/bin/python3.8
```

The first line will get the `gph-site` source code. Of course, you should feel free to fork the repository to your own GitHub account or to any other thing that gives you a Git URL, in which case you would modify that URL.

The second line will install a *virtual environment* in which you can run a particular Python version and install packages without affecting the rest of your system. We chose `python3.8` as the newest version of Python available as of time of writing, on which we are pretty sure `gph-site` runs, so it's probably a safe bet unless you're reading this in like 2025. This might take a few seconds to a minute. It will also automatically activate your virtualenv. Your prompt should now say `(venv)` at the start. (You can name your virtualenv anything you want, `venv` or not; but it should probably be alphanumeric and you should make sure to change all its appearances below.)

**If you open a new shell in the future and want to work on the website, you will need to type `workon venv`** to reactivate the virtual environment.

Next:

```
cd gph-site
pip install -r requirements.txt
```

The first line will navigate into the `gph-site` directory where you copied this code. The second line will install all the required packages. This might also take a few minutes, in particular there will be a bit of a wait after "Installing collected packages...". There might even be an error (TODO: retest this) but I think it's safe.

### Configuring PythonAnywhere

On the PythonAnywhere website, find the Web tab; click "Add a new web app" and then "Manual configuration". (Do not choose "Django" even though `gph-site` is a Django project; that's for starting a *new* Django project.) Select Python 3.8 or the same version you selected when creating your virtual environment.

You should end up on a web app configuration page with a big button that says "Reload (yourusername).pythonanywhere.com" or some such and a ton of other stuff below. You'll be coming back to this page often.

Fill in some fields on this page, replacing `yourusername` with your actual username:

- Source code: `/home/yourusername/gph-site` (unknown if this is necessary)
- Virtualenv: `/home/yourusername/.virtualenvs/venv`

Open the "WSGI configuration file" link in a new tab. You will be able to edit it directly from your browser. Comment out or delete the existing code (you can do this by adding `#` before the start of every line that doesn't already have `#`), and put in this code, which should be similar to some code commented "Django" in the default file contents (replacing `yourusername` as before):

```python
import os
import sys

sys.path.append('/home/yourusername/gph-site')
os.environ['DJANGO_SETTINGS_MODULE'] = 'gph.settings.prod'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Hit Save on the top. Go back to the Configuration page we were on previously and click the green button that says "Reload yourusername.pythonanywhere.com".

In theory, if you now visit `yourusername.pythonanywhere.com` you should see a very basic puzzlehunt website with some text about a puzzlehunt, but none of the styles will be there. To fix that, go to a terminal, activate your virtual environment and `cd` into your code directory if necessary, and run `python manage.py collectstatic`. Also, on the Configuration page under "Static files", add this entry:

URL        | Directory
-----------|---------------------------------
`/static/` | `/home/yourusername/gph-site/static`

Click the green Reload button on the Configuration page, and refresh your browser. If everything went as expected, the home page should be visible and styled. In the future, if you make further changes to the static files, you will need to run `python manage.py collectstatic` again.

Although the home page loads, dynamic pages like Teams and Puzzles will show an error, because we haven't set up the database. Back in the shell, with your virtual environment activated and in the `gph-site` directory, run:

```
python manage.py migrate
```

If you want to create a user you can use to log in to the website and administer the hunt, run `python manage.py createsuperuser` in the terminal and follow instructions. There are also configurations that (currently) cannot be made directly through the website, which are generally in `hunt_config.py`.

**IMPORTANT: Set the SECRET_KEY in `settings/base.py`** to a securely generated long random string. Your app will still run if you don't do this step, but it will be insecure!

## Heroku

Heroku is another hosting "platform as a service" with a free tier. The free tier is serviceable, but Heroku scales up and down to different amounts of compute power quite well and all costs are pro-rated (albeit by how long your app is set to that scale, not how much actual compute gets used).

Follow instructions on the Heroku website to install the Heroku CLI and then create an app. Mine is called `gph-site-test`. Then, clone this repository and run `heroku git:remote -a gph-site-test`.

Heroku requires some configuration/code changes, which are on a separate branch `heroku` of this repo. It's not essential that you understand this list, but they will probably be helpful for debugging:

- We need a `Procfile` to tell Heroku how to run our app.
- [SQLite isn't a good fit for Heroku](https://devcenter.heroku.com/articles/sqlite3) because Heroku doesn't provide a "real" filesystem. Fortunately Heroku provides easy-to-use (and free at low volumes) PostgreSQL, so we need to switch Django to use that instead. **Note** that running the website from the Heroku branch will be a bit harder because you need to get PostgreSQL running locally too. (It might be OK to switch the database only in the `prod` settings file, but we haven't set that up and `manage.py` still uses `dev` which means trying to running `manage.py` stuff on your prod server will not work. TODO: investigate if this is OK)
- We install the `whitenoise` middleware so Django can serve static files directly in a production-ready way.

If you run `git push heroku heroku:master`, you will push the `heroku` branch to its `master` and deploy the code.

**Make sure to `heroku config:set SECRET_KEY="YOUR_SECRET_KEY_HERE"`** to a securely generated long random string. Your app will still run if you don't do this step, but it will be insecure!

In theory, if you now visit `yourappname.herokuapp.com` you should see the properly styled front page of the puzzlehunt website with some text about a puzzlehunt. (Heroku will automatically run `collectstatic` for you.) However, dynamic pages like Teams and Puzzles will show an error. You will still need to set up the database by running `heroku run python manage.py migrate` manually, or you can [add it to the Procfile to run automatically on every release](https://help.heroku.com/GDQ74SU2/django-migrations):

```
release: python manage.py migrate
```
