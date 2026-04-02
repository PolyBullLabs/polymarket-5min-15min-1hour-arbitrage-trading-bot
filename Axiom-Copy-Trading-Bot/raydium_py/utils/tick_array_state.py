from construct import Struct, Int32sl, Int64ul, Int8ul, Int32ul, Array, Bytes, Padding, Adapter
from solders.pubkey import Pubkey  # type: ignore


class Int128Adapter(Adapter):
    def _decode(self, obj, context, path):
        value = (obj.high << 64) | obj.low
        if obj.high & (1 << 63):
            value -= 1 << 128
        return value

    def _encode(self, obj, context, path):
        if obj < 0:
            obj += 1 << 128
        high = (obj >> 64) & ((1 << 64) - 1)
        low = obj & ((1 << 64) - 1)
        return dict(high=high, low=low)


class UInt128Adapter(Adapter):
    def _decode(self, obj, context, path):
        return (obj.high << 64) | obj.low

    def _encode(self, obj, context, path):
        high = (obj >> 64) & ((1 << 64) - 1)
        low = obj & ((1 << 64) - 1)
        return dict(high=high, low=low)


Int128ul = Int128Adapter(Struct(
    'low' / Int64ul,
    'high' / Int64ul
))

UInt128ul = UInt128Adapter(Struct(
    'low' / Int64ul,
    'high' / Int64ul
))

TICK_ARRAY_SIZE_USIZE = 60
REWARD_NUM = 3

TickState = Struct(
    'tick' / Int32sl,
    'liquidity_net' / Int128ul,
    'liquidity_gross' / UInt128ul,
    'fee_growth_outside_0_x64' / UInt128ul,
    'fee_growth_outside_1_x64' / UInt128ul,
    'reward_growths_outside_x64' / Array(REWARD_NUM, UInt128ul),
    'padding' / Array(13, Int32ul),
)

TickArrayState = Struct(
    Padding(8),
    'pool_id' / Bytes(32),
    'start_tick_index' / Int32sl,
    'ticks' / Array(TICK_ARRAY_SIZE_USIZE, TickState),
    'initialized_tick_count' / Int8ul,
    'recent_epoch' / Int64ul,
    'padding' / Padding(107),
)


def parse_tick_array(data: bytes):
    parsed = TickArrayState.parse(data)
    return {
        'pool_id': str(Pubkey.from_bytes(parsed.pool_id)),
        'start_tick_index': parsed.start_tick_index,
        'initialized_tick_count': parsed.initialized_tick_count,
        'recent_epoch': parsed.recent_epoch,
        'ticks': [
            {
                'tick': tick.tick,
                'liquidity_net': tick.liquidity_net,
                'liquidity_gross': tick.liquidity_gross,
                'fee_growth_outside_0_x64': tick.fee_growth_outside_0_x64,
                'fee_growth_outside_1_x64': tick.fee_growth_outside_1_x64,
                'reward_growths_outside_x64': list(tick.reward_growths_outside_x64),
            }
            for tick in parsed.ticks
        ],
    }
