from django.apps import AppConfig


class GDPRConfig(AppConfig):
    name = 'gdpr'
    # Django 6.0 changed the DEFAULT_AUTO_FIELD default to BigAutoField. Pin the primary key type used by the existing
    # migrations so projects do not get unexpected migrations for this app.
    default_auto_field = 'django.db.models.AutoField'
