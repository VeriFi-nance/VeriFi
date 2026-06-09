from django.apps import AppConfig


class PostsConfig(AppConfig):
    name = "posts"

    def ready(self):
        # Register post_save signal handlers (asset usage tracking).
        from . import signals  # noqa: F401
