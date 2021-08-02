from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

class CustomStorage(ManifestStaticFilesStorage):
    patterns = ()
