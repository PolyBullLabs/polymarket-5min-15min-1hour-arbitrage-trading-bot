"""
Copy Trading Strategy Configuration

This module defines the strategy for copying trades from followed traders.
Three strategies are supported:
- PERCENTAGE: Copy a fixed percentage of trader's order size
- FIXED: Copy a fixed dollar amount per trade
- ADAPTIVE: Dynamically adjust percentage based on trader's order size
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


class CopyStrategy(str, Enum):
    PERCENTAGE = 'PERCENTAGE'
    FIXED = 'FIXED'
    ADAPTIVE = 'ADAPTIVE'


@dataclass
class MultiplierTier:
    """Tier definition for tiered multipliers"""
    min: float  # Minimum trade size in USD (inclusive)
    max: Optional[float]  # Maximum trade size in USD (exclusive), None = infinity
    multiplier: float  # Multiplier to apply


@dataclass
class CopyStrategyConfig:
    """Configuration for copy trading strategy"""
    # Core strategy
    strategy: CopyStrategy

    # Main parameter (meaning depends on strategy)
    # PERCENTAGE: Percentage of trader's order (e.g., 10.0 = 10%)
    # FIXED: Fixed dollar amount per trade (e.g., 50.0 = $50)
    # ADAPTIVE: Base percentage for adaptive scaling
    copy_size: float

    # Adaptive strategy parameters (only used if strategy = ADAPTIVE)
    adaptive_min_percent: Optional[float] = None  # Minimum percentage for large orders
    adaptive_max_percent: Optional[float] = None  # Maximum percentage for small orders
    adaptive_threshold: Optional[float] = None  # Threshold in USD to trigger adaptation

    # Tiered multipliers (optional - applies to all strategies)
    # If set, multiplier is applied based on trader's order size
    tiered_multipliers: Optional[List[MultiplierTier]] = None

    # Legacy single multiplier (for backward compatibility)
    # Ignored if tiered_multipliers is set
    trade_multiplier: Optional[float] = None

    # Safety limits
    max_order_size_usd: float = 100.0  # Maximum size for a single order
    min_order_size_usd: float = 1.0  # Minimum size for a single order
    max_position_size_usd: Optional[float] = None  # Maximum total size for a position (optional)
    max_daily_volume_usd: Optional[float] = None  # Maximum total volume per day (optional)


@dataclass
class OrderSizeCalculation:
    """Result of order size calculation"""
    trader_order_size: float  # Original trader's order size
    base_amount: float  # Calculated amount before limits
    final_amount: float  # Final amount after applying limits
    strategy: CopyStrategy  # Strategy used
    capped_by_max: bool  # Whether capped by MAX_ORDER_SIZE
    reduced_by_balance: bool  # Whether reduced due to balance
    below_minimum: bool  # Whether below minimum threshold
    reasoning: str  # Human-readable explanation


def calculate_order_size(
    config: CopyStrategyConfig,
    trader_order_size: float,
    available_balance: float,
    current_position_size: float = 0.0
) -> OrderSizeCalculation:
    """Calculate order size based on copy strategy"""
    base_amount: float
    reasoning: str

    # Step 1: Calculate base amount based on strategy
    if config.strategy == CopyStrategy.PERCENTAGE:
        base_amount = trader_order_size * (config.copy_size / 100)
        reasoning = f"{config.copy_size}% of trader's ${trader_order_size:.2f} = ${base_amount:.2f}"
    elif config.strategy == CopyStrategy.FIXED:
        base_amount = config.copy_size
        reasoning = f"Fixed amount: ${base_amount:.2f}"
    elif config.strategy == CopyStrategy.ADAPTIVE:
        adaptive_percent = _calculate_adaptive_percent(config, trader_order_size)
        base_amount = trader_order_size * (adaptive_percent / 100)
        reasoning = f"Adaptive {adaptive_percent:.1f}% of trader's ${trader_order_size:.2f} = ${base_amount:.2f}"
    else:
        raise ValueError(f"Unknown strategy: {config.strategy}")

    # Step 1.5: Apply tiered or single multiplier based on trader's order size
    multiplier = get_trade_multiplier(config, trader_order_size)
    final_amount = base_amount * multiplier

    if multiplier != 1.0:
        reasoning += f" → {multiplier}x multiplier: ${base_amount:.2f} → ${final_amount:.2f}"

    capped_by_max = False
    reduced_by_balance = False
    below_minimum = False

    # Step 2: Apply maximum order size limit
    if final_amount > config.max_order_size_usd:
        final_amount = config.max_order_size_usd
        capped_by_max = True
        reasoning += f" → Capped at max ${config.max_order_size_usd}"

    # Step 3: Apply maximum position size limit (if configured)
    if config.max_position_size_usd:
        new_total_position = current_position_size + final_amount
        if new_total_position > config.max_position_size_usd:
            allowed_amount = max(0, config.max_position_size_usd - current_position_size)
            if allowed_amount < config.min_order_size_usd:
                final_amount = 0
                reasoning += " → Position limit reached"
            else:
                final_amount = allowed_amount
                reasoning += " → Reduced to fit position limit"

    # Step 4: Check available balance (with 1% safety buffer)
    max_affordable = available_balance * 0.99
    if final_amount > max_affordable:
        final_amount = max_affordable
        reduced_by_balance = True
        reasoning += f" → Reduced to fit balance (${max_affordable:.2f})"

    # Step 5: Check minimum order size
    if final_amount < config.min_order_size_usd:
        below_minimum = True
        reasoning += f" → Below minimum ${config.min_order_size_usd}"
        final_amount = config.min_order_size_usd

    return OrderSizeCalculation(
        trader_order_size=trader_order_size,
        base_amount=base_amount,
        final_amount=final_amount,
        strategy=config.strategy,
        capped_by_max=capped_by_max,
        reduced_by_balance=reduced_by_balance,
        below_minimum=below_minimum,
        reasoning=reasoning
    )


def _calculate_adaptive_percent(config: CopyStrategyConfig, trader_order_size: float) -> float:
    """
    Calculate adaptive percentage based on trader's order size

    Logic:
    - Small orders (< threshold): Use higher percentage (up to maxPercent)
    - Large orders (> threshold): Use lower percentage (down to minPercent)
    - Medium orders: Linear interpolation between copySize and min/max
    """
    min_percent = config.adaptive_min_percent or config.copy_size
    max_percent = config.adaptive_max_percent or config.copy_size
    threshold = config.adaptive_threshold or 500.0

    if trader_order_size >= threshold:
        # Large order: scale down to minPercent
        factor = min(1, trader_order_size / threshold - 1)
        return _lerp(config.copy_size, min_percent, factor)
    else:
        # Small order: scale up to maxPercent
        factor = trader_order_size / threshold
        return _lerp(max_percent, config.copy_size, factor)


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between two values"""
    return a + (b - a) * max(0, min(1, t))


