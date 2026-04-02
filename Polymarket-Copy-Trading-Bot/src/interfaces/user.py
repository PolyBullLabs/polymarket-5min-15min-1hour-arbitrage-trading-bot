"""
User interface types
"""
from typing import Optional
from bson import ObjectId


class UserActivityInterface:
    """Interface for user activity/trade data"""
    def __init__(self, data: dict):
        self._id: Optional[ObjectId] = data.get('_id')
        self.proxy_wallet: Optional[str] = data.get('proxyWallet')
        self.timestamp: Optional[int] = data.get('timestamp')
        self.condition_id: Optional[str] = data.get('conditionId')
        self.type: Optional[str] = data.get('type')
        self.size: Optional[float] = data.get('size')
        self.usdc_size: Optional[float] = data.get('usdcSize')
        self.transaction_hash: Optional[str] = data.get('transactionHash')
        self.price: Optional[float] = data.get('price')
        self.asset: Optional[str] = data.get('asset')
        self.side: Optional[str] = data.get('side')
        self.outcome_index: Optional[int] = data.get('outcomeIndex')
        self.title: Optional[str] = data.get('title')
        self.slug: Optional[str] = data.get('slug')
        self.icon: Optional[str] = data.get('icon')
        self.event_slug: Optional[str] = data.get('eventSlug')
        self.outcome: Optional[str] = data.get('outcome')
        self.name: Optional[str] = data.get('name')
        self.pseudonym: Optional[str] = data.get('pseudonym')
        self.bio: Optional[str] = data.get('bio')
        self.profile_image: Optional[str] = data.get('profileImage')
        self.profile_image_optimized: Optional[str] = data.get('profileImageOptimized')
        self.bot: Optional[bool] = data.get('bot', False)
        self.bot_executed_time: Optional[int] = data.get('botExcutedTime', 0)
        self.my_bought_size: Optional[float] = data.get('myBoughtSize')

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            '_id': self._id,
            'proxyWallet': self.proxy_wallet,
            'timestamp': self.timestamp,
            'conditionId': self.condition_id,
            'type': self.type,
            'size': self.size,
            'usdcSize': self.usdc_size,
            'transactionHash': self.transaction_hash,
            'price': self.price,
            'asset': self.asset,
            'side': self.side,
            'outcomeIndex': self.outcome_index,
            'title': self.title,
            'slug': self.slug,
            'icon': self.icon,
            'eventSlug': self.event_slug,
            'outcome': self.outcome,
            'name': self.name,
            'pseudonym': self.pseudonym,
            'bio': self.bio,
            'profileImage': self.profile_image,
            'profileImageOptimized': self.profile_image_optimized,
            'bot': self.bot,
            'botExcutedTime': self.bot_executed_time,
            'myBoughtSize': self.my_bought_size,
        }


class UserPositionInterface:
    """Interface for user position data"""
    def __init__(self, data: dict):
        self._id: Optional[ObjectId] = data.get('_id')
        self.proxy_wallet: Optional[str] = data.get('proxyWallet')
        self.asset: Optional[str] = data.get('asset')
        self.condition_id: Optional[str] = data.get('conditionId')
        self.size: Optional[float] = data.get('size')
        self.avg_price: Optional[float] = data.get('avgPrice')
        self.initial_value: Optional[float] = data.get('initialValue')
        self.current_value: Optional[float] = data.get('currentValue')
        self.cash_pnl: Optional[float] = data.get('cashPnl')
        self.percent_pnl: Optional[float] = data.get('percentPnl')
        self.total_bought: Optional[float] = data.get('totalBought')
        self.realized_pnl: Optional[float] = data.get('realizedPnl')
        self.percent_realized_pnl: Optional[float] = data.get('percentRealizedPnl')
        self.cur_price: Optional[float] = data.get('curPrice')
        self.redeemable: Optional[bool] = data.get('redeemable')
        self.mergeable: Optional[bool] = data.get('mergeable')
        self.title: Optional[str] = data.get('title')
        self.slug: Optional[str] = data.get('slug')
        self.icon: Optional[str] = data.get('icon')
        self.event_slug: Optional[str] = data.get('eventSlug')
        self.outcome: Optional[str] = data.get('outcome')
        self.outcome_index: Optional[int] = data.get('outcomeIndex')
        self.opposite_outcome: Optional[str] = data.get('oppositeOutcome')
        self.opposite_asset: Optional[str] = data.get('oppositeAsset')
        self.end_date: Optional[str] = data.get('endDate')
        self.negative_risk: Optional[bool] = data.get('negativeRisk')

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            '_id': self._id,
            'proxyWallet': self.proxy_wallet,
            'asset': self.asset,
            'conditionId': self.condition_id,
            'size': self.size,
            'avgPrice': self.avg_price,
            'initialValue': self.initial_value,
            'currentValue': self.current_value,
            'cashPnl': self.cash_pnl,
            'percentPnl': self.percent_pnl,
            'totalBought': self.total_bought,
            'realizedPnl': self.realized_pnl,
            'percentRealizedPnl': self.percent_realized_pnl,
            'curPrice': self.cur_price,
            'redeemable': self.redeemable,
            'mergeable': self.mergeable,
            'title': self.title,
            'slug': self.slug,
            'icon': self.icon,
            'eventSlug': self.event_slug,
            'outcome': self.outcome,
            'outcomeIndex': self.outcome_index,
            'oppositeOutcome': self.opposite_outcome,
            'oppositeAsset': self.opposite_asset,
            'endDate': self.end_date,
            'negativeRisk': self.negative_risk,
        }

