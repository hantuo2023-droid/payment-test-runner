"""Deployment-owned exact-origin authorization for non-production binding."""
import os
from urllib.parse import urlsplit


def origin(value):
    u = urlsplit(value)
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
        raise ValueError('无效 HTTP(S) origin')
    return (u.scheme, u.hostname.lower(), u.port or (443 if u.scheme == 'https' else 80))


def authorized_origins():
    values = [os.getenv('PTR_SANDBOX_URL', 'http://127.0.0.1:8080')]
    values += os.getenv('PTR_AUTHORIZED_ORIGINS', '').split(',')
    result = set()
    for value in values:
        if not value.strip():
            continue
        u = urlsplit(value.strip())
        if u.path not in ('', '/') or u.query or u.fragment:
            raise ValueError('授权列表必须使用完整 origin，不含路径或查询参数')
        result.add(origin(value.strip()))
    return result


def binding_error(task):
    if task['environment'] == 'Production':
        return None
    if not task['authorized']:
        return '请确认对测试环境的授权'
    try:
        origins = {origin(task[k]) for k in ('base_url', 'login_url', 'target_url')}
        if len(origins) != 1 or not origins <= authorized_origins():
            return '测试站点未列入服务器授权范围，请管理员配置 PTR_AUTHORIZED_ORIGINS'
        if any(host == 'preply.com' or host.endswith('.preply.com') for _, host, _ in origins):
            return 'Preply 真实站点仅支持 Production UI 验证'
    except ValueError:
        return '授权站点配置无效，请管理员检查 origin 配置'
    return None


async def restrict_context(context, task):
    if task['environment'] == 'Production':
        return
    allowed = origin(task['base_url'])
    async def guard(route):
        try:
            permitted = origin(route.request.url) == allowed
        except ValueError:
            permitted = False
        if permitted:
            await route.continue_()
        else:
            await route.abort('blockedbyclient')
    await context.route('**/*', guard)
