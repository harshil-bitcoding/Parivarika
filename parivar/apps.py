from django.apps import AppConfig

class ParivarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parivar'

    def ready(self):
        import parivar.signals