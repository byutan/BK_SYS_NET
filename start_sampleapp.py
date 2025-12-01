#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import json
import socket
import argparse

from daemon.weaprous import WeApRous

PORT = 8000  # Default port
CURRENT_PORT = 0

app = WeApRous()
@app.route('/', methods=['GET'])
def home_page(headers, body):
    return f"ON PORT: {CURRENT_PORT}"

@app.route('/login', methods=['POST','PUT'])
def login(headers="guest", body="anonymous"):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    print ("[SampleApp] Logging in {} to {}".format(headers, body))

@app.route('/hello', methods=['PUT','POST'])
def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print ("[SampleApp] ['PUT'] Hello in {} to {}".format(headers, body))


@app.route('/send-peer', methods=['POST'])
def send_peer(headers, body):
    """Send message to a peer. Expects JSON body: {"ip":"x.x.x.x","port":8002,"message":"..."}

    The handler connects to the peer's /p2p/receive endpoint and forwards the JSON payload.
    Returns JSON {"status":"ok"} or error.
    """
    import json, socket
    try:
        payload = json.loads(body or '{}')
    except Exception:
        return {"error": "invalid json"}

    ip = payload.get('ip')
    port = int(payload.get('port') or 0)
    message = payload.get('message')
    if not ip or not port or message is None:
        return {"error": "missing fields"}

    # forward to peer
    try:
        b = json.dumps({'from': 'webapp', 'message': message}).encode('utf-8')
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((ip, port))
            req = (
                f"POST /p2p/receive HTTP/1.1\r\nHost: {ip}\r\nContent-Type: application/json\r\nContent-Length: {len(b)}\r\n\r\n"
            ).encode('utf-8') + b
            s.sendall(req)
            _ = s.recv(4096)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}

@app.route('/chat', methods=['GET'])
def chat_page(headers, body):
    """Serve the P2P chat web interface as HTML."""
    try:
        with open('www/chat.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        # Return as string (WeApRous will handle HTML rendering)
        return html_content
    except Exception as e:
        return {"error": f"Failed to load chat page: {str(e)}"}

if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(prog='Backend', description='', epilog='Beckend daemon')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=PORT)
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port
    
    CURRENT_PORT = port
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    # Print registered routes for clarity
    try:
        print("[SampleApp] Registered routes:")
        for (method, path), fn in app.routes.items():
            print(f"  - {method} {path} -> {fn.__name__}")
    except Exception:
        pass

    app.run()