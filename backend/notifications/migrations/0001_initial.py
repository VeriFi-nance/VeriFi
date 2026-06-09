from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0010_merge_0009_profilechangelog_0009_walletuser_avatar"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(choices=[("post_liked", "Post liked"), ("post_saved", "Post proof saved"), ("post_commented", "Post commented"), ("comment_replied", "Comment replied"), ("comment_liked", "Comment liked"), ("followed", "Followed"), ("channel_join_request", "Channel join request"), ("channel_approved", "Channel approved"), ("channel_rejected", "Channel rejected"), ("channel_banned", "Channel banned"), ("channel_unbanned", "Channel unbanned"), ("channel_moderator_added", "Channel moderator added"), ("channel_moderator_removed", "Channel moderator removed"), ("claim_resolved", "Claim resolved"), ("claim_market_opened", "Claim market opened"), ("rep_spent", "Rep spent"), ("rep_payout", "Rep payout"), ("energy_granted", "Energy granted"), ("energy_spent", "Energy spent"), ("position_entry_triggered", "Position entry triggered"), ("position_resolved", "Position resolved")], max_length=40)),
                ("title", models.CharField(max_length=120)),
                ("message", models.CharField(blank=True, default="", max_length=280)),
                ("target_url", models.CharField(blank=True, default="", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("dedupe_key", models.CharField(blank=True, max_length=160, null=True, unique=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications_sent", to="accounts.walletuser")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="accounts.walletuser")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "read_at", "-created_at"], name="notif_recipient_read_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "-created_at"], name="notif_recipient_created_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["dedupe_key"], name="notif_dedupe_idx"),
        ),
    ]
