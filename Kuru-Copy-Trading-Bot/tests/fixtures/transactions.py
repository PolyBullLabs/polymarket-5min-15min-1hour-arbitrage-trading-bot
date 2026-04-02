"""Sample blockchain transaction data fixtures for testing."""

from datetime import datetime, timezone

# Sample transaction with Kuru interaction
SAMPLE_TRANSACTION_KURU = {
    "hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "from": "0x1234567890123456789012345678901234567890",
    "to": "0xKuruContractAddress000000000000000000000",  # Placeholder for Kuru contract
    "value": 0,
    "gas": 300000,
    "gasPrice": 20000000000,  # 20 Gwei
    "nonce": 10,
    "blockNumber": 1000000,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "transactionIndex": 5,
    "input": "0x1234abcd",  # Contract call data
    "timestamp": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
}

# Transaction receipt with logs
SAMPLE_TRANSACTION_RECEIPT = {
    "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "transactionIndex": 5,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "blockNumber": 1000000,
    "from": "0x1234567890123456789012345678901234567890",
    "to": "0xKuruContractAddress000000000000000000000",
    "cumulativeGasUsed": 250000,
    "gasUsed": 200000,
    "contractAddress": None,
    "logs": [
        {
            "address": "0xKuruContractAddress000000000000000000000",
            "topics": [
                "0xOrderPlacedEventSignature0000000000000000000000000000000000000000",
                "0x0000000000000000000000001234567890123456789012345678901234567890",  # trader
            ],
            "data": "0x000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000056bc75e2d63100000",  # order data
            "blockNumber": 1000000,
            "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "transactionIndex": 5,
            "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
            "logIndex": 0,
            "removed": False,
        }
    ],
    "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "status": 1,  # Success
}

# Failed transaction receipt
SAMPLE_TRANSACTION_RECEIPT_FAILED = {
    "transactionHash": "0xfailed1234567890failed1234567890failed1234567890failed1234567890fa",
    "transactionIndex": 10,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "blockNumber": 1000001,
    "from": "0x1234567890123456789012345678901234567890",
    "to": "0xKuruContractAddress000000000000000000000",
    "cumulativeGasUsed": 100000,
    "gasUsed": 100000,
    "contractAddress": None,
    "logs": [],
    "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "status": 0,  # Failed
}

# Non-Kuru transaction (should be filtered out)
SAMPLE_TRANSACTION_NON_KURU = {
    "hash": "0xnon_kuru000000000000000000000000000000000000000000000000000000000",
    "from": "0x1234567890123456789012345678901234567890",
    "to": "0xOtherContract00000000000000000000000000",
    "value": 1000000000000000000,  # 1 ETH
    "gas": 21000,
    "gasPrice": 20000000000,
    "nonce": 11,
    "blockNumber": 1000002,
    "blockHash": "0xblock1234567890block1234567890block1234567890block1234567890block",
    "transactionIndex": 8,
    "input": "0x",
    "timestamp": datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
}

# List of all sample transactions
ALL_TRANSACTIONS = [
    SAMPLE_TRANSACTION_KURU,
    SAMPLE_TRANSACTION_NON_KURU,
]

# List of all sample receipts
ALL_RECEIPTS = [
    SAMPLE_TRANSACTION_RECEIPT,
    SAMPLE_TRANSACTION_RECEIPT_FAILED,
]
