#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.backend
~~~~~~~~~~~~~~~~~

This module provides a backend object to manage and persist backend daemon. 
It implements a basic backend server using Python's socket and threading libraries.
It supports handling multiple client connections concurrently and routing requests using a
custom HTTP adapter.

Requirements:
--------------
- socket: provide socket networking interface.
- threading: Enables concurrent client handling via threads.
- response: response utilities.
- httpadapter: the class for handling HTTP requests.
- CaseInsensitiveDict: provides dictionary for managing headers or routes.


Notes:
------
- The server create daemon threads for client handling.
- The current implementation error handling is minimal, socket errors are printed to the console.
- The actual request processing is delegated to the HttpAdapter class.

Usage Example:
--------------
>>> create_backend("127.0.0.1", 9000, routes={})

"""

import socket
import threading
import argparse

from .response import *
from .httpadapter import HttpAdapter

def handle_client(ip, port, conn, addr, routes):
    """
    Initializes an HttpAdapter instance and delegates the client handling logic to it.

    :param ip (str): IP address of the server.
    :param port (int): Port number the server is listening on.
    :param conn (socket.socket): Client connection socket.
    :param addr (tuple): client address (IP, port).
    :param routes (dict): Dictionary of route handlers.
    """
    daemon = HttpAdapter(ip, port, conn, addr, routes)

    # Handle client
    daemon.handle_client(conn, addr, routes)

def run_backend(ip, port, routes):
    """
    Starts the backend server, binds to the specified IP and port, and listens for incoming
    connections. Each connection is handled in a separate thread. The backend accepts incoming
    connections and spawns a thread for each client.


    :param ip (str): IP address to bind the server.
    :param port (int): Port number to listen on.
    :param routes (dict): Dictionary of route handlers.
    """
    # 1. Tạo 1 socket mạng
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 2. Gán địa chỉ ip và port cho socket
        server.bind((ip, port))
        # 3. Lắng nghe tối đa 50 client
        server.listen(50)
        # Log full bind address for easier LAN debugging
        try:
            print(f"[Backend] Listening on {ip}:{port}")
        except Exception:
            print("[Backend] Listening on port {}".format(port))
        if routes:
            print(f"[Backend] Routes: {routes}")
        while True:
            # 4. Chờ client kết nối tới
            # addr: ip và port của client
            conn, addr = server.accept()
            # 5. Tạo thread xử lý client này để client kết nối khác không phải chờ
            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes),
                daemon=True  
            )
            # 6. Thread xử lý client kết nối
            client_thread.start()
    except socket.error as e:   
        print("Socket error: {}".format(e))

def create_backend(ip, port, routes={}):
    run_backend(ip, port, routes)