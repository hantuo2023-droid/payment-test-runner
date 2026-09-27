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
    if item['protocol'] not in ('HTTP','SOCKS5') or not item['host'] or any(c in item['host'] for c in '/@:#? ') or not item['port'] or not 1 <= item['port'] <= 65535:
        raise ValueError('Invalid host or port')
    if item['protocol'] == 'SOCKS5' and (item['username'] or item['password']):
        raise ValueError('Chromium does not support authenticated SOCKS5')
    item['host'] = item['host'].lower()
    if item['password'] and item['password'] in item['name']: item['name'] = f"{item['host']}:{item['port']}"
    return item
