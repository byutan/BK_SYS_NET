"""
Simple centralized tracker server for hybrid P2P chat.

Endpoints (JSON over HTTP):
- POST /submit-info    -> register a peer {"ip":"x.x.x.x","port":int,"name":str}
- GET  /get-list       -> returns {"peers": [ {ip,port,name} ] }
- POST /add-list       -> add peer to channel {"channel":"general","peer":{...}}
- GET  /get-list?channel=name -> returns channel peers and messages
- POST /broadcast-peer -> add message to channel {"from":{...},"channel":"general","message":"..."}
- POST /connect-peer   -> return peer info for connection {"to":{"ip","port"}}

This tracker is intentionally small and uses raw sockets and threads to integrate
with the project's existing socket architecture.
"""
import socket
import threading
import json
import time
from urllib.parse import urlparse, parse_qs
import traceback

LOCK = threading.Lock()

# peers: map peer_id -> {ip, port, name, ts}
PEERS = {}
# channels: map channel -> {peers:set(peer_id), messages:[{from,message,ts}]}
CHANNELS = {}

def _peer_id(info):
    return f"{info['ip']}:{info['port']}"

def handle_http(conn, addr):
    try:
        # Read request data in a loop to avoid truncated bodies on slow clients
        conn.settimeout(0.5)
        raw = b''
        try:
            while True:
                chunk = conn.recv(8192)
                if not chunk:
                    break
                raw += chunk
                # if chunk smaller than buffer, likely end of data
                if len(chunk) < 8192:
                    break
        except socket.timeout:
            # timed out reading more data — proceed with what we have
            pass

        if not raw:
            return

        text = raw.decode('utf-8', 'ignore')
        first_line = text.split('\r\n',1)[0]
        parts = first_line.split()
        if len(parts) < 2:
            return
        method = parts[0]
        path = parts[1]

        # parse headers & body
        head, _, body = text.partition('\r\n\r\n')
        content = body.strip()

        parsed = urlparse(path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        # Handle CORS preflight immediately
        if method == 'OPTIONS':
            # reply with CORS headers
            try:
                return conn.sendall(build_response(200, {}))
            except Exception:
                return

        # Basic request logging for debugging
        try:
            body_preview = content[:200] if isinstance(content, str) else ''
            print(f"[Tracker] Request from {addr}: {method} {route} ContentLen={len(content)} Preview={body_preview}")
        except Exception:
            pass

        # Dispatch
        if method == 'POST' and route == '/submit-info':
            try:
                obj = json.loads(content or '{}')
            except Exception as e:
                return conn.sendall(build_response(400, {'error': 'invalid json', 'detail': str(e)}))
            with LOCK:
                pid = _peer_id(obj)
                PEERS[pid] = {**obj, 'ts': time.time()}
            resp = {'status':'ok','peers_count': len(PEERS)}
            return conn.sendall(build_response(200, resp))

        if method == 'GET' and route == '/get-list':
            channel = qs.get('channel',[None])[0]
            with LOCK:
                if channel:
                    ch = CHANNELS.get(channel, {'peers':set(), 'messages':[]})
                    peers = [PEERS[p] for p in ch['peers'] if p in PEERS]
                    resp = {'channel': channel, 'peers': peers, 'messages': ch['messages']}
                else:
                    resp = {'peers': list(PEERS.values())}
            return conn.sendall(build_response(200, resp))

        if method == 'POST' and route == '/add-list':
            try:
                obj = json.loads(content or '{}')
            except Exception as e:
                return conn.sendall(build_response(400, {'error':'invalid json', 'detail': str(e)}))
            channel = obj.get('channel')
            peer = obj.get('peer')
            if not channel or not peer:
                return conn.sendall(build_response(400, {'error':'missing channel or peer'}))
            pid = _peer_id(peer)
            with LOCK:
                CHANNELS.setdefault(channel, {'peers': set(), 'messages': []})
                CHANNELS[channel]['peers'].add(pid)
            print(f"[Tracker] /add-list: added {pid} to {channel}")
            return conn.sendall(build_response(200, {'status':'ok'}))

        if method == 'POST' and route == '/broadcast-peer':
            # debug log incoming payload
            try:
                print(f"[Tracker] /broadcast-peer from {addr}: {content}")
            except Exception:
                pass
            try:
                obj = json.loads(content or '{}')
            except Exception as e:
                return conn.sendall(build_response(400, {'error':'invalid json', 'detail': str(e)}))
            from_peer = obj.get('from')
            channel = obj.get('channel')
            message = obj.get('message')
            if not from_peer or not channel or message is None:
                return conn.sendall(build_response(400, {'error':'missing fields'}))
            pid = _peer_id(from_peer)
            entry = {'from': from_peer, 'message': message, 'ts': time.time()}
            with LOCK:
                # Do not store or forward private messages via tracker — private messages should be direct P2P.
                if channel == 'private':
                    peers = []
                else:
                    ch = CHANNELS.setdefault(channel, {'peers': set(), 'messages': []})
                    ch['messages'].append(entry)
                    # ensure sender is present
                    ch['peers'].add(pid)
                    peers = [PEERS[p] for p in ch['peers'] if p in PEERS]
            # attempt to forward the message to peers' /p2p/receive endpoints (only for non-private)
            try:
                forward_results = _forward_to_peers(peers, entry, exclude_pid=pid) if channel != 'private' else []
            except Exception:
                forward_results = []
            # return list of peers and forwarding results
            return conn.sendall(build_response(200, {'status':'ok','peers': peers, 'forwarded': forward_results}))

        if method == 'POST' and route == '/connect-peer':
            try:
                obj = json.loads(content or '{}')
            except Exception as e:
                return conn.sendall(build_response(400, {'error':'invalid json', 'detail': str(e)}))
            to = obj.get('to')
            if not to:
                return conn.sendall(build_response(400, {'error':'missing to'}))
            pid = _peer_id(to)
            with LOCK:
                info = PEERS.get(pid)
            if not info:
                return conn.sendall(build_response(404, {'error':'peer not found'}))
            print(f"[Tracker] /connect-peer: returning info for {pid}")
            return conn.sendall(build_response(200, {'peer': info}))

        # default
        return conn.sendall(build_response(404, {'error':'not found'}))
    except Exception as e:
        # Log the traceback to help debug connection resets
        try:
            print('[Tracker] Exception in handle_http:')
            traceback.print_exc()
        except:
            pass
        try:
            conn.sendall(build_response(500, {'error': str(e)}))
        except:
            pass
    finally:
        try:
            conn.close()
        except:
            pass

def build_response(status_code=200, obj=None):
    body = json.dumps(obj or {}).encode('utf-8')
    # Include CORS headers so browser-based WebApp (different port) can fetch tracker API
    headers = (
        f"HTTP/1.1 {status_code} OK\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        "Access-Control-Allow-Headers: Content-Type\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode('utf-8')
    return headers + body


def _forward_to_peers(peers, entry, exclude_pid=None):
    """Attempt to POST the entry to each peer's /p2p/receive endpoint.
    Returns a list of results per peer.
    """
    results = []
    b = json.dumps(entry).encode('utf-8')
    for p in peers:
        pid = f"{p.get('ip')}:{p.get('port')}"
        if exclude_pid and pid == exclude_pid:
            continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                addr = (p.get('ip'), int(p.get('port')))
                s.connect(addr)
                req = (
                    f"POST /p2p/receive HTTP/1.1\r\nHost: {p.get('ip')}\r\nContent-Type: application/json\r\nContent-Length: {len(b)}\r\n\r\n"
                ).encode('utf-8') + b
                s.sendall(req)
                try:
                    _ = s.recv(4096)
                except Exception:
                    pass
            results.append({'peer': pid, 'ok': True})
            try:
                print(f"[Tracker] Forwarded message to {pid}")
            except Exception:
                pass
        except Exception as e:
            results.append({'peer': pid, 'ok': False, 'error': str(e)})
            try:
                print(f"[Tracker] Failed to forward to {pid}: {e}")
            except Exception:
                pass
    return results

def run_tracker(ip='0.0.0.0', port=9001):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((ip, port))
    srv.listen(50)
    print(f"[Tracker] Listening on {ip}:{port}")
    try:
        while True:
            conn, addr = srv.accept()
            t = threading.Thread(target=handle_http, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print('\n[Tracker] Shutting down')
    finally:
        srv.close()

if __name__ == '__main__':
    run_tracker('0.0.0.0', 9001)
