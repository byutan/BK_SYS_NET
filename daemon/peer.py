"""
Simple peer process for hybrid P2P chat.

Features:
- Listens for incoming P2P HTTP POSTs at /p2p/receive
- Registers itself with the central tracker via /submit-info
- Can query tracker (/get-list) to discover peers
- Broadcasts messages to peers by POSTing to their /p2p/receive endpoint
- Optional LAN UDP announce to support discovery
"""
import socket
import threading
import json
import time
from urllib.parse import urlparse


class Peer:
    def __init__(self, ip='0.0.0.0', port=10000, name=None, tracker_ip='127.0.0.1', tracker_port=9001, udp_broadcast_port=9002):
        self.ip = ip
        self.port = port
        self.name = name or f"peer-{port}"
        self.tracker = (tracker_ip, tracker_port)
        self.udp_port = udp_broadcast_port
        self.running = False
        self.messages = []
        # recent message keys for short-window deduplication
        self._recent_keys = {}

    def start(self):
        self.running = True
        t = threading.Thread(target=self._run_server, daemon=True)
        t.start()
        # start UDP listener
        u = threading.Thread(target=self._udp_listener, daemon=True)
        u.start()
        # announce ourselves
        self.register_to_tracker()
        self.udp_announce()

    def _run_server(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try to bind to specified IP, fallback to 0.0.0.0 if not available
        bind_ip = self.ip
        try:
            srv.bind((bind_ip, self.port))
        except OSError as e:
            print(f"[Peer:{self.name}] Warning: Cannot bind to {bind_ip}:{self.port} ({e})")
            print(f"[Peer:{self.name}] Falling back to 0.0.0.0:{self.port}")
            bind_ip = '0.0.0.0'
            srv.bind((bind_ip, self.port))
        
        srv.listen(50)
        print(f"[Peer:{self.name}] Listening on {bind_ip}:{self.port}")
        try:
            while self.running:
                conn, addr = srv.accept()
                threading.Thread(target=self._handle_conn, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            pass
        finally:
            srv.close()

    def _handle_conn(self, conn, addr):
        try:
            data = conn.recv(8192)
            if not data:
                return
            text = data.decode('utf-8', 'ignore')
            first_line = text.split('\r\n',1)[0]
            parts = first_line.split()
            if len(parts) < 2:
                return
            method = parts[0]
            path = parts[1]
            head, _, body = text.partition('\r\n\r\n')
            content = body.strip()
            # Handle CORS preflight immediately
            if method == 'OPTIONS':
                # respond with CORS headers and no body
                hdr = (
                    "HTTP/1.1 200 OK\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                    "Access-Control-Allow-Headers: Content-Type\r\n"
                    "Content-Length: 0\r\n"
                    "Connection: close\r\n\r\n"
                ).encode('utf-8')
                try:
                    conn.sendall(hdr)
                except:
                    pass
                return
            if method == 'POST' and path == '/p2p/receive':
                # Simple, robust receive: parse JSON (or keep raw), store, print and respond.
                try:
                    try:
                        obj = json.loads(content or '{}')
                    except Exception:
                        obj = {'raw': content}
                    now_ts = time.time()
                    obj['ts'] = now_ts
                    # compute dedupe key from sender, channel and message
                    sender = obj.get('from') if isinstance(obj.get('from'), dict) else obj.get('from')
                    from_ip = ''
                    from_port = 0
                    if isinstance(sender, dict):
                        from_ip = sender.get('ip', '')
                        try:
                            from_port = int(sender.get('port') or 0)
                        except Exception:
                            from_port = 0
                    key_msg = (str(from_ip), str(from_port), str(obj.get('channel') or 'general'), str(obj.get('message') or obj.get('raw') or ''))
                    key = '|'.join(key_msg)
                    last = self._recent_keys.get(key)
                    if last and (now_ts - last) < 2.0:
                        # duplicate within 2s window — ignore
                        # respond OK but do not append or print duplicate
                        try:
                            conn.sendall(self._build_response(200, {'status': 'duplicate_ignored'}))
                        except Exception:
                            pass
                        return
                    # not duplicate — record and append
                    self._recent_keys[key] = now_ts
                    # prune old keys occasionally
                    if len(self._recent_keys) > 500:
                        cutoff = now_ts - 5.0
                        for k, t in list(self._recent_keys.items()):
                            if t < cutoff:
                                del self._recent_keys[k]
                    self.messages.append(obj)
                    # friendly debug log
                    try:
                        sender = obj.get('from') if isinstance(obj.get('from'), dict) else obj.get('from')
                        sender_name = sender.get('name') if isinstance(sender, dict) else str(sender)
                    except Exception:
                        sender_name = 'unknown'
                    channel = obj.get('channel') or 'general'
                    message = obj.get('message') or obj.get('raw') or ''
                    print(f"\n[Received from {sender_name} in {channel}]: {message}")
                except Exception as e:
                    print(f"[Peer:{self.name}] Error handling /p2p/receive: {e}")
                try:
                    conn.sendall(self._build_response(200, {'status': 'ok'}))
                except Exception:
                    pass
                return

            # GET /peer-inbox returns and clears queued messages
            if method == 'GET' and path == '/peer-inbox':
                try:
                    out = self.messages.copy()
                    self.messages.clear()
                    body = json.dumps(out).encode('utf-8')
                    hdr = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json; charset=utf-8\r\n"
                        "Access-Control-Allow-Origin: *\r\n"
                        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                        "Access-Control-Allow-Headers: Content-Type\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        "Connection: close\r\n\r\n"
                    ).encode('utf-8')
                    conn.sendall(hdr + body)
                except Exception:
                    try:
                        conn.sendall(self._build_response(500, {'error': 'failed to read inbox'}))
                    except:
                        pass
                return
            conn.sendall(self._build_response(404, {'error':'not found'}))
        except Exception as e:
            try:
                conn.sendall(self._build_response(500, {'error': str(e)}))
            except:
                pass
        finally:
            try:
                conn.close()
            except:
                pass

    def _build_response(self, status, obj):
        b = json.dumps(obj).encode('utf-8')
        # Include CORS headers so browser clients can POST directly to peers
        hdr = (
            f"HTTP/1.1 {status} OK\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
            f"Content-Length: {len(b)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode('utf-8')
        return hdr + b

    def register_to_tracker(self):
        # Use explicit IP if not 0.0.0.0, otherwise auto-detect
        reg_ip = self.ip if self.ip != '0.0.0.0' else self._local_ip()
        payload = {'ip': reg_ip, 'port': self.port, 'name': self.name}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(self.tracker)
                body = json.dumps(payload).encode('utf-8')
                req = (
                    f"POST /submit-info HTTP/1.1\r\nHost: {self.tracker[0]}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
                ).encode('utf-8') + body
                s.sendall(req)
                _ = s.recv(4096)
            print(f"[Peer:{self.name}] Registered to tracker {self.tracker} as {reg_ip}:{self.port}")
            # Auto-add to default channel 'general'
            self.add_to_channel('general', reg_ip)
        except Exception as e:
            print(f"[Peer:{self.name}] Failed to register to tracker: {e}")

    def add_to_channel(self, channel_name, reg_ip):
        """Add this peer to a channel on the tracker."""
        payload = {
            'channel': channel_name,
            'peer': {'ip': reg_ip, 'port': self.port, 'name': self.name}
        }
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(self.tracker)
                body = json.dumps(payload).encode('utf-8')
                req = (
                    f"POST /add-list HTTP/1.1\r\nHost: {self.tracker[0]}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
                ).encode('utf-8') + body
                s.sendall(req)
                _ = s.recv(4096)
            print(f"[Peer:{self.name}] Added to channel '{channel_name}'")
        except Exception as e:
            print(f"[Peer:{self.name}] Failed to add to channel: {e}")

    def get_peers_from_tracker(self, channel=None):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                path = '/get-list'
                if channel:
                    path += f'?channel={channel}'
                req = f"GET {path} HTTP/1.1\r\nHost: {self.tracker[0]}\r\n\r\n".encode('utf-8')
                s.connect(self.tracker)
                s.sendall(req)
                data = s.recv(8192)
                if not data:
                    return []
                body = data.split(b'\r\n\r\n',1)[1]
                js = json.loads(body.decode('utf-8','ignore') or '{}')
                peers = js.get('peers', [])
                print(f"[{self.name}] Peers in tracker: {[(p.get('name'), p.get('ip'), p.get('port')) for p in peers]}")
                return peers
        except Exception as e:
            print(f"[Peer:{self.name}] get_peers error: {e}")
            return []

    def broadcast(self, message, channel=None):
        peers = self.get_peers_from_tracker(channel)
        # Use explicit IP if not 0.0.0.0, otherwise auto-detect
        my_ip = self.ip if self.ip != '0.0.0.0' else self._local_ip()
        # exclude self
        target_peers = [p for p in peers if not (p.get('ip') == my_ip and int(p.get('port')) == self.port)]
        
        if not target_peers:
            print(f"[{self.name}] No other peers in channel '{channel}'")
            return
        
        payload = {'from': {'ip': my_ip, 'port': self.port, 'name': self.name}, 'channel': channel, 'message': message}
        b = json.dumps(payload).encode('utf-8')
        
        print(f"[{self.name}] Broadcasting to {len(target_peers)} peer(s)")
        for p in target_peers:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(3)  # 3 second timeout
                    peer_addr = (p['ip'], int(p['port']))
                    s.connect(peer_addr)
                    req = (
                        f"POST /p2p/receive HTTP/1.1\r\nHost: {p['ip']}\r\nContent-Type: application/json\r\nContent-Length: {len(b)}\r\n\r\n"
                    ).encode('utf-8') + b
                    s.sendall(req)
                    response = s.recv(4096)
                print(f"[{self.name}] ✓ Sent to {p['name']} at {peer_addr}")
            except socket.timeout:
                print(f"[{self.name}] ✗ Timeout connecting to {p['name']} at {p['ip']}:{p['port']}")
            except ConnectionRefusedError:
                print(f"[{self.name}] ✗ Connection refused by {p['name']} at {p['ip']}:{p['port']}")
            except Exception as e:
                print(f"[{self.name}] ✗ Failed to send to {p['name']} at {p['ip']}:{p['port']}: {e}")

    def _local_ip(self):
        # best-effort to find a LAN IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    def udp_announce(self):
        # send one-shot UDP broadcast containing our ip/port
        try:
            msg = json.dumps({'ip': self._local_ip(), 'port': self.port, 'name': self.name}).encode('utf-8')
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(msg, ('<broadcast>', self.udp_port))
            s.close()
            print(f"[Peer:{self.name}] UDP announce sent on port {self.udp_port}")
        except Exception as e:
            print(f"[Peer:{self.name}] UDP announce failed: {e}")

    def _udp_listener(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', self.udp_port))
            while True:
                data, addr = s.recvfrom(4096)
                try:
                    obj = json.loads(data.decode('utf-8','ignore'))
                except Exception:
                    continue
                # discovered peer; register to tracker to keep consistent
                if 'ip' in obj and 'port' in obj:
                    print(f"[Peer:{self.name}] LAN discovered peer {obj}")
                    # auto-register discovered peer into tracker list via add-list? we'll just attempt to add it to tracker
                    # optional: call tracker to inform about discovered peer
                time.sleep(0.01)
        except Exception:
            pass


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=10000)
    parser.add_argument('--name', default=None)
    parser.add_argument('--tracker-ip', default='127.0.0.1')
    parser.add_argument('--tracker-port', type=int, default=9001)
    args = parser.parse_args()

    peer = Peer(ip='0.0.0.0', port=args.port, name=args.name, tracker_ip=args.tracker_ip, tracker_port=args.tracker_port)
    peer.start()

    # Simple interactive CLI
    print("Enter messages to broadcast (empty to quit). Prefix with '#channel ' to set channel.")
    channel = None
    try:
        while True:
            line = input('> ')
            if not line:
                break
            if line.startswith('#'):
                channel = line[1:].strip()
                print(f"Channel set to {channel}")
                continue
            peer.broadcast(line, channel)
    except KeyboardInterrupt:
        pass
