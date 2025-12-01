

"""
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
import re
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.

# Global
rr_index = {}
rr_lock = threading.Lock()

def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                  fails, returns a 404 Not Found response.
    """
    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend.settimeout(10) # Timeout sau 10s

    try:
        backend.connect((host, port))
        # 1. Xử lý Request Header (Decode + Fix Keep-Alive)
        if isinstance(request, bytes):
            request_str = request.decode('utf-8', errors='ignore')
        else:
            request_str = request

        # Thay thế 'Connection: keep-alive' thành 'Connection: close'
        if re.search(r'Connection:\s*keep-alive', request_str, re.IGNORECASE):
            request_str = re.sub(r'Connection:\s*keep-alive', 'Connection: close', request_str, flags=re.IGNORECASE)
        elif 'Connection:' not in request_str:
            # Nếu chưa có header Connection, chèn vào
            request_str = request_str.replace('\r\n\r\n', '\r\nConnection: close\r\n\r\n')
        
        # Gửi request đã sửa tới Backend
        backend.sendall(request_str.encode('utf-8'))

        # Nhận phản hồi từ Backend
        response = b""
        while True:
            try:
                chunk = backend.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                print(f"[Proxy] Timeout waiting for response from {host}:{port}")
                break
        
        backend.close()
        return response

    except socket.error as e:
        print(f"[Proxy] Error connecting to backend {host}:{port} -> {e}")
        return (
            "HTTP/1.1 502 Bad Gateway\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 15\r\n"
            "Connection: close\r\n"
            "\r\n"
            "502 Bad Gateway"
        ).encode('utf-8')
    
    # backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # try:
    #     backend.connect((host, port))
    #     backend.sendall(request.encode())
    #     response = b""
    #     while True:
    #         chunk = backend.recv(4096)
    #         if not chunk:
    #             break
    #         response += chunk
    #     return response
    # except socket.error as e:
    #     print("Socket error: {}".format(e))
    #     return (
    #             "HTTP/1.1 404 Not Found\r\n"
    #             "Content-Type: text/plain\r\n"
    #             "Content-Length: 13\r\n"
    #             "Connection: close\r\n"
    #             "\r\n"
    #             "404 Not Found"
    #         ).encode('utf-8')


