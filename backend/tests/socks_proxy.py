"""Controlled RFC 1928/1929 upstream fixture; never connects to public hosts."""
import hmac
import select
import socket
import socketserver
import threading


def receive(sock, count):
    data = b''
    while len(data) < count:
        chunk = sock.recv(count-len(data))
        if not chunk:
            raise EOFError()
        data += chunk
    return data


class SocksProxy:
    def __init__(self, target_port, username='fixture-user', password='fixture-password'):
        self.username, self.password = username, password
        self.authenticated = self.rejected = self.connections = 0
        self.sockets = set()
        parent = self
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                upstream = None
                client = self.request
                parent.sockets.add(client)
                client.settimeout(12)
                try:
                    version, count = receive(client, 2)
                    methods = receive(client, count)
                    method = 2 if parent.username else 0
                    if version != 5 or method not in methods:
                        client.sendall(b'\x05\xff');return
                    client.sendall(bytes([5, method]))
                    if method == 2:
                        version, length = receive(client, 2)
                        user = receive(client, length)
                        password = receive(client, receive(client, 1)[0])
                        valid = version == 1 and hmac.compare_digest(user, parent.username.encode()) and hmac.compare_digest(password, parent.password.encode())
                        client.sendall(bytes([1, 0 if valid else 1]))
                        if not valid:
                            parent.rejected += 1
                            return
                        parent.authenticated += 1
                    version, command, reserved, atyp = receive(client, 4)
                    if atyp == 1:host = socket.inet_ntoa(receive(client, 4))
                    elif atyp == 3:host = receive(client, receive(client, 1)[0]).decode()
                    else:raise ValueError('Unsupported fixture destination')
                    port = int.from_bytes(receive(client, 2), 'big')
                    if (version, command, reserved) != (5, 1, 0) or host not in ('localhost','127.0.0.1') or port != target_port:
                        client.sendall(b'\x05\x02\x00\x01'+b'\x00'*6);return
                    upstream = socket.create_connection((host, port), timeout=10)
                    parent.sockets.add(upstream)
                    parent.connections += 1
                    client.sendall(b'\x05\x00\x00\x01'+b'\x00'*6)
                    while True:
                        ready, _, _ = select.select([client, upstream], [], [], 12)
                        if not ready:return
                        for source in ready:
                            data = source.recv(65536)
                            if not data:return
                            (upstream if source is client else client).sendall(data)
                except (OSError, EOFError, ValueError):
                    pass
                finally:
                    for stream in (client, upstream):
                        if stream:
                            parent.sockets.discard(stream)
                            stream.close()
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True
        self.server = Server(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        for stream in list(self.sockets):
            try:stream.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            stream.close()
        self.thread.join(timeout=3)
