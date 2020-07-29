# Deployment

**Draft** instructions for setting this website up on some relatively easy platforms. If you have any experience with deploying, you probably don't need to read this document.

## PythonAnywhere

This is completely free and overall pretty beginner-friendly, but if you do know your way around computers you might have a bit more trouble. (For example, being able to SSH from your own computer appears to be a paid feature.) It's mostly cribbed from:

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

Click the green Reload button on the Configuration page, and refresh your browser.
