import struct
from solders.pubkey import Pubkey  # type: ignore
from raydium_py.raydium.constants import RAYDIUM_CLMM
from bitstring import BitArray

MIN_TICK = -443636
MAX_TICK = 443636
TICK_ARRAY_SIZE = 60
TICK_ARRAY_BITMAP_SIZE = 512
TOTAL_BITS = 1024
U1024_MASK = (1 << TOTAL_BITS) - 1


def load_current_and_next_tick_arrays(pool_id, tick_current, tick_spacing, tick_array_bitmap, tickarray_bitmap_extension, zero_for_one):
    _, current_valid_tick_array_start_index = get_first_initialized_tick_array(
        tick_current, tick_spacing, tick_array_bitmap, tickarray_bitmap_extension, zero_for_one
    )

    tick_array_keys = []
    initial_tick_array_key = get_pda_tick_array_address(pool_id, current_valid_tick_array_start_index)
    tick_array_keys.append(initial_tick_array_key)

    for _ in range(5):
        next_tick_array_index = next_initialized_tick_array_start_index(
            tick_array_bitmap, tickarray_bitmap_extension, current_valid_tick_array_start_index, tick_spacing, zero_for_one
        )

        if next_tick_array_index is None:
            break
        
        current_valid_tick_array_start_index = next_tick_array_index
        next_tick_array_key = get_pda_tick_array_address(pool_id, current_valid_tick_array_start_index)
        tick_array_keys.append(next_tick_array_key)
    
    return tick_array_keys


def get_pda_tick_array_address(pool_id: Pubkey, start_index: int):
    tick_array, _ = Pubkey.find_program_address(
        [b"tick_array", bytes(pool_id), struct.pack(">i", start_index)],
        RAYDIUM_CLMM
    )
    return tick_array


def get_pda_tick_array_bitmap_extension(pool_id: Pubkey):
    bitmap_extension, _ = Pubkey.find_program_address(
        [b"pool_tick_array_bitmap_extension", bytes(pool_id)],
        RAYDIUM_CLMM
    )
    return bitmap_extension


def next_initialized_tick(current_tick_index: int, tick_spacing: int, zero_for_one: bool, tick_array_current):
    def _get_mut(ticks, index: int):
        try:
            return ticks[index]
        except IndexError:
            return None
    
    current_tick_array_start_index = get_array_start_index(current_tick_index, tick_spacing)
    start_tick_index = tick_array_current['start_tick_index']
    ticks = tick_array_current['ticks']
    if current_tick_array_start_index != start_tick_index:
        return None

    offset_in_array = (current_tick_index - start_tick_index) // tick_spacing

    if zero_for_one:
        while offset_in_array >= 0:
            tick = _get_mut(ticks, offset_in_array)
            if tick is not None and tick['liquidity_gross'] != 0:
                return tick
            offset_in_array -= 1
    else:
        offset_in_array += 1
        while offset_in_array < len(ticks):
            tick = _get_mut(ticks, offset_in_array)
            if tick is not None and tick['liquidity_gross'] != 0:
                return tick
            offset_in_array += 1

    return None


def get_first_initialized_tick_array(tick_current, tick_spacing, tick_array_bitmap, tickarray_bitmap_extension, zero_for_one):
    tick_array_start_index = get_array_start_index(tick_current, tick_spacing)

    if is_overflow_default_tickarray_bitmap([tick_current], tick_spacing):
        is_initialized, start_index = check_tick_array_is_initialized(tick_array_start_index, tick_spacing, tickarray_bitmap_extension)
    else:
        u1024_bitmap = bitmap_list_to_u1024(tick_array_bitmap)
        is_initialized, start_index = check_current_tick_array_is_initialized(u1024_bitmap, tick_current, tick_spacing)

    if is_initialized:
        return (True, start_index)
        
    next_start_index = next_initialized_tick_array_start_index(tick_array_bitmap, tickarray_bitmap_extension, tick_array_start_index, tick_spacing, zero_for_one)
    
    return (False, next_start_index)


