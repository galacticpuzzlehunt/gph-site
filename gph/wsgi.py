'''
WSGI config for gph project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
'''

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gph.settings.prod')
# ??? This might have sometimes helped us generate HTTPS URLs
# os.environ.setdefault('HTTPS', 'on')

application = get_wsgi_application()