def resolve_routing_policy(hostname, routes):
    """
    Handles a routing policy to return the matching proxy_pass.
    It determines the target backend to forward the request to.
    """
    route_info = routes.get(hostname)
    if not route_info and ':' in hostname:
        clean_host = hostname.split(':')[0]
        route_info = routes.get(clean_host)
        if route_info:
            print(f"[Router] Fallback: Found route for '{clean_host}' (original: {hostname})")

    if not route_info:
        return None, None
    
    proxy_map, policy = route_info
    target_url = ""
    # Case 1: Chỉ có 1 backend (String) hoặc List nhưng chỉ có 1 phần tử
    if isinstance(proxy_map, str):
        target_url = proxy_map
    elif isinstance(proxy_map, list):
        if len(proxy_map) == 1:
            target_url = proxy_map[0]
        else:
            # Case 2: Round Robin với nhiều backend
            if policy == 'round-robin':
                with rr_lock: # Khóa lại để tính toán index an toàn
                    current_idx = rr_index.get(hostname, 0)
                    target_url = proxy_map[current_idx % len(proxy_map)]
                    rr_index[hostname] = current_idx + 1
                    print(f"[LoadBalancing] Host: {hostname} -> RoundRobin Index: {current_idx} -> Target: {target_url}")
            else:
                # Mặc định lấy cái đầu tiên nếu policy lạ
                target_url = proxy_map[0]
    try:
        # Loại bỏ prefix http:// hoặc https://
        if '://' in target_url:
            target_url = target_url.split('://')[1]
        
        if ':' in target_url:
            host, port_str = target_url.split(':', 1)
            return host, int(port_str.replace(';', '')) # remove ; if exists
        else:
            # Mặc định port 80 nếu không ghi port
            return target_url.replace(';', ''), 80
    except Exception as e:
        print(f"[Proxy] Error parsing target URL '{target_url}': {e}")
        return None, None



    # 1. Tìm route cho hostname. Nếu không thấy, trả về None để báo lỗi.
    # route_info = routes.get(hostname)
    # if not route_info:
    #     print(f"[Proxy] ERROR: Host '{hostname}' not found in configuration.")
    #     return None, None

    # proxy_map, policy = route_info
    
    # # 2. Xử lý logic dựa trên proxy_map là chuỗi hay danh sách
    # if isinstance(proxy_map, str):  # Trường hợp chỉ có 1 proxy_pass
    #     # proxy_map là một chuỗi như '192.168.1.6:9000'
    #     try:
    #         host, port_str = proxy_map.split(':', 1)
    #         return host, int(port_str)
    #     except (ValueError, IndexError):
    #         print(f"[Proxy] ERROR: Invalid proxy_pass format for host '{hostname}': {proxy_map}")
    #         return None, None

    # elif isinstance(proxy_map, list): # Trường hợp có nhiều proxy_pass
    #     if not proxy_map:
    #         print(f"[Proxy] ERROR: Empty proxy_pass list for host '{hostname}'.")
    #         return None, None

    #     if policy == 'round-robin':
    #         with rr_lock:
    #             i = rr_index.get(hostname, 0)
    #             upstream = proxy_map[i % len(proxy_map)]
    #             rr_index[hostname] = i + 1
            
    #         try:
    #             host, port_str = upstream.split(':', 1)
    #             return host, int(port_str)
    #         except (ValueError, IndexError):
    #             print(f"[Proxy] ERROR: Invalid proxy_pass format in list for host '{hostname}': {upstream}")
    #             return None, None
    #     else:
    #         # Các policy khác chưa được hỗ trợ, chỉ lấy cái đầu tiên
    #         print(f"[Proxy] WARNING: Policy '{policy}' not fully supported, using first entry.")
    #         try:
    #             host, port_str = proxy_map[0].split(':', 1)
    #             return host, int(port_str)
    #         except (ValueError, IndexError):
    #             print(f"[Proxy] ERROR: Invalid proxy_pass format for host '{hostname}': {proxy_map[0]}")
    #             return None, None

    # # Nếu không rơi vào trường hợp nào, trả về lỗi
    # return None, None
