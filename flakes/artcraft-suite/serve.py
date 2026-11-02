#!/usr/bin/env python3
"""Serve ArtCraft on localhost with WebAssembly MIME types and isolation headers."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.wasm': 'application/wasm', '.js': 'text/javascript'}

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        super().end_headers()

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', required=True)
parser.add_argument('--port', type=int, default=8175)
args = parser.parse_args()
server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=args.directory))
print(f'ArtCraft: http://localhost:{args.port}', flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.server_close()
