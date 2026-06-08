from cloudinary.models import CloudinaryField
from django.db import models
from accounts.models import WalletUser


class Channel(models.Model):
    class PostPermission(models.TextChoices):
        ALL = "all"
        CREATOR_ONLY = "creator_only"

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(WalletUser, on_delete=models.SET_NULL, null=True, related_name="created_channels")
    post_permission = models.CharField(max_length=15, choices=PostPermission.choices, default=PostPermission.ALL)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ChannelMembership(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        BANNED = "banned"

    class Role(models.TextChoices):
        MEMBER = "member"
        MODERATOR = "moderator"
        OWNER = "owner"

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="channel_memberships")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    role = models.CharField(
        max_length=15,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("channel", "user")
        indexes = [
            models.Index(
                fields=["channel", "status"],
                name="chan_member_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user.address[:10]} in {self.channel.name} ({self.status})"


class Post(models.Model):
    author = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="posts")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="posts", null=True, blank=True)
    content = models.TextField(max_length=500)
    image = CloudinaryField("image", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["-created_at"],
                name="post_global_feed_idx",
                condition=models.Q(channel__isnull=True),
            ),
            models.Index(
                fields=["channel", "-created_at"],
                name="post_channel_feed_idx",
            ),
            models.Index(
                fields=["author", "-created_at"],
                name="post_author_feed_idx",
            ),
        ]

    def __str__(self):
        return f"{self.author.address[:10]}… — {self.content[:40]}"


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="post_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Like<post={self.post_id} user={self.user_id}>"


class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True)
    author = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="post_comments")
    content = models.TextField(max_length=500, blank=True)
    image = CloudinaryField("image", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "created_at"], name="post_comment_thread_idx"),
            models.Index(fields=["parent", "created_at"], name="post_comment_reply_idx"),
        ]

    def __str__(self):
        return f"Comment<post={self.post_id} author={self.author_id}>"


class PostCommentLike(models.Model):
    comment = models.ForeignKey(PostComment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="post_comment_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("comment", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"CommentLike<comment={self.comment_id} user={self.user_id}>"


class SavedProof(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saved_proofs")
    user = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="saved_proofs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="saved_proof_user_idx"),
        ]

    def __str__(self):
        return f"SavedProof<post={self.post_id} user={self.user_id}>"
    

class Asset(models.Model):
    class MarketType(models.TextChoices):
        CRYPTO = "crypto"
        FOREX = "forex"
        COMMODITY = "commodity"
        EQUITY = "equity"
        INDEX = "index"

    class Provider(models.TextChoices):
        COINGECKO = "coingecko"
        YFINANCE = "yfinance"
        BINANCE = "binance"
        KUCOIN = "kucoin"
        KRAKEN = "kraken"
        TWELVEDATA = "twelvedata"

    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    market_type = models.CharField(
        max_length=20,
        choices=MarketType.choices,
        default=MarketType.CRYPTO,
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.COINGECKO,
    )
    provider_symbol = models.CharField(max_length=50, blank=True, default="")
    quote_currency = models.CharField(max_length=10, default="USD")
    binance_symbol = models.CharField(max_length=20, blank=True, default="")
    kucoin_symbol = models.CharField(max_length=20, blank=True, default="")
    kraken_pair = models.CharField(max_length=20, blank=True, default="")
    twelvedata_symbol = models.CharField(max_length=20, blank=True, default="")
    last_price_update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name
    
class HardClaim(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed"
        UNDETERMINED = "undetermined"
        REJECTED = "rejected"

    author = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="hard_claims", null=True, blank=True)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="hard_claims", null=True, blank=True)
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, blank=True, related_name="hard_claims")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, blank=False, null=False)
    direction = models.CharField(max_length=20, blank=True, default="") # this will be binary, 1 up, 0 down
    # Numerator/denominator + magnitude semantics from the ensemble extractor.
    # value_type distinguishes an absolute price target from a percentage move;
    # `percentage` stores the magnitude (a price when value_type == "PRICE").
    value_type = models.CharField(max_length=20, default="PERCENTAGE_UP")
    percentage = models.FloatField(blank=False, null=False) # magnitude: percentage move, or absolute price when value_type == PRICE
    until = models.DateField(blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    reference_price = models.FloatField(blank=True, null=True)
    reference_price_url = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default="undetermined")
    signature = models.TextField(blank=True, default="")
    claim_payload = models.JSONField(blank=True, default=dict)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(until__gt=models.F("created_at")),
                name="hardclaim_until_after_created_at",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "until"],
                name="hardclaim_resolve_idx",
                condition=models.Q(status="undetermined"),
            ),
            models.Index(
                fields=["author", "-id"],
                name="hardclaim_author_idx",
            ),
        ]

    def __str__(self):
        return f"{self.asset} {self.direction}: {self.percentage}%"


