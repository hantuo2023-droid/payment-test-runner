import csv
from urllib.parse import urlsplit, unquote

def network_key(item):
    return f"{item['protocol']}|{(item.get('host') or '').lower()}|{item.get('port') or ''}|{item.get('username') or ''}"

def network_line(line):
    if '://' in line:
        u = urlsplit(line)
        if u.scheme not in ('http','socks5') or u.path not in ('','/') or u.query or u.fragment:
            raise ValueError('Unsupported URL')
        item = dict(name=f'{u.hostname}:{u.port}',protocol=u.scheme.upper(),host=u.hostname,port=u.port,username=unquote(u.username or ''),password=unquote(u.password or ''))
    else:
        p = [x.strip() for x in next(csv.reader([line],strict=True))]
        if len(p) != 6: raise ValueError('Six columns required')
        item = dict(zip(('name','protocol','host','port','username','password'),p))
        item['port'] = int(item['port'])
        item['protocol'] = item['protocol'].upper()
    return validate_network(item)


def validate_network(item):
    item = dict(item)
    item['protocol'] = item['protocol'].upper()
    item['host'] = (item.get('host') or '').strip().lower()
    try:
        item['port'] = int(item['port'])
    except (TypeError,ValueError):
        raise ValueError('节点需要有效端口') from None
    if item['protocol'] not in ('HTTP','SOCKS5') or not item['host'] or any(c in item['host'] for c in '/@:#?') or any(c.isspace() or ord(c)<32 for c in item['host']) or not 1 <= int(item['port']) <= 65535:
        raise ValueError('节点需要 HTTP/SOCKS5、有效 Host 和 1–65535 端口')
    username, password = item.get('username') or '', item.get('password') or ''
    if item['protocol'] == 'SOCKS5' and (username or password):
        if not 1 <= len(username.encode('utf-8')) <= 255 or not 1 <= len(password.encode('utf-8')) <= 255:
            raise ValueError('SOCKS5 认证需用户名与密码，各为 1–255 个 UTF-8 字节')
    if password and password in item['name']: item['name'] = f"{item['host']}:{item['port']}"
    return item


def proxy_added(db, previously_had_proxy):
    # First imported proxy replaces the initial Direct default. Later explicit
    # checkbox choices, including selecting Direct alongside proxies, are kept.
    if not previously_had_proxy:
        db.execute("UPDATE networks SET selected=0 WHERE protocol='Direct'")
