import requests


def get_pool_info_by_id(pool_id: str) -> dict:
    base_url = 'https://api-v3.raydium.io/pools/info/ids'
    params = {'ids': pool_id}

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f'Failed to fetch pool info: {e}'}


def get_pool_info_by_mint(
        mint: str,
        pool_type: str = 'all',
        sort_field: str = 'default',
        sort_type: str = 'desc',
        page_size: int = 100,
        page: int = 1
) -> dict:
    base_url = 'https://api-v3.raydium.io/pools/info/mint'

    params = {
        'mint1': mint,
        'poolType': pool_type,
        'poolSortField': sort_field,
        'sortType': sort_type,
        'pageSize': page_size,
        'page': page
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': f'Failed to fetch pair address: {e}'}
