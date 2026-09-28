import asyncio
import pytest
from backend.tests.test_api import client
from backend.store import rows, execute, seed, unseal, seal
from backend.runs import Plan, chosen, signature
from backend.network_import import network_line
from backend.network_transport import BrowserNetwork
from backend.tests.socks_proxy import SocksProxy


@pytest.fixture
def netclient(client):
    execute('DELETE FROM networks')
    seed()
    yield client
    execute('DELETE FROM networks')
    seed()


def test_authenticated_socks_import_and_direct_default(netclient):
    c = netclient
    direct = c.get('/api/networks').json()[0]['id']
    assert chosen(Plan(task_id=1))['networks'] == [direct]
    p = c.post('/api/import/preview',json={'kind':'networks','text':'socks5://fixture-user:fixture-password@localhost:1080'}).json()
    assert p['valid']==1 and not p['errors'] and 'fixture-password' not in str(p)
    assert c.post('/api/import/confirm',json={'preview_id':p['preview_id']}).json()['imported']==1
    node=next(n for n in c.get('/api/networks').json() if n['protocol']=='SOCKS5')
    assert chosen(Plan(task_id=1))['networks']==[node['id']]
    assert unseal(rows('SELECT secret FROM networks WHERE id=?',(node['id'],))[0]['secret'])=='fixture-password'
    # Explicit Direct selection persists across subsequent import and seed/restart.
    c.post('/api/pools/networks/selection',json={'ids':[direct],'selected':True})
    c.post('/api/networks',json={'name':'second','protocol':'HTTP','host':'localhost','port':1090})
    seed()
    assert direct in chosen(Plan(task_id=1))['networks']
    selected=[n['id'] for n in c.get('/api/networks').json() if n['protocol']!='Direct']
    assert c.post('/api/networks/delete',json={'ids':selected,'confirmed':True}).status_code==200
    assert chosen(Plan(task_id=1))['networks']==[direct]


def test_edit_credentials_resets_health_and_invalidates_proof(netclient):
    c=netclient
    config={'name':'authenticated','protocol':'SOCKS5','host':'LOCALHOST','port':1080,'username':'fixture-user','password':'old-password'}
    nid=c.post('/api/networks',json=config).json()['id']
    execute("UPDATE networks SET status='CONNECTED',latency_ms=12,checked_at='old',check_task_id=1,check_task_version=1 WHERE id=?",(nid,))
    old=rows('SELECT * FROM networks WHERE id=?',(nid,))[0]
    before=signature({},dict(accounts=[],cards=[],networks=[old]))
    # Keep password when absent, never return the old value in the editor payload.
    assert c.put(f'/api/networks/{nid}',json=dict(config,password=None,name='renamed')).status_code==200
    saved=rows('SELECT * FROM networks WHERE id=?',(nid,))[0]
    assert saved['secret']==old['secret'] and saved['status']=='UNKNOWN' and saved['latency_ms'] is None
    assert saved['checked_at'] is None and saved['check_task_version'] is None
    assert c.put(f'/api/networks/{nid}',json=dict(config,password='new-password')).status_code==200
    saved=rows('SELECT * FROM networks WHERE id=?',(nid,))[0]
    assert unseal(saved['secret'])=='new-password'
    assert signature({},dict(accounts=[],cards=[],networks=[saved]))!=before
    for endpoint in ('/api/networks','/api/networks/export'):
        output=c.get(endpoint).text
        assert 'old-password' not in output and 'new-password' not in output
    assert c.put(f'/api/networks/{nid}',json=dict(config,username='',password='')).status_code==200
    assert unseal(rows('SELECT secret FROM networks WHERE id=?',(nid,))[0]['secret'])==''


