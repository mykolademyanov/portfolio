from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    name = "pgr_django.properties"

    def ready(self):
        # This makes Django load up the register the connected receivers.
        import pgr_django.properties.signals
