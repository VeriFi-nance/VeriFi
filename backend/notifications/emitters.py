from __future__ import annotations

from accounts.models import WalletUser
from posts.models import Channel, HardClaim, Position, Post, PostComment

from .models import Notification
from .services import notify_once


def _name(user: WalletUser | None) -> str:
    if user is None:
        return "Someone"
    return f"@{user.username}" if user.username else user.address[:10]


def _post_url(post_id: int | None) -> str:
    return f"/post/{post_id}" if post_id else "/feed"


def _claim_url(claim: HardClaim) -> str:
    return f"/claim/{claim.id}"


def _position_url(position: Position) -> str:
    return _post_url(position.post_id)


def notify_post_liked(post: Post, actor: WalletUser, like_id: int):
    return notify_once(
        recipient=post.author,
        actor=actor,
        type=Notification.Type.POST_LIKED,
        title="Your post got a like",
        message=f"{_name(actor)} liked your post.",
        target_url=_post_url(post.id),
        metadata={"post_id": post.id, "like_id": like_id},
        dedupe_key=f"post-like:{like_id}",
    )


def notify_post_saved(post: Post, actor: WalletUser, saved_proof_id: int):
    return notify_once(
        recipient=post.author,
        actor=actor,
        type=Notification.Type.POST_SAVED,
        title="Your proof was saved",
        message=f"{_name(actor)} saved your post proof.",
        target_url=_post_url(post.id),
        metadata={"post_id": post.id, "saved_proof_id": saved_proof_id},
        dedupe_key=f"post-saved:{saved_proof_id}",
    )


def notify_post_commented(comment: PostComment):
    return notify_once(
        recipient=comment.post.author,
        actor=comment.author,
        type=Notification.Type.POST_COMMENTED,
        title="New comment on your post",
        message=f"{_name(comment.author)} commented on your post.",
        target_url=_post_url(comment.post_id),
        metadata={"post_id": comment.post_id, "comment_id": comment.id},
        dedupe_key=f"post-comment:{comment.id}:post-author",
    )


def notify_comment_replied(comment: PostComment):
    if comment.parent is None:
        return None
    return notify_once(
        recipient=comment.parent.author,
        actor=comment.author,
        type=Notification.Type.COMMENT_REPLIED,
        title="New reply to your comment",
        message=f"{_name(comment.author)} replied to your comment.",
        target_url=_post_url(comment.post_id),
        metadata={"post_id": comment.post_id, "comment_id": comment.id, "parent_id": comment.parent_id},
        dedupe_key=f"comment-reply:{comment.id}:parent-author",
    )


def notify_comment_liked(comment: PostComment, actor: WalletUser, like_id: int):
    return notify_once(
        recipient=comment.author,
        actor=actor,
        type=Notification.Type.COMMENT_LIKED,
        title="Your comment got a like",
        message=f"{_name(actor)} liked your comment.",
        target_url=_post_url(comment.post_id),
        metadata={"post_id": comment.post_id, "comment_id": comment.id, "like_id": like_id},
        dedupe_key=f"comment-like:{like_id}",
    )


def notify_followed(recipient: WalletUser, actor: WalletUser, follow_id: int):
    return notify_once(
        recipient=recipient,
        actor=actor,
        type=Notification.Type.FOLLOWED,
        title="New follower",
        message=f"{_name(actor)} followed you.",
        target_url=f"/u/{actor.username or actor.address}",
        metadata={"follow_id": follow_id, "actor_address": actor.address},
        dedupe_key=f"follow:{follow_id}",
    )


def notify_channel_join_request(channel: Channel, actor: WalletUser, membership_id: int):
    return notify_once(
        recipient=channel.creator,
        actor=actor,
        type=Notification.Type.CHANNEL_JOIN_REQUEST,
        title="New channel join request",
        message=f"{_name(actor)} requested to join {channel.name}.",
        target_url="/settings",
        metadata={"channel_id": channel.id, "membership_id": membership_id},
        dedupe_key=f"channel-join:{membership_id}",
    )


def notify_channel_membership(
    *,
    channel: Channel,
    recipient: WalletUser,
    actor: WalletUser,
    type: str,
    title: str,
    message: str,
    dedupe_key: str,
):
    return notify_once(
        recipient=recipient,
        actor=actor,
        type=type,
        title=title,
        message=message,
        target_url="/feed",
        metadata={"channel_id": channel.id, "channel_name": channel.name},
        dedupe_key=dedupe_key,
    )


