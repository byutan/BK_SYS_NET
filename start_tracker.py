"""Start tracker script for hybrid P2P chat."""
import argparse
from daemon.tracker import run_tracker

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Hybrid Chat Tracker")
    parser.add_argument('--ip', default='0.0.0.0', help='Tracker listening IP')
    parser.add_argument('--port', type=int, default=9001, help='Tracker port')

    args = parser.parse_args()

    print(f"[Tracker] Starting on {args.ip}:{args.port}")
    run_tracker(args.ip, args.port)
