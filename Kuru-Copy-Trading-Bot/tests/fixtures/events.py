"""Sample Kuru event log fixtures for testing."""

# OrderPlaced event log
SAMPLE_EVENT_ORDER_PLACED = {
    "address": "0xKuruContractAddress000000000000000000000",
    "topics": [
        "0xOrderPlacedEventSignature0000000000000000000000000000000000000000",
        "0x0000000000000000000000001234567890123456789012345678901234567890",  # trader address
        "0x4554482d55534443000000000000000000000000000000000000000000000000",  # market (ETH-USDC)
    ],
    "data": "0x"
    + "0000000000000000000000000000000000000000000000000000000000000001"  # order ID
    + "0000000000000000000000000000000000000000000000000000000000000001"  # side (BUY=1)
    + "00000000000000000000000000000000000000000000006c6b935b8bbd400000"  # price (2000.5 * 10^18)
    + "00000000000000000000000000000000000000000000014d1120d7b1600000"  # size (1.5 * 10^18)
    + "0000000000000000000000000000000000000000000000000000000000000001",  # order type (LIMIT=1)
    "blockNumber": 1000000,
    "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "transactionIndex": 5,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "logIndex": 0,
    "removed": False,
}

# TradeExecuted event log
SAMPLE_EVENT_TRADE_EXECUTED = {
    "address": "0xKuruContractAddress000000000000000000000",
    "topics": [
        "0xTradeExecutedEventSignature000000000000000000000000000000000000000",
        "0x0000000000000000000000001234567890123456789012345678901234567890",  # trader address
        "0x4554482d55534443000000000000000000000000000000000000000000000000",  # market (ETH-USDC)
    ],
    "data": "0x"
    + "0000000000000000000000000000000000000000000000000000000000000001"  # trade ID
    + "0000000000000000000000000000000000000000000000000000000000000001"  # side (BUY=1)
    + "00000000000000000000000000000000000000000000006c6b935b8bbd400000"  # price (2000.5 * 10^18)
    + "00000000000000000000000000000000000000000000014d1120d7b1600000"  # size (1.5 * 10^18)
    + "0000000000000000000000000000000000000000000000000000000063d0f800",  # timestamp
    "blockNumber": 1000000,
    "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "transactionIndex": 5,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "logIndex": 1,
    "removed": False,
}

# OrderCancelled event log
SAMPLE_EVENT_ORDER_CANCELLED = {
    "address": "0xKuruContractAddress000000000000000000000",
    "topics": [
        "0xOrderCancelledEventSignature00000000000000000000000000000000000000",
        "0x0000000000000000000000001234567890123456789012345678901234567890",  # trader address
    ],
    "data": "0x" + "0000000000000000000000000000000000000000000000000000000000000001",  # order ID
    "blockNumber": 1000001,
    "transactionHash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    "transactionIndex": 8,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "logIndex": 0,
    "removed": False,
}

# MarginDeposit event log
SAMPLE_EVENT_MARGIN_DEPOSIT = {
    "address": "0xKuruContractAddress000000000000000000000",
    "topics": [
        "0xMarginDepositEventSignature0000000000000000000000000000000000000000",
        "0x0000000000000000000000001234567890123456789012345678901234567890",  # trader address
    ],
    "data": "0x"
    + "000000000000000000000000USDC00000000000000000000000000000000000"  # token
    + "0000000000000000000000000000000000000000000000056bc75e2d63100000",  # amount (100 USDC)
    "blockNumber": 1000002,
    "transactionHash": "0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
    "transactionIndex": 3,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "logIndex": 0,
    "removed": False,
}

# Malformed event (missing data)
SAMPLE_EVENT_MALFORMED_NO_DATA = {
    "address": "0xKuruContractAddress000000000000000000000",
    "topics": [
        "0xOrderPlacedEventSignature0000000000000000000000000000000000000000",
    ],
    "data": "0x",  # Empty data
    "blockNumber": 1000003,
    "transactionHash": "0xmalformed000000000000000000000000000000000000000000000000000000",
    "transactionIndex": 15,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "logIndex": 0,
    "removed": False,
}

# Malformed event (invalid data format)
SAMPLE_EVENT_MALFORMED_INVALID = {
    "address": "0xKuruContractAddress000000000000000000000",
    "topics": [
        "0xTradeExecutedEventSignature000000000000000000000000000000000000000",
    ],
    "data": "0xinvalid_hex_data",  # Invalid hex
    "blockNumber": 1000004,
    "transactionHash": "0xmalformed000000000000000000000000000000000000000000000000000001",
    "transactionIndex": 20,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "logIndex": 0,
    "removed": False,
}

# List of all valid events
ALL_VALID_EVENTS = [
    SAMPLE_EVENT_ORDER_PLACED,
    SAMPLE_EVENT_TRADE_EXECUTED,
    SAMPLE_EVENT_ORDER_CANCELLED,
    SAMPLE_EVENT_MARGIN_DEPOSIT,
]

# List of malformed events (for error handling tests)
ALL_MALFORMED_EVENTS = [
    SAMPLE_EVENT_MALFORMED_NO_DATA,
    SAMPLE_EVENT_MALFORMED_INVALID,
]
