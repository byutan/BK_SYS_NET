"""
Lightweight smoke-test for the hybrid chat endpoints.
Usage: python tools/smoke_test.py --tracker 192.168.1.8:9001 --backend 192.168.1.8:8000 --peer 192.168.1.8:10000

This script uses the stdlib (urllib) so no extra deps are required.
It performs the following actions:
 - POST /submit-info (tracker)
 - POST /add-list (tracker)
 - POST /broadcast-peer (tracker)
 - GET  /get-list?channel=general (tracker)
 - POST /connect-peer (tracker)
 - POST /send-peer (backend WeApRous sample app)

Note: Make sure tracker, backend and peer are running before executing.
"""

import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
import sys


def http_post(hostport, path, obj):
    url = f"http://{hostport}{path}"
    data = json.dumps(obj).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST', headers={
        'Content-Type': 'application/json'
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode('utf-8', 'ignore')
            return r.getcode(), json.loads(body or '{}')
    except urllib.error.HTTPError as he:
        try:
            return he.code, json.loads(he.read().decode('utf-8','ignore') or '{}')
        except Exception:
            return he.code, {'error': str(he)}
    except Exception as e:
        return None, {'error': str(e)}


def http_get(hostport, path):
    url = f"http://{hostport}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read().decode('utf-8', 'ignore')
            return r.getcode(), json.loads(body or '{}')
    except urllib.error.HTTPError as he:
        try:
            return he.code, json.loads(he.read().decode('utf-8','ignore') or '{}')
        except Exception:
            return he.code, {'error': str(he)}
    except Exception as e:
        return None, {'error': str(e)}


def write_log(line):
    try:
        with open('tools/smoke_test.log', 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def run_all(tracker, backend, peer):
    print('1) POST /submit-info (idempotent)')
    # check if peer already registered
    code_g, res_g = http_get(tracker, '/get-list')
    exists = False
    try:
        peers = res_g.get('peers', []) if isinstance(res_g, dict) else []
        for p in peers:
            if str(p.get('ip')) == peer.split(':')[0] and int(p.get('port')) == int(peer.split(':')[1]):
                exists = True
                break
    except Exception:
        peers = []

    if exists:
        print(' - peer already registered; skipping submit-info')
        write_log('submit-info: skipped (already registered)')
    else:
        code, res = http_post(tracker, '/submit-info', {'ip': peer.split(':')[0], 'port': int(peer.split(':')[1]), 'name': 'smoketest'})
        print(code, res)
        write_log(f'submit-info: {code} {res}')

    print('\n2) POST /add-list (channel=general) (idempotent)')
    # check channel membership first
    code_ch, res_ch = http_get(tracker, '/get-list?channel=general')
    in_channel = False
    try:
        ch_peers = res_ch.get('peers', []) if isinstance(res_ch, dict) else []
        for p in ch_peers:
            if str(p.get('ip')) == peer.split(':')[0] and int(p.get('port')) == int(peer.split(':')[1]):
                in_channel = True
                break
    except Exception:
        ch_peers = []

    if in_channel:
        print(' - peer already in channel; skipping add-list')
        write_log('add-list: skipped (already in channel)')
    else:
        code, res = http_post(tracker, '/add-list', {'channel': 'general', 'peer': {'ip': peer.split(':')[0], 'port': int(peer.split(':')[1]), 'name': 'smoketest'}})
        print(code, res)
        write_log(f'add-list: {code} {res}')

    print('\n3) POST /broadcast-peer')
    code, res = http_post(tracker, '/broadcast-peer', {'from': {'ip': peer.split(':')[0], 'port': int(peer.split(':')[1]), 'name': 'smoketest'}, 'channel': 'general', 'message': 'hello from smoke_test'})
    print(code, res)
    write_log(f'broadcast-peer: {code} {res}')

    print('\n4) GET /get-list?channel=general')
    code, res = http_get(tracker, '/get-list?channel=general')
    print(code, json.dumps(res, indent=2))
    write_log(f'get-list: {code} {json.dumps(res)}')

    print('\n5) POST /connect-peer (ask tracker about peer)')
    code, res = http_post(tracker, '/connect-peer', {'to': {'ip': peer.split(':')[0], 'port': int(peer.split(':')[1])}})
    print(code, res)
    write_log(f'connect-peer: {code} {res}')

    print('\n6) POST /send-peer (backend) — forward to peer via backend')
    code, res = http_post(backend, '/send-peer', {'ip': peer.split(':')[0], 'port': int(peer.split(':')[1]), 'message': 'hi from backend send-peer'})
    print(code, res)
    write_log(f'send-peer: {code} {res}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--tracker', default='127.0.0.1:9001')
    p.add_argument('--backend', default='127.0.0.1:8000')
    p.add_argument('--peer', default='127.0.0.1:10000')
    args = p.parse_args()
    print('Smoke test starting — ensure tracker, backend, and peer are running')
    run_all(args.tracker, args.backend, args.peer)