def is_overflow_default_tickarray_bitmap(tick_indices, tick_spacing):

    def _tick_array_start_index_range(tick_spacing):
        max_tick_boundary = tick_spacing * TICK_ARRAY_SIZE * TICK_ARRAY_BITMAP_SIZE
        min_tick_boundary = -max_tick_boundary

        if max_tick_boundary > MAX_TICK:
            max_tick_boundary = get_array_start_index(MAX_TICK, tick_spacing)
            max_tick_boundary += tick_count(tick_spacing)

        if min_tick_boundary < MIN_TICK:
            min_tick_boundary = get_array_start_index(MIN_TICK, tick_spacing)

        return min_tick_boundary, max_tick_boundary
    
    min_tick_array_start_index_boundary, max_tick_array_index_boundary = _tick_array_start_index_range(tick_spacing)

    for tick_index in tick_indices:
        tick_array_start_index = get_array_start_index(tick_index, tick_spacing)

        if (tick_array_start_index >= max_tick_array_index_boundary or tick_array_start_index < min_tick_array_start_index_boundary):
            return True

    return False


def check_tick_array_is_initialized(tick_array_start_index, tick_spacing, tickarray_bitmap_extension):

    def _calc_tick_array_offset_in_bitmap(tick_array_start_index, tick_spacing):
        m = abs(tick_array_start_index) % (tick_spacing * TICK_ARRAY_SIZE * TICK_ARRAY_BITMAP_SIZE)
        tick_array_offset_in_bitmap = m // (TICK_ARRAY_SIZE * tick_spacing)

        if tick_array_start_index < 0 and m != 0:
            tick_array_offset_in_bitmap = (
                TICK_ARRAY_BITMAP_SIZE - tick_array_offset_in_bitmap
            )
        return tick_array_offset_in_bitmap

    positive_bitmap = tickarray_bitmap_extension[0]
    negative_bitmap = tickarray_bitmap_extension[1]

    _, bitmap = get_bitmap(tick_array_start_index, tick_spacing, positive_bitmap, negative_bitmap)

    tick_array_offset = _calc_tick_array_offset_in_bitmap(tick_array_start_index, tick_spacing)

    tickarray_bitmap = BitArray(length=TICK_ARRAY_BITMAP_SIZE)

    for i, part in enumerate(bitmap):
        tickarray_bitmap.overwrite(BitArray(uint=part, length=64), (7 - i) * 64)

    initialized = tickarray_bitmap.bin[-(tick_array_offset + 1)] == "1"

    return initialized, tick_array_start_index


def bitmap_list_to_u1024(bitmap_list: list) -> int:
    if len(bitmap_list) != 16:
        raise Exception("Bitmap list must have exactly 16 elements.")
    result = 0
    # Little-endian: bitmap_list[0] is the least-significant 64 bits.
    for i, value in enumerate(bitmap_list):
        result += value << (64 * i)
    return result


def check_current_tick_array_is_initialized(bit_map: int, tick_current: int, tick_spacing: int):
    multiplier = int(tick_spacing) * TICK_ARRAY_SIZE
    compressed = int(tick_current / multiplier) + 512
    if tick_current < 0 and (tick_current % multiplier) != 0:
        compressed -= 1
    bit_pos = abs(compressed)
    mask = 1 << bit_pos
    masked = bit_map & mask
    initialized = (masked != 0)
    result_tick = (compressed - 512) * multiplier

    return (initialized, result_tick)


def next_initialized_tick_array_start_index(tick_array_bitmap, tickarray_bitmap_extension, last_tick_array_start_index, tick_spacing, zero_for_one):
    
    last_tick_array_start_index = get_array_start_index(last_tick_array_start_index, tick_spacing)
    
    iteration = 0
    while True:
        iteration += 1

        is_found, start_index = next_initialized_tick_array_start_index_in_bitmap(
            u1024_from_list(tick_array_bitmap),
            last_tick_array_start_index,
            tick_spacing,
            zero_for_one
        )

        if is_found:
            return start_index
        
        last_tick_array_start_index = start_index

        is_found, start_index = next_initialized_tick_array_from_one_bitmap(
            last_tick_array_start_index,
            tick_spacing,
            zero_for_one,
            tickarray_bitmap_extension
        )

        if is_found:
            return start_index
        
        last_tick_array_start_index = start_index
        
        if last_tick_array_start_index < MIN_TICK or last_tick_array_start_index > MAX_TICK:
            return None


