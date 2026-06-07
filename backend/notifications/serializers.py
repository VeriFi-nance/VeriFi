from rest_framework import serializers

from accounts.serializers import avatar_delivery_url

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor_address = serializers.CharField(source="actor.address", read_only=True, allow_null=True)
    actor_username = serializers.CharField(source="actor.username", read_only=True, allow_null=True)
    actor_avatar_url = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "message",
            "target_url",
            "metadata",
            "created_at",
            "read_at",
            "unread",
            "actor_address",
            "actor_username",
            "actor_avatar_url",
        ]

    def get_actor_avatar_url(self, obj):
        avatar = getattr(obj.actor, "avatar", None) if obj.actor else None
        return avatar_delivery_url(avatar)

    def get_unread(self, obj):
        return obj.read_at is None
