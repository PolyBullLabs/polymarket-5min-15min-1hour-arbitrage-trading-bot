from construct import Int64ul, Padding, Struct, Bytes, Array

EXTENSION_TICKARRAY_BITMAP_SIZE = 14

TickArrayBitmapExtension = Struct(
    Padding(8),
    'pool_id' / Bytes(32),  
    'positive_tick_array_bitmap' / Array(
        EXTENSION_TICKARRAY_BITMAP_SIZE,
        Array(8, Int64ul)
    ),
    'negative_tick_array_bitmap' / Array(
        EXTENSION_TICKARRAY_BITMAP_SIZE,
        Array(8, Int64ul)
    )
)