def notify_claim_resolved(claim: HardClaim):
    if claim.status not in (HardClaim.Status.CONFIRMED, HardClaim.Status.REJECTED):
        return None
    return notify_once(
        recipient=claim.author,
        actor=None,
        type=Notification.Type.CLAIM_RESOLVED,
        title="Your claim resolved",
        message=f"Your {claim.asset.symbol} claim resolved as {claim.status}.",
        target_url=_claim_url(claim),
        metadata={"claim_id": claim.id, "status": claim.status, "asset_symbol": claim.asset.symbol},
        dedupe_key=f"claim-resolved:{claim.id}:{claim.status}",
        suppress_self=False,
    )


def notify_claim_market_opened(claim: HardClaim, actor: WalletUser):
    return notify_once(
        recipient=actor,
        actor=actor,
        type=Notification.Type.CLAIM_MARKET_OPENED,
        title="Claim market opened",
        message=f"You opened a market for your {claim.asset.symbol} claim.",
        target_url=_claim_url(claim),
        metadata={"claim_id": claim.id},
        dedupe_key=f"claim-market-opened:{claim.id}",
        suppress_self=False,
    )


def notify_rep_spent(
    *,
    recipient: WalletUser,
    amount: float,
    title: str,
    message: str,
    target_url: str,
    metadata: dict,
    dedupe_key: str,
):
    return notify_once(
        recipient=recipient,
        actor=recipient,
        type=Notification.Type.REP_SPENT,
        title=title,
        message=message,
        target_url=target_url,
        metadata={"amount": amount, **metadata},
        dedupe_key=dedupe_key,
        suppress_self=False,
    )


def notify_rep_payout(
    *,
    recipient: WalletUser,
    amount: float,
    claim: HardClaim,
    refunded: bool,
):
    return notify_once(
        recipient=recipient,
        actor=None,
        type=Notification.Type.REP_PAYOUT,
        title="Rep refunded" if refunded else "Rep payout received",
        message=(
            f"{amount:.2f} rep was refunded from the {claim.asset.symbol} market."
            if refunded
            else f"You received {amount:.2f} rep from the {claim.asset.symbol} market."
        ),
        target_url=_claim_url(claim),
        metadata={"claim_id": claim.id, "amount": amount, "refunded": refunded},
        dedupe_key=f"claim-market-payout:{claim.id}:{recipient.pk}:{claim.status}",
        suppress_self=False,
    )


def notify_energy_granted(recipient: WalletUser, amount: float, dedupe_key: str):
    return notify_once(
        recipient=recipient,
        actor=None,
        type=Notification.Type.ENERGY_GRANTED,
        title="Daily energy granted",
        message=f"You received {amount:.0f} energy.",
        target_url="/feed",
        metadata={"amount": amount},
        dedupe_key=dedupe_key,
        suppress_self=False,
    )


def notify_energy_spent(
    *,
    recipient: WalletUser,
    amount: float,
    title: str,
    message: str,
    target_url: str,
    metadata: dict,
    dedupe_key: str,
):
    return notify_once(
        recipient=recipient,
        actor=recipient,
        type=Notification.Type.ENERGY_SPENT,
        title=title,
        message=message,
        target_url=target_url,
        metadata={"amount": amount, **metadata},
        dedupe_key=dedupe_key,
        suppress_self=False,
    )


def notify_position_entry(position: Position):
    return notify_once(
        recipient=position.author,
        actor=None,
        type=Notification.Type.POSITION_ENTRY_TRIGGERED,
        title="Position entry triggered",
        message=f"Your {position.asset.symbol} position is now active.",
        target_url=_position_url(position),
        metadata={"position_id": position.id, "status": position.status, "asset_symbol": position.asset.symbol},
        dedupe_key=f"position-entry:{position.id}",
        suppress_self=False,
    )


def notify_position_resolved(position: Position):
    terminal = {
        Position.Status.MISSED,
        Position.Status.CONFIRMED,
        Position.Status.REJECTED,
        Position.Status.EXPIRED,
    }
    if position.status not in terminal:
        return None
    return notify_once(
        recipient=position.author,
        actor=None,
        type=Notification.Type.POSITION_RESOLVED,
        title="Position resolved",
        message=f"Your {position.asset.symbol} position resolved as {position.status}.",
        target_url=_position_url(position),
        metadata={
            "position_id": position.id,
            "status": position.status,
            "asset_symbol": position.asset.symbol,
            "pnl_percentage": position.pnl_percentage,
        },
        dedupe_key=f"position-resolved:{position.id}:{position.status}",
        suppress_self=False,
    )
