"""Loopback-only HTTP proxy used by real Chromium regression tests."""
import http.client
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

class Proxy:
    def __init__(self, port, target_port=18080):
        self.binds=0
        self.requests=0
        self.block=False
        self.deny_bind=False
        self.drop_bind=False
        parent=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self): self.forward()
            def do_POST(self): self.forward()
            def forward(self):
                url=urlsplit(self.path)
                if url.hostname not in ('127.0.0.1','localhost') or url.port!=target_port:
                    self.send_error(403);return
                parent.requests+=1
                if parent.block:
                    self.send_error(403);return
                if url.path=='/bind':
                    parent.binds+=1
                    if parent.deny_bind:
                        self.send_error(429);return
                upstream=http.client.HTTPConnection(url.hostname,url.port,timeout=10)
                try:
                    body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                    headers={k:v for k,v in self.headers.items() if k.lower() not in ('proxy-authorization','proxy-connection','connection','host')}
                    upstream.request(self.command,url.path+('?' + url.query if url.query else ''),body=body,headers=headers)
                    response=upstream.getresponse()
                    data=response.read()
                    if url.path=='/bind' and parent.drop_bind:
                        # Upstream accepted the request; deliberately lose its response.
                        self.close_connection=True
                        return
                    self.send_response(response.status)
                    for k,v in response.getheaders():
                        if k.lower() not in ('transfer-encoding','connection','content-length'): self.send_header(k,v)
                    self.send_header('Content-Length',str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                finally:upstream.close()
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
    def start(self):self.thread.start();return self
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join()