def u1024_from_list(words):
    value = 0
    for i, word in enumerate(words):
        value |= word << (64 * i)
    return value & U1024_MASK


def max_tick_in_tickarray_bitmap(tick_spacing):
    return tick_spacing * TICK_ARRAY_SIZE * TICK_ARRAY_BITMAP_SIZE


def most_significant_bit(x):
    if x == 0:
        return None
    return TOTAL_BITS - x.bit_length()


def least_significant_bit(x):
    if x == 0:
        return None
    return (x & -x).bit_length() - 1


def next_initialized_tick_array_start_index_in_bitmap(bit_map, last_tick_array_start_index, tick_spacing, zero_for_one):

    if isinstance(bit_map, list):
        bit_map = u1024_from_list(bit_map)

    bit_map &= U1024_MASK

    tick_boundary = max_tick_in_tickarray_bitmap(tick_spacing)

    if zero_for_one:
        next_tick_array_start_index = last_tick_array_start_index - tick_count(tick_spacing)
    else:
        next_tick_array_start_index = last_tick_array_start_index + tick_count(tick_spacing)

    if next_tick_array_start_index < -tick_boundary or next_tick_array_start_index >= tick_boundary:
        return (False, last_tick_array_start_index)

    multiplier = tick_spacing * TICK_ARRAY_SIZE
    compressed = next_tick_array_start_index // multiplier + 512
    if next_tick_array_start_index < 0 and next_tick_array_start_index % multiplier != 0:
        compressed -= 1
    bit_pos = abs(compressed)

    if zero_for_one:

        shift_amount = TOTAL_BITS - bit_pos - 1

        offset_bit_map = (bit_map << shift_amount) & U1024_MASK

        next_bit = most_significant_bit(offset_bit_map)

        if next_bit is not None:
            next_array_start_index = (bit_pos - next_bit - 512) * multiplier

            return (True, next_array_start_index)
        else:

            return (False, -tick_boundary)
    else:

        offset_bit_map = bit_map >> bit_pos
        next_bit = least_significant_bit(offset_bit_map)
        if next_bit is not None:
            next_array_start_index = (bit_pos + next_bit - 512) * multiplier
            return (True, next_array_start_index)
        else:
            fallback = tick_boundary - tick_count(tick_spacing)
            return (False, fallback)


def next_initialized_tick_array_from_one_bitmap(last_tick_array_start_index, tick_spacing, zero_for_one, tickarray_bitmap_extension):

    multiplier = tick_count(tick_spacing)

    if zero_for_one:
        next_tick_array_start_index = last_tick_array_start_index - multiplier
    else:
        next_tick_array_start_index = last_tick_array_start_index + multiplier
        
    min_tick_array_start_index = get_array_start_index(MIN_TICK, tick_spacing)
    max_tick_array_start_index = get_array_start_index(MAX_TICK, tick_spacing)

    if (next_tick_array_start_index < min_tick_array_start_index or
        next_tick_array_start_index > max_tick_array_start_index):
        return (False, next_tick_array_start_index)

    positive_bitmap = tickarray_bitmap_extension[0]
    negative_bitmap = tickarray_bitmap_extension[1]

    _, tickarray_bitmap = get_bitmap(next_tick_array_start_index, tick_spacing, positive_bitmap, negative_bitmap)
    
    next_initialized_tick_array = next_initialized_tick_array_in_bitmap(tickarray_bitmap, next_tick_array_start_index, tick_spacing, zero_for_one)

    return next_initialized_tick_array