class HardClaimEvent(models.Model):
    class EventType(models.TextChoices):
        CREATION = "creation"
        PRICE_CHECK = "price_check"
        RESOLUTION = "resolution"

    hard_claim = models.ForeignKey(HardClaim, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(
                fields=["hard_claim", "event_type"],
                name="hardclaim_event_lookup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.event_type} at {self.timestamp} for claim {self.hard_claim.id}"


class OHLCData(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="ohlc_data")
    timestamp = models.DateTimeField()
    interval = models.CharField(max_length=5, default="1d")
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()

    class Meta:
        unique_together = ("asset", "timestamp", "interval")
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.asset.symbol} {self.timestamp} ({self.interval}) O={self.open} H={self.high} L={self.low} C={self.close}"

class Position(models.Model):
    class Direction(models.TextChoices):
        LONG = "long"
        SHORT = "short"

    class Status(models.TextChoices):
        PENDING = "pending"
        MISSED = "missed"
        ACTIVE = "active"
        CONFIRMED = "confirmed"
        REJECTED = "rejected"
        EXPIRED = "expired"
        CLOSED_EARLY = "closed_early"

    author = models.ForeignKey(WalletUser, on_delete=models.CASCADE, related_name="positions")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="positions", null=True, blank=True)
    post = models.ForeignKey(
        "Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions",
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    entry_price = models.FloatField()
    entry_interval = models.DateTimeField()
    stop_loss = models.FloatField()
    take_profit = models.FloatField()
    lifetime = models.DateTimeField()
    exit_price = models.FloatField(null=True, blank=True)
    pnl_percentage = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    signature = models.TextField(blank=True, default="")
    position_payload = models.JSONField(blank=True, default=dict)

    def __str__(self):
        return f"Position {self.id} ({self.asset.symbol} {self.direction})"

class PositionEvent(models.Model):
    class EventType(models.TextChoices):
        CREATION = "creation"
        ENTRY_TRIGGERED = "entry_triggered"
        PRICE_CHECK = "price_check"
        RESOLUTION = "resolution"
        MANUAL_CLOSE = "manual_close"

    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.event_type} at {self.timestamp} for position {self.position.id}"


class AssetSubscription(models.Model):
    """
    Observer Design Pattern — subscriber list.
    Each row represents one Position or HardClaim subscribing to one Asset (the Observable).
    The Asset iterates this table during notification to dispatch price updates
    to all active observers.
    """
    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="subscriptions"
    )
    position = models.OneToOneField(
        Position, on_delete=models.CASCADE, related_name="asset_subscription", null=True, blank=True
    )
    hard_claim = models.OneToOneField(
        HardClaim, on_delete=models.CASCADE, related_name="asset_subscription", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(position__isnull=False, hard_claim__isnull=True) |
                    models.Q(position__isnull=True, hard_claim__isnull=False)
                ),
                name="subscription_target_exclusive"
            )
        ]

    def __str__(self):
        target = f"Position #{self.position_id}" if self.position_id else f"HardClaim #{self.hard_claim_id}"
        return f"Subscription: {target} → {self.asset.symbol}"


class ClaimMarket(models.Model):
    """Model G — creator-as-trader CPMM market bound to a HardClaim."""

    class Side(models.TextChoices):
        YES = "YES"
        NO = "NO"

    hard_claim = models.OneToOneField(
        HardClaim, on_delete=models.CASCADE, related_name="market", primary_key=True
    )
    y_reserve = models.FloatField()
    n_reserve = models.FloatField()
    yes_outstanding = models.FloatField(default=0.0)
    no_outstanding = models.FloatField(default=0.0)
    escrow = models.FloatField(default=0.0)
    total_burned = models.FloatField(default=0.0)
    creator_side = models.CharField(max_length=3, choices=Side.choices)
    creator_stake_rep = models.FloatField()
    listing_fee_burned = models.FloatField(default=2.0)
    resolved = models.BooleanField(default=False)
    refunded_trivial = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Market<claim={self.hard_claim_id} Y={self.y_reserve:.2f} N={self.n_reserve:.2f}>"


class ClaimStake(models.Model):
    """One row per (market, user). Locked-payout receipt."""

    class Side(models.TextChoices):
        YES = "YES"
        NO = "NO"

    market = models.ForeignKey(
        ClaimMarket, on_delete=models.CASCADE, related_name="stakes"
    )
    user = models.ForeignKey(
        WalletUser, on_delete=models.CASCADE, related_name="claim_stakes"
    )
    side = models.CharField(max_length=3, choices=Side.choices)
    rep_paid_gross = models.FloatField()
    rep_paid_net = models.FloatField()
    shares = models.FloatField()
    entry_price = models.FloatField()
    is_creator = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("market", "user")
        ordering = ["created_at"]

    def __str__(self):
        return f"Stake<m={self.market_id} u={self.user_id} {self.side} {self.shares:.2f}sh>"