#24 hàm này được gọi khi một kết nối client được chấp nhận bởi proxy server.
def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    matches the hostname against known routes. In the matching
    condition,it forwards the request to the appropriate backend.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): port number of the proxy server.
    :params conn (socket.socket): client connection socket.
    :params addr (tuple): client address (IP, port).
    :params routes (dict): dictionary mapping hostnames and location.
    """
    try:
        request = conn.recv(4096)
        if not request:
            conn.close()
            return
        request_str = request.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error reading request: {e}")
        conn.close()
        return

    # 1. Phân tích Host Header
    hostname = None
    for line in request_str.splitlines():
        if line.lower().startswith('host:'):
            # Lấy phần sau dấu : đầu tiên, xóa khoảng trắng
            hostname = line.split(':', 1)[1].strip()
            break
    
    if not hostname:
        hostname = f"{addr[0]}:{port}" # Fallback
    print(f"[Proxy] Request from {addr} for Host: {hostname}")

    # 2. Tìm Backend phù hợp
    resolved_host, resolved_port = resolve_routing_policy(hostname, routes)

    # 3. Forward hoặc trả lỗi
    if resolved_host and resolved_port:
        response = forward_request(resolved_host, resolved_port, request)
    else:
        print(f"[Proxy] 404 Not Found: No route for host {hostname}")
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode('utf-8')
    try:
        conn.sendall(response)
    except Exception as e:
        print(f"Error sending response: {e}")
    finally:
        conn.close()


    # print("*" * 60)
    # print("Start Handle Client")

    """
    Sample Request:
        Start Handle Client
        [request] GET /login.html HTTP/1.1
        Host: 192.168.1.12:8080
        Connection: keep-alive
        Cache-Control: max-age=0
        Upgrade-Insecure-Requests: 1
        User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36
        Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8
        Sec-GPC: 1
        Accept-Language: en-US,en;q=0.5
        Referer: http://192.168.1.12:8080/login
        Accept-Encoding: gzip, deflate
    """
    # request = conn.recv(4096).decode(errors='ignore')

    # #25 đọc hostname từ header 'Host'
    # hostname = None
    # for line in request.splitlines():
    #     if line.lower().startswith('host:'):
    #         # host header may contain ':' so split only on the first ':' occurrence
    #         hostname = line.split(':', 1)[1].strip()  # e.g. '192.168.1.12:8080'
    #         break
    # # If Host header missing, fall back to client's address:port to avoid crash
    # if not hostname:
    #     try:
    #         hostname = f"{addr[0]}:{port}"
    #     except Exception:
    #         hostname = ''

    # print("[Proxy] {} at Host: {} Port: {}".format(addr, hostname, port))

    # #26 gọi hàm resolve_routing_policy(hostname, routes) để xác định backend phù hợp dựa trên hostname.
    # resolved_host, resolved_port = resolve_routing_policy(hostname, routes)

    # #27 gọi forward_request, hàm này mở một kết nối socket mới đến Backend Server ở port 9000
    # if resolved_host and resolved_port:
    #     print(f"[Proxy] Host name {hostname} is forwarded to {resolved_host}:{resolved_port}")
    #     response = forward_request(resolved_host, resolved_port, request)
    # else:
    #     # Nếu không tìm thấy, tạo response 404
    #     print(f"[Proxy] No valid backend found for host {hostname}. Returning 404.")
    #     response = (
    #         "HTTP/1.1 404 Not Found\r\n"
    #         "Content-Type: text/plain\r\n"
    #         "Content-Length: 13\r\n"
    #         "Connection: close\r\n"
    #         "\r\n"
    #         "404 Not Found"
    #     ).encode('utf-8')

    # conn.sendall(response)
    # conn.close()

#16 Chạy proxy server với IP và port đã cho
def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections. 

    The process dinds the proxy server to the specified IP and port.
    In each incomping connection, it accepts the connections and
    spawns a new thread for each client using `handle_client`.
 

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.

    """
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Cho phép dùng lại port ngay lập tức nếu crash
    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print(f"\n[Proxy] Server started on {ip}:{port}")
        print(f"[Proxy] Loaded routes: {list(routes.keys())}")
        print("------------------------------------------------")

        while True:
            conn, addr = proxy.accept()
            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes),
                daemon=True
            )
            client_thread.start()
    except KeyboardInterrupt:
        print("\n[Proxy] Shutting down...")
    except Exception as e:
        print(f"[Proxy] Fatal Error: {e}")
    finally:
        proxy.close()

    # #17 Tạo socket proxy
    # proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # try:
    #     #18 bind vào địa chỉ
    #     proxy.bind((ip, port))
    #     #19 listen() để chuyển sang trạng thái sẵn sàng.
    #     proxy.listen(50)
    #     print("[Proxy] Listening on IP {} port {}".format(ip, port))
    #     #20 đi vào vòng lặp while True và bị dừng lại (block) ở hàm proxy.accept(),  chờ đợi một kết nối đến.
    #     try:
    #         while True:
    #             conn, addr = proxy.accept() #21 Chấp nhận kết nối đến
    #             client_thread = threading.Thread( #22 Tạo luồng mới cho mỗi kết nối client
    #                 target=handle_client, #23 Gọi hàm handle_client từ daemon/proxy.py
    #                 args=(ip, port, conn, addr, routes),
    #                 daemon=True
    #             )
    #             client_thread.start()
    #     except KeyboardInterrupt:
    #         print("\n[Proxy] Ctrl+C detected, shutting down...")

    # except socket.error as e:
    #     print("Socket error: {}".format(e))
    # finally:
    #     try:
    #         proxy.close() 
    #     except Exception as e:
    #         print("Error closing proxy socket: {}".format(e))

#15 gọi create_proxy('0.0.0.0', 8080, routes) gọi run_proxy
def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)

