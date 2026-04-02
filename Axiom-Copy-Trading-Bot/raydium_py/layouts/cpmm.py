from construct import Struct, Int64ul, Int8ul, Bytes, Array, Padding, Int8ul, Flag, Int16ul, GreedyRange, Adapter

CPMM_POOL_STATE_LAYOUT = Struct(
    Padding(8),
    'amm_config' / Bytes(32),
    'pool_creator' / Bytes(32),
    'token_0_vault' / Bytes(32),
    'token_1_vault' / Bytes(32),
    'lp_mint' / Bytes(32),
    'token_0_mint' / Bytes(32),
    'token_1_mint' / Bytes(32),
    'token_0_program' / Bytes(32),
    'token_1_program' / Bytes(32),
    'observation_key' / Bytes(32),
    'auth_bump' / Int8ul,
    'status' / Int8ul,
    'lp_mint_decimals' / Int8ul,
    'mint_0_decimals' / Int8ul,
    'mint_1_decimals' / Int8ul,
    'lp_supply' / Int64ul,
    'protocol_fees_token_0' / Int64ul,
    'protocol_fees_token_1' / Int64ul,
    'fund_fees_token_0' / Int64ul,
    'fund_fees_token_1' / Int64ul,
    'open_time' / Int64ul,
    'padding' / Array(32, Int64ul),
    )

AMM_CONFIG_LAYOUT = Struct(
    Padding(8),
    'bump' / Int8ul,
    'disable_create_pool' / Flag,
    'index' / Int16ul,
    'trade_fee_rate' / Int64ul,
    'protocol_fee_rate' / Int64ul,
    'fund_fee_rate' / Int64ul,
    'create_pool_fee' / Int64ul,
    'protocol_owner' / Bytes(32),
    'fund_owner' / Bytes(32),
    'padding' / Array(16, Int64ul),
)


class UInt128Adapter(Adapter):
    def _decode(self, obj, context, path):
        return (obj.high << 64) | obj.low

    def _encode(self, obj, context, path):
        high = (obj >> 64) & ((1 << 64) - 1)
        low = obj & ((1 << 64) - 1)
        return dict(high=high, low=low)


UInt128ul = UInt128Adapter(Struct(
    'low' / Int64ul,
    'high' / Int64ul
))

OBSERVATION = Struct(
    'block_timestamp' / Int64ul,
    'cumulative_token_0_price_x32' / UInt128ul ,
    'cumulative_token_1_price_x32' / UInt128ul ,
)

OBSERVATION_STATE = Struct(
    Padding(8),
    'initialized' / Flag,
    'observationIndex' / Int16ul,
    'poolId' / Bytes(32),  
    'observations' / GreedyRange(OBSERVATION),
    'padding' / GreedyRange(Int64ul), 
)
