"""Start peer script for hybrid P2P chat."""
from daemon.peer import Peer
import argparse
import time

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Hybrid Chat Peer")
    parser.add_argument('--ip', default='127.0.0.1', help='Peer REGISTRATION IP (IP other peers use to reach this peer). For LAN, use your actual machine IP like 192.168.1.10')
    parser.add_argument('--port', type=int, default=10000, help='Peer listening port')
    parser.add_argument('--name', default='Peer', help='Peer name')
    parser.add_argument('--tracker-ip', default='127.0.0.1', help='Tracker IP address')
    parser.add_argument('--tracker-port', type=int, default=9001, help='Tracker port')
    
    args = parser.parse_args()

    print(f"[Peer] Starting as {args.name} on {args.ip}:{args.port}")
    print(f"[Peer] Connecting to Tracker {args.tracker_ip}:{args.tracker_port}")

    peer = Peer(
        ip=args.ip,
        port=args.port,
        name=args.name,
        tracker_ip=args.tracker_ip,
        tracker_port=args.tracker_port
    )
    peer.start()

    # Interactive chat CLI
    print(f"\n[{args.name}] Ready for chat! Type messages to broadcast.")
    print(f"[{args.name}] Use '#channel_name' to switch channels (e.g., '#general')")
    print(f"[{args.name}] Press Ctrl+C to exit\n")
    
    channel = None
    try:
        while True:
            try:
                msg = input('> ')
                if not msg:
                    continue
                if msg.startswith('#'):
                    channel = msg[1:].strip()
                    if channel:
                        print(f"[{args.name}] Channel set to: {channel}")
                    continue
                if channel is None:
                    print(f"[{args.name}] Please set a channel first: #channel_name")
                    continue
                peer.broadcast(msg, channel)
            except EOFError:
                # Handle non-interactive mode gracefully
                time.sleep(1)
    except KeyboardInterrupt:
        print(f'\n[{args.name}] Shutting down...')
