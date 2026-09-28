"""Ephemeral loopback SOCKS5 relay for Chromium's unsupported proxy auth.

Only CONNECT is supported. Destinations and traffic always go through the
configured upstream; authentication/connection errors never fall back to Direct.
"""
import asyncio
import threading
from backend.store import unseal


async def socks_address(reader, atyp):
    if atyp == 1:
        return await reader.readexactly(4)
    if atyp == 4:
        return await reader.readexactly(16)
    if atyp == 3:
        length = await reader.readexactly(1)
        if not length[0]:
            raise ValueError('Empty SOCKS destination')
        return length + await reader.readexactly(length[0])
    raise ValueError('Unsupported SOCKS address')


class BrowserNetwork:
    def __init__(self, network):
        self.network = network
        self.server = None
        self.tasks = set()
        self.writers = set()
        self.closed = False
        self.loop = None
        self.thread = None

    async def start(self):
        # Keep socket relay I/O on a selector loop. Windows Proactor transports
        # can fail to detach reset connections during shutdown (Python 3.12).
        # Playwright retains its normal subprocess-capable event loop.
        if self.network['protocol'] == 'SOCKS5' and self.network.get('username'):
            self.loop = asyncio.SelectorEventLoop()
            self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
            self.thread.start()
            return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(self._start(), self.loop))
        return await self._start()

    async def _start(self):
        n = self.network
        if n['protocol'] == 'Direct':
            return None
        if n['protocol'] == 'SOCKS5' and n.get('username'):
            self.server = await asyncio.start_server(self.accept, '127.0.0.1', 0, limit=65536)
            port = self.server.sockets[0].getsockname()[1]
            return {'server': f'socks5://127.0.0.1:{port}', 'bypass': '<-loopback>'}
        scheme = 'http' if n['protocol'] == 'HTTP' else 'socks5'
        config = {'server': f'{scheme}://{n["host"]}:{n["port"]}', 'bypass': '<-loopback>'}
        password = unseal(n['secret']) if n.get('secret') else ''
        if n.get('username') or password:
            config.update(username=n.get('username') or '', password=password)
        return config

    def accept(self, reader, writer):
        if self.closed or len(self.tasks) >= 128:
            writer.close()
            return
        self.writers.add(writer)
        task = asyncio.create_task(self.serve(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def serve(self, reader, writer):
        upstream = None
        try:
            # Bound incomplete greetings, authentication and connection setup.
            async with asyncio.timeout(10):
                version, count = await reader.readexactly(2)
                methods = await reader.readexactly(count)
                if version != 5 or 0 not in methods:
                    writer.write(b'\x05\xff')
                    await writer.drain()
                    return
                writer.write(b'\x05\x00')
                await writer.drain()
                version, command, reserved, atyp = await reader.readexactly(4)
                if (version, command, reserved) != (5, 1, 0):
                    raise ValueError('Only SOCKS CONNECT is supported')
                destination = await socks_address(reader, atyp) + await reader.readexactly(2)
                n = self.network
                remote, upstream = await asyncio.open_connection(n['host'], n['port'])
                self.writers.add(upstream)
                upstream.write(b'\x05\x01\x02')
                await upstream.drain()
                if await remote.readexactly(2) != b'\x05\x02':
                    raise ValueError('Upstream authentication unavailable')
                username = n['username'].encode('utf-8')
                password = unseal(n['secret']).encode('utf-8')
                if not 1 <= len(username) <= 255 or not 1 <= len(password) <= 255:
                    raise ValueError('Invalid SOCKS credentials')
                upstream.write(b'\x01' + bytes([len(username)]) + username + bytes([len(password)]) + password)
                await upstream.drain()
                if await remote.readexactly(2) != b'\x01\x00':
                    raise ValueError('Upstream authentication failed')
                upstream.write(bytes([5, 1, 0, atyp]) + destination)
                await upstream.drain()
                reply = await remote.readexactly(4)
                if reply[0] != 5 or reply[2] != 0:
                    raise ValueError('Invalid upstream reply')
                bound = await socks_address(remote, reply[3]) + await remote.readexactly(2)
                writer.write(reply + bound)
                await writer.drain()
                if reply[1] != 0:
                    return
            async def copy(source, target):
                while data := await source.read(65536):
                    target.write(data)
                    await target.drain()
                if target.can_write_eof():
                    target.write_eof()
            async with asyncio.TaskGroup() as group:
                group.create_task(copy(reader, upstream))
                group.create_task(copy(remote, writer))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Exception strings may contain credentials or destination details.
            try:
                writer.write(b'\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
            except Exception:
                pass
        finally:
            for stream in (writer, upstream):
                if stream:
                    self.writers.discard(stream)
                    stream.close()

    async def close(self):
        if self.thread:
            thread, loop = self.thread, self.loop
            self.thread = None
            try:
                await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(self._close(), loop))
            finally:
                loop.call_soon_threadsafe(loop.stop)
                await asyncio.to_thread(thread.join)
                loop.close()
        else:
            await self._close()

    async def _close(self):
        self.closed = True
        if self.server:
            self.server.close()
        for writer in list(self.writers):
            writer.close()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        self.writers.clear()
        if self.server:
            await self.server.wait_closed()


async def close_browser_network(browser, network):
    # Close relay sockets first so Chromium cannot wait on open proxy tunnels.
    try:
        if network:
            await network.close()
    finally:
        if browser:
            await asyncio.wait_for(browser.close(), timeout=10)
