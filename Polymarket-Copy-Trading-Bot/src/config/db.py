"""
Database configuration and connection management
"""
import re
import sys
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from .env import ENV

client: MongoClient = None
database_name: str = 'polymarket_copytrading'  # Default database name


def extract_database_name(uri: str) -> str:
    """Extract database name from MongoDB URI"""
    # Try to extract database name from URI
    # Format: mongodb://.../database_name or mongodb+srv://.../database_name
    # Look for the last / that's not part of the protocol or path before query params
    # Pattern: find /database_name (not followed by @ or before ?)
    
    # First, remove query parameters
    uri_without_params = uri.split('?')[0]
    
    # Split by / and look for the database name (after the last meaningful /)
    # For mongodb://host:port/db or mongodb+srv://cluster/db
    parts = uri_without_params.split('/')
    
    # Find the database name part (after protocol, credentials, host/port)
    # For mongodb://user:pass@host:port/db -> parts would be ['mongodb:', '', 'user:pass@host:port', 'db']
    # For mongodb+srv://cluster/db -> parts would be ['mongodb+srv:', '', 'cluster', 'db']
    
    if len(parts) >= 4 and parts[3]:  # Database name is usually at index 3
        db_name = parts[3]
        # Make sure it's not empty and doesn't contain @ (which would be part of credentials)
        if db_name and '@' not in db_name:
            return db_name
    
    return 'polymarket_copytrading'  # Default if not found


async def connect_db() -> None:
    """Connect to MongoDB"""
    global client, database_name
    try:
        uri = ENV.MONGO_URI or 'mongodb://localhost:27017/polymarket_copytrading'
        # Extract database name from URI
        database_name = extract_database_name(uri)
        client = MongoClient(uri)
        # Test connection
        client.admin.command('ping')
        try:
            from colorama import Fore, Style
            print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} MongoDB connected')
        except ImportError:
            print('[SUCCESS] MongoDB connected')
    except ConnectionFailure as error:
        try:
            from colorama import Fore, Style
            print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} MongoDB connection failed: {error}', file=sys.stderr)
        except ImportError:
            print(f'[ERROR] MongoDB connection failed: {error}', file=sys.stderr)
        raise


def close_db() -> None:
    """Close MongoDB connection gracefully"""
    global client
    try:
        if client:
            client.close()
            try:
                from colorama import Fore, Style
                print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} MongoDB connection closed')
            except ImportError:
                print('[SUCCESS] MongoDB connection closed')
    except Exception as error:
        try:
            from colorama import Fore, Style
            print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} Error closing MongoDB connection: {error}', file=sys.stderr)
        except ImportError:
            print(f'[ERROR] Error closing MongoDB connection: {error}', file=sys.stderr)


def get_client() -> MongoClient:
    """Get MongoDB client instance"""
    if client is None:
        raise RuntimeError('Database not connected. Call connect_db() first.')
    return client


def get_database_name() -> str:
    """Get the database name"""
    return database_name

