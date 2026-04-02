from construct import Int32ul, Struct, Int8ul, Int16ul, Int64ul, Int32sl, Bytes, Array, Flag, Padding, Adapter


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
    'cumulative_token_0_price_x32' / UInt128ul,
    'cumulative_token_1_price_x32' / UInt128ul
)

AMM_CONFIG_LAYOUT = Struct(
    Padding(8),
    'bump' / Int8ul,
    'index' / Int16ul,
    'owner' / Bytes(32),
    'protocol_fee_rate' / Int32ul,
    'trade_fee_rate' / Int32ul,
    'tick_spacing' / Int16ul,
    'fund_fee_rate' / Int32ul,
    'padding_u32' / Int32ul,
    'fund_owner' / Bytes(32),
    'padding' / Array(3, Int64ul)
)

OBSERVATION_STATE_LAYOUT = Struct(
    'initialized' / Flag,
    'pool_id' / Bytes(32),
    'observations' / Array(1000, OBSERVATION),
    'padding' / Array(5, UInt128ul)
)

POSITION_REWARD_INFO = Struct(
    'reward_amount' / UInt128ul,
    'reward_growth_inside' / UInt128ul
)

PERSONAL_POSITION_STATE_LAYOUT = Struct(
    Padding(8),
    'bump' / Int8ul,
    'nft_mint' / Bytes(32),
    'pool_id' / Bytes(32),
    'tick_lower_index' / Int32sl,
    'tick_upper_index' / Int32sl,
    'liquidity' / UInt128ul,
    'fee_growth_inside_0_last_x64' / UInt128ul,
    'fee_growth_inside_1_last_x64' / UInt128ul,
    'token_fees_owed_0' / Int64ul,
    'token_fees_owed_1' / Int64ul,
    'reward_infos' / Array(3, POSITION_REWARD_INFO),
    'padding' / Array(8, Int64ul)
)

CLMM_POOL_STATE_LAYOUT = Struct(
    Padding(8),
    'bump' / Int8ul,
    'amm_config' / Bytes(32),
    'owner' / Bytes(32),
    'token_mint_0' / Bytes(32),
    'token_mint_1' / Bytes(32),
    'token_vault_0' / Bytes(32),
    'token_vault_1' / Bytes(32),
    'observation_key' / Bytes(32),
    'mint_decimals_0' / Int8ul,
    'mint_decimals_1' / Int8ul,
    'tick_spacing' / Int16ul,
    'liquidity' / UInt128ul,
    'sqrt_price_x64' / UInt128ul,
    'tick_current' / Int32sl,
    'observation_index' / Int16ul,
    'observation_update_duration' / Int16ul,
    'fee_growth_global_0_x64' / UInt128ul,
    'fee_growth_global_1_x64' / UInt128ul,
    'protocol_fees_token_0' / Int64ul,
    'protocol_fees_token_1' / Int64ul,
    'swap_in_amount_token_0' / UInt128ul,
    'swap_out_amount_token_1' / UInt128ul,
    'swap_in_amount_token_1' / UInt128ul,
    'swap_out_amount_token_0' / UInt128ul,
    'status' / Int8ul,
    Padding(7),
    Padding(507), # I need help decoding this part - skipping for now...
    'tick_array_bitmap' / Array(16, Int64ul),
    'total_fees_token_0' / Int64ul,
    'total_fees_claimed_token_0' / Int64ul,
    'total_fees_token_1' / Int64ul,
    'total_fees_claimed_token_1' / Int64ul,
    'fund_fees_token_0' / Int64ul,
    'fund_fees_token_1' / Int64ul,
    'padding1' / Array(26, Int64ul),
    'padding2' / Array(32, Int64ul)
)

TICK_ARRAY_STATE_LAYOUT = Struct(
    'pool_id' / Bytes(32),
    'start_tick_index' / Int32sl,
    'ticks' / Array(60, Struct(
        'tick_index' / Int32sl,
        'liquidity_net' / Int64ul,
        'liquidity_gross' / UInt128ul
    )),
    'initialized_tick_count' / Int8ul,
    'padding' / Array(115, Int8ul)
)

PROTOCOL_POSITION_STATE_LAYOUT = Struct(
    Padding(8),
    'bump' / Int8ul,
    'pool_id' / Bytes(32),
    'tick_lower_index' / Int32sl,
    'tick_upper_index' / Int32sl,
    'liquidity' / UInt128ul,
    'fee_growth_inside_0_last_x64' / UInt128ul,
    'fee_growth_inside_1_last_x64' / UInt128ul,
    'token_fees_owed_0' / Int64ul,
    'token_fees_owed_1' / Int64ul,
    'reward_growth_inside' / Array(3, UInt128ul),
    'padding' / Array(8, Int64ul)
)