def validate_copy_strategy_config(config: CopyStrategyConfig) -> List[str]:
    """Validate copy strategy configuration"""
    errors: List[str] = []

    # Validate copySize
    if config.copy_size <= 0:
        errors.append('copy_size must be positive')

    if config.strategy == CopyStrategy.PERCENTAGE and config.copy_size > 100:
        errors.append('copy_size for PERCENTAGE strategy should be <= 100')

    # Validate limits
    if config.max_order_size_usd <= 0:
        errors.append('max_order_size_usd must be positive')

    if config.min_order_size_usd <= 0:
        errors.append('min_order_size_usd must be positive')

    if config.min_order_size_usd > config.max_order_size_usd:
        errors.append('min_order_size_usd cannot be greater than max_order_size_usd')

    # Validate adaptive parameters
    if config.strategy == CopyStrategy.ADAPTIVE:
        if not config.adaptive_min_percent or not config.adaptive_max_percent:
            errors.append('ADAPTIVE strategy requires adaptive_min_percent and adaptive_max_percent')

        if config.adaptive_min_percent and config.adaptive_max_percent:
            if config.adaptive_min_percent > config.adaptive_max_percent:
                errors.append('adaptive_min_percent cannot be greater than adaptive_max_percent')

    return errors


def get_recommended_config(balance_usd: float) -> CopyStrategyConfig:
    """Get recommended configuration for different balance sizes"""
    if balance_usd < 500:
        # Small balance: Conservative
        return CopyStrategyConfig(
            strategy=CopyStrategy.PERCENTAGE,
            copy_size=5.0,
            max_order_size_usd=20.0,
            min_order_size_usd=1.0,
            max_position_size_usd=50.0,
            max_daily_volume_usd=100.0,
        )
    elif balance_usd < 2000:
        # Medium balance: Balanced
        return CopyStrategyConfig(
            strategy=CopyStrategy.PERCENTAGE,
            copy_size=10.0,
            max_order_size_usd=50.0,
            min_order_size_usd=1.0,
            max_position_size_usd=200.0,
            max_daily_volume_usd=500.0,
        )
    else:
        # Large balance: Adaptive
        return CopyStrategyConfig(
            strategy=CopyStrategy.ADAPTIVE,
            copy_size=10.0,
            adaptive_min_percent=5.0,
            adaptive_max_percent=15.0,
            adaptive_threshold=300.0,
            max_order_size_usd=100.0,
            min_order_size_usd=1.0,
            max_position_size_usd=1000.0,
            max_daily_volume_usd=2000.0,
        )


