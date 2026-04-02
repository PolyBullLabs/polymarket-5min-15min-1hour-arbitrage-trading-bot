"""
User history models for MongoDB
"""
from typing import Dict, Any
from pymongo.collection import Collection
from ..config.db import get_client, get_database_name


def get_user_position_collection(wallet_address: str) -> Collection:
    """Get position collection for a specific wallet address"""
    db = get_client()[get_database_name()]
    collection_name = f'user_positions_{wallet_address}'
    return db[collection_name]


def get_user_activity_collection(wallet_address: str) -> Collection:
    """Get activity collection for a specific wallet address"""
    db = get_client()[get_database_name()]
    collection_name = f'user_activities_{wallet_address}'
    return db[collection_name]