def test_network_edit_conflicts_and_validation(netclient):
    c=netclient
    config={'name':'one','protocol':'HTTP','host':'localhost','port':1081}
    first=c.post('/api/networks',json=config).json()['id']
    second=c.post('/api/networks',json=dict(config,port=1082)).json()['id']
    assert c.put(f'/api/networks/{second}',json=config).status_code==409
    direct=next(n['id'] for n in c.get('/api/networks').json() if n['protocol']=='Direct')
    assert c.put(f'/api/networks/{direct}',json=config).status_code==400
    for credentials in ({'username':'user','password':''},{'username':'','password':'sensitive'},{'username':'user','password':'密'*86}):
        response=c.put(f'/api/networks/{first}',json=dict(config,protocol='SOCKS5',**credentials))
        assert response.status_code==400 and 'sensitive' not in response.text and '密'*86 not in response.text
    parsed=network_line('node,SOCKS5,localhost,1080,user,"pass,word"')
    assert parsed['password']=='pass,word'
    for value in ('socks5://localhost','http://:1080'):
        with pytest.raises(ValueError):network_line(value)


def test_authenticated_relay_no_direct_fallback_and_cleanup():
    async def check():
        requests=[]
        async def target(reader,writer):
            requests.append(await reader.readexactly(4))
            writer.write(b'PONG');await writer.drain();writer.close()
        server=await asyncio.start_server(target,'127.0.0.1',0)
        port=server.sockets[0].getsockname()[1]
        proxy=SocksProxy(port).start()
        config={'protocol':'SOCKS5','host':'127.0.0.1','port':proxy.port,'username':'fixture-user','secret':seal('fixture-password')}
        async def connection(relay, domain=False):
            settings=await relay.start()
            local_port=int(settings['server'].rsplit(':',1)[1])
            reader,writer=await asyncio.open_connection('127.0.0.1',local_port)
            writer.write(b'\x05\x01\x00');await writer.drain()
            assert await reader.readexactly(2)==b'\x05\x00'
            address=b'\x03\x09localhost' if domain else b'\x01\x7f\x00\x00\x01'
            writer.write(b'\x05\x01\x00'+address+port.to_bytes(2,'big'));await writer.drain()
            return reader,writer,local_port
        try:
            for domain in (False,True):
                relay=BrowserNetwork(config)
                reader,writer,local_port=await connection(relay,domain)
                assert (await reader.readexactly(10))[1]==0
                writer.write(b'PING');await writer.drain()
                assert await reader.readexactly(4)==b'PONG'
                writer.close();await relay.close()
                with pytest.raises(OSError):await asyncio.open_connection('127.0.0.1',local_port)
                assert not relay.tasks and not relay.writers
            bad=BrowserNetwork(dict(config,secret=seal('incorrect')))
            reader,writer,_=await connection(bad)
            assert (await reader.readexactly(10))[1]!=0
            writer.close();await bad.close()
            assert requests==[b'PING',b'PING'] and proxy.rejected==1
            # A browser may leave an idle or incomplete connection when stopped.
            idle=BrowserNetwork(config)
            settings=await idle.start()
            thread=idle.thread
            reader,writer=await asyncio.open_connection('127.0.0.1',int(settings['server'].rsplit(':',1)[1]))
            writer.write(b'\x05');await writer.drain()
            await asyncio.wait_for(idle.close(),timeout=3)
            try:
                assert await asyncio.wait_for(reader.read(),timeout=1)==b''
            except ConnectionResetError:
                pass  # Closing an unread partial greeting may reset the peer.
            assert not thread.is_alive() and not idle.tasks and not idle.writers
            writer.close()
        finally:
            proxy.stop();server.close();await server.wait_closed()
    asyncio.run(check())


def test_old_probe_cannot_restore_health_after_credentials_changed(netclient,monkeypatch):
    from backend import runs
    config={'name':'probe race','protocol':'SOCKS5','host':'localhost','port':1080,'username':'fixture-user','password':'old-password'}
    nid=netclient.post('/api/networks',json=config).json()['id']
    old=rows('SELECT * FROM networks WHERE id=?',(nid,))[0]
    async def delayed_probe(task,network):
        execute("UPDATE networks SET secret=?,status='UNKNOWN' WHERE id=?",(seal('new-password'),nid))
        return {'chromium':True,'connected':True,'latency_ms':1,'reason':''}
    monkeypatch.setattr(runs,'probe_browser',delayed_probe)
    report=asyncio.run(runs.probe_pool({'id':1,'version':1},[old]))
    assert not report[0]['connected']
    assert rows('SELECT status FROM networks WHERE id=?',(nid,))[0]['status']=='UNKNOWN'