def parse_tiered_multipliers(tiers_str: str) -> List[MultiplierTier]:
    """
    Parse tiered multipliers from environment string
    Format: "1-10:2.0,10-100:1.0,100-500:0.2,500+:0.1"

    Args:
        tiers_str: Comma-separated tier definitions

    Returns:
        Array of MultiplierTier objects, sorted by min value

    Raises:
        ValueError: If format is invalid
    """
    if not tiers_str or tiers_str.strip() == '':
        return []

    tiers: List[MultiplierTier] = []
    tier_defs = [t.strip() for t in tiers_str.split(',') if t.strip()]

    for tier_def in tier_defs:
        # Format: "min-max:multiplier" or "min+:multiplier"
        parts = tier_def.split(':')
        if len(parts) != 2:
            raise ValueError(f'Invalid tier format: "{tier_def}". Expected "min-max:multiplier" or "min+:multiplier"')

        range_str, multiplier_str = parts
        try:
            multiplier = float(multiplier_str)
        except ValueError:
            raise ValueError(f'Invalid multiplier in tier "{tier_def}": {multiplier_str}')

        if multiplier < 0:
            raise ValueError(f'Invalid multiplier in tier "{tier_def}": {multiplier_str}')

        # Parse range
        if range_str.endswith('+'):
            # Infinite upper bound: "500+"
            try:
                min_val = float(range_str[:-1])
            except ValueError:
                raise ValueError(f'Invalid minimum value in tier "{tier_def}": {range_str}')
            if min_val < 0:
                raise ValueError(f'Invalid minimum value in tier "{tier_def}": {range_str}')
            tiers.append(MultiplierTier(min=min_val, max=None, multiplier=multiplier))
        elif '-' in range_str:
            # Bounded range: "100-500"
            min_str, max_str = range_str.split('-')
            try:
                min_val = float(min_str)
                max_val = float(max_str)
            except ValueError:
                raise ValueError(f'Invalid range values in tier "{tier_def}": {range_str}')

            if min_val < 0:
                raise ValueError(f'Invalid minimum value in tier "{tier_def}": {min_str}')
            if max_val <= min_val:
                raise ValueError(f'Invalid maximum value in tier "{tier_def}": {max_str} (must be > {min_val})')

            tiers.append(MultiplierTier(min=min_val, max=max_val, multiplier=multiplier))
        else:
            raise ValueError(f'Invalid range format in tier "{tier_def}". Use "min-max" or "min+"')

    # Sort tiers by min value
    tiers.sort(key=lambda t: t.min)

    # Validate no overlaps and no gaps
    for i in range(len(tiers) - 1):
        current = tiers[i]
        next_tier = tiers[i + 1]

        if current.max is None:
            raise ValueError(f'Tier with infinite upper bound must be last: {current.min}+')

        if current.max > next_tier.min:
            raise ValueError(f'Overlapping tiers: [{current.min}-{current.max}] and [{next_tier.min}-{next_tier.max or "∞"}]')

    return tiers


def get_trade_multiplier(config: CopyStrategyConfig, trader_order_size: float) -> float:
    """
    Get the appropriate multiplier for a given trade size

    Args:
        config: Copy strategy configuration
        trader_order_size: Trader's order size in USD

    Returns:
        Multiplier to apply (1.0 if no multiplier configured)
    """
    # Use tiered multipliers if configured
    if config.tiered_multipliers and len(config.tiered_multipliers) > 0:
        for tier in config.tiered_multipliers:
            if trader_order_size >= tier.min:
                if tier.max is None or trader_order_size < tier.max:
                    return tier.multiplier
        # If no tier matches, use the last tier's multiplier
        return config.tiered_multipliers[-1].multiplier

    # Fall back to single multiplier if configured
    if config.trade_multiplier is not None:
        return config.trade_multiplier

    # Default: no multiplier
    return 1.0