def next_initialized_tick_array_in_bitmap(
    tickarray_bitmap,
    next_tick_array_start_index: int,
    tick_spacing: int,
    zero_for_one: bool,
):
    def _u512_is_zero(x: int) -> bool:
        return x == 0

    def _u512_leading_zeros(x: int) -> int:
        if x == 0:
            return 512
        return 512 - x.bit_length()

    def _u512_trailing_zeros(x: int) -> int:
        if x == 0:
            return 512
        return (x & -x).bit_length() - 1

    def _calc_tick_array_offset_in_bitmap(tick_array_start_index, tick_spacing):
        m = abs(tick_array_start_index) % (tick_spacing * TICK_ARRAY_SIZE * TICK_ARRAY_BITMAP_SIZE)
        tick_array_offset_in_bitmap = m // (TICK_ARRAY_SIZE * tick_spacing)

        if tick_array_start_index < 0 and m != 0:
            tick_array_offset_in_bitmap = TICK_ARRAY_BITMAP_SIZE - tick_array_offset_in_bitmap
        return tick_array_offset_in_bitmap

    def _get_bitmap_tick_boundary(tick_array_start_index, tick_spacing):
        ticks_in_one_bitmap = tick_spacing * TICK_ARRAY_SIZE * TICK_ARRAY_BITMAP_SIZE
        m = abs(tick_array_start_index) // ticks_in_one_bitmap
        if tick_array_start_index < 0 and abs(tick_array_start_index) % ticks_in_one_bitmap != 0:
            m += 1
        min_value = ticks_in_one_bitmap * m
        if tick_array_start_index < 0:
            return -min_value, -min_value + ticks_in_one_bitmap
        else:
            return min_value, min_value + ticks_in_one_bitmap

    bitmap_min_tick_boundary, bitmap_max_tick_boundary = _get_bitmap_tick_boundary(next_tick_array_start_index, tick_spacing)
    tick_array_offset = _calc_tick_array_offset_in_bitmap(next_tick_array_start_index, tick_spacing)

    u512_tickarray_bitmap = BitArray(length=TICK_ARRAY_BITMAP_SIZE)
    
    for i, part in enumerate(tickarray_bitmap):
        u512_tickarray_bitmap.overwrite(BitArray(uint=part, length=64), (7 - i) * 64)

    if zero_for_one:
        offset_bit_map = u512_tickarray_bitmap << (TICK_ARRAY_BITMAP_SIZE - 1 - tick_array_offset)
        offset_int = offset_bit_map.uint

        if _u512_is_zero(offset_int):
            next_bit = None
        else:
            next_bit = _u512_leading_zeros(offset_int)
        if next_bit is not None:
            next_array_start_index = next_tick_array_start_index - next_bit * tick_count(tick_spacing)
            return (True, next_array_start_index)
        else:
            return (False, bitmap_min_tick_boundary)
    else:
        offset_bit_map = u512_tickarray_bitmap >> tick_array_offset
        offset_int = offset_bit_map.uint

        if _u512_is_zero(offset_int):
            next_bit = None
        else:
            next_bit = _u512_trailing_zeros(offset_int)
        if next_bit is not None:
            next_array_start_index = next_tick_array_start_index + next_bit * tick_count(tick_spacing)
            return (True, next_array_start_index)
        else:
            return (False, bitmap_max_tick_boundary - tick_count(tick_spacing))


def get_bitmap(tick_index, tick_spacing, positive_bitmap, negative_bitmap):
    ticks_in_one_bitmap = tick_spacing * TICK_ARRAY_SIZE * TICK_ARRAY_BITMAP_SIZE
    offset = abs(tick_index) // ticks_in_one_bitmap - 1
    
    if tick_index < 0 and abs(tick_index) % ticks_in_one_bitmap == 0:
        offset -= 1
    
    if tick_index < 0:
        return offset, negative_bitmap[offset]
    else:
        return offset, positive_bitmap[offset]


def tick_count(tick_spacing):
    return TICK_ARRAY_SIZE * tick_spacing


def get_array_start_index(tick_index, tick_spacing):
    ticks_in_array = tick_count(tick_spacing)
    start = tick_index // ticks_in_array
    if tick_index < 0 and tick_index % ticks_in_array != 0:
        start -= 1
    return start * ticks_in_array
