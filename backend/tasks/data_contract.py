"""Adapter-owned test data validation. No Production binding adapter exists."""
import re
from urllib.parse import urlsplit

FIXTURES = {'4242424242424242':'BOUND','4000000000000002':'DECLINED','4000000000003220':'3DS_REQUIRED','4000000000000069':'INVALID_DATA','4000000000009995':'TIMEOUT'}

def local_fixture(task):
    url = urlsplit(task['base_url'])
    return task['adapter'] == 'sandbox' and url.hostname in ('127.0.0.1','localhost','sandbox')

def validate_data(task, item):
    if task['environment'] == 'Production' or not task['authorized']:
        return '完整填写仅用于明确授权的非 Production 环境'
    if local_fixture(task) and item['number'] not in FIXTURES:
        return 'Local Sandbox 仅支持内置五种 fixture；其他授权站点使用其官方测试数据'
    if not re.fullmatch(r'\d{12,19}',item['number']):
        return '该 Adapter 需要 12–19 位官方测试卡号'
    return None
