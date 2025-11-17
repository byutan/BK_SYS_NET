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
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

import socket
from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict
from .resp_template import RESP_TEMPLATES



class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.
    ... (docstring giữ nguyên) ...
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.
        ... (docstring giữ nguyên) ...
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.
        ... (docstring giữ nguyên) ...
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # === BẮT ĐẦU SỬA LỖI THỤT LỀ ===
        # Toàn bộ khối try...finally này phải nằm BÊN TRONG hàm handle_client
        try:
            # 1) Đọc từ socket
            raw = self.read_from_socket(conn)

            # 2) Phân tích thành Request object
            self.parse_into_request(req, raw, routes)
                  
            # If WeApRous routes exist and we have a matching hook, dispatch to it
            if req.hook:
                return self.send(resp, self.handle_weaprous(req, resp))
            
            # Otherwise handle Task 1 (login + static files)
            # ----- Task 1A: /login (ưu tiên) ----
            if req.method == "POST" and req.path == "/login":
                # Gọi hàm xử lý đăng nhập và gửi phản hồi
                return self.send(resp, self.handle_login(req, resp))

            # ----- Task 1B:  kiểm tra cookie -----
            early = self.cookie_auth_guard(req)
            if early is not None:
                # Nếu cookie_auth_guard trả về 1 response (tức là 401)
                # Gửi response đó và dừng lại ngay.
                return self.send(resp, early)

            # ----- Nếu vượt qua Task 1B, xử lý phục vụ file (ví dụ: index.html) -----
            # (Lưu ý: hàm dispatch() của bạn sẽ lo việc này)
            return self.send(resp, self.dispatch(req, resp))

        except Exception as e:
            # ... (Xử lý lỗi 500) ...
            e_tmpl = RESP_TEMPLATES["server_error"]
            # Sửa lại lỗi encode:
            body = e_tmpl["body"] + f"\n".encode("utf-8")
            return self.conn.sendall(resp.compose(
                status=e_tmpl["status"],
                headers={"Content-Type": e_tmpl["content_type"], **e_tmpl["headers"]},
                body=body
            ))
        finally:
            # Luôn đóng kết nối
            try:
                conn.close()
            except:
                pass
        # === KẾT THÚC SỬA LỖI THỤT LỀ ===


# -------------------- I/O ----------------------------------------------------------------
    def read_from_socket(self, conn) -> str:
        """Read HTTP request from socket with timeout."""
        try:
            conn.settimeout(5)  # 5-second timeout
            data = conn.recv(8192)  # Read more data at once
            if not data:
                return ""
            return data.decode("utf-8", "ignore")
        except socket.timeout:
            return ""
        except Exception as e:
            print(f"[HttpAdapter] read_from_socket error: {e}")
            return ""
# -------------------- Parse ----------------------------------------------------------------

    def parse_into_request(self, req, raw: str, routes):
        """
        Sử dụng req.prepare (từ request.py) để phân tích dữ liệu thô.
        """
        req.prepare(raw, routes)
        if not hasattr(req, "body") or req.body is None:
            req.body = b""

# --- CÁC HÀM TRỢ GIÚP MÀ BẠN SẼ CẦN TẠO ---
    def handle_login(self, req, resp):
    
        # Phân tích body (dạng 'username=admin&password=password')
        raw_body = req.body.decode("utf-8", "ignore") if isinstance(req.body, (bytes, bytearray)) else (req.body or "")
        creds = {}
        for pair in raw_body.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                creds[k] = v

        # Kiểm tra thông tin
        if creds.get("username") == "admin" and creds.get("password") == "password":
            # Nếu ĐÚNG:
            # 1. Đặt đường dẫn thành /index.html để chuẩn bị phục vụ
            req.path = "/chat.html"
            
            # 2. Xây dựng response cho file index.html
            #    (Hàm này sẽ gọi response.py để đọc file)
            raw = resp.build_response(req) 
            body = raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else raw
            
            # 3. Tạo header, quan trọng nhất là 'Set-Cookie'
            headers = {
                "Content-Type": "text/html; charset=utf-8",
                "Set-Cookie": "auth=true; Path=/", # GỬI COOKIE CHO TRÌNH DUYỆT
            }
            # 4. Trả về bộ 3 (status, headers, body)
            return ("200 OK", headers, body)

        # Nếu SAI: Trả về 401
        e = RESP_TEMPLATES["login_failed"]
        return (e["status"], {"Content-Type": e["content_type"], **e["headers"]}, e["body"])

    def cookie_auth_guard(self, req):
        """
        Hàm này xử lý logic cho Task 1B:
        - Bảo vệ trang /index.html.
        - Kiểm tra cookie 'auth=true'.
        - Trả về None (cho qua) hoặc (401 response) (chặn lại).
        """
        # Chỉ "gác cổng" cho trang / hoặc /index.html
        if req.path in ("/", "/chat.html"):
            
            # req.cookies (từ request.py) đã phân tích cookie cho ta
            if req.cookies.get("auth") != "true":
                # Nếu KHÔNG CÓ cookie 'auth=true', trả về 401
                e = RESP_TEMPLATES["unauthorized"]
                return (e["status"], {"Content-Type": e["content_type"], **e["headers"]}, e["body"])
        
        # Sửa lỗi nhỏ: nếu request là "/", đổi thành "/index.html"
        if req.path == "/":
            req.path = "/chat.html"
            
        # Nếu có cookie, hoặc request đến file khác (.css), cho qua
        return None
# -------------------- Send  --------------------
    def dispatch(self, req, resp):
        """
        Quyết định xem nên làm gì:
        1) Gọi hook (Task 2)
        2) Phục vụ file tĩnh (Task 1)
        """
        if req.hook: # req.hook sẽ None trong Task 1
            return self.handle_weaprous(req, resp) # handle registered WeApRous route
        return self.handle_static(req, resp) # Sẽ chạy ở Task 1

    def handle_weaprous(self, req, resp):
        """
        Execute a WeApRous registered handler.

        - Calls the function stored in req.hook with (headers, body) signature when possible.
        - Supports handlers that return dict (JSON) or string/bytes.
        - Returns the triple expected by send(): (status, headers, body)
        """
        func = req.hook
        try:
            # prepare arguments
            body = req.body or b""
            try:
                body_text = body.decode('utf-8', 'ignore') if isinstance(body, (bytes, bytearray)) else str(body)
            except Exception:
                body_text = ''

            # Try calling with (headers, body) then fallback to (body,) then no-arg
            result = None
            try:
                result = func(req.headers, body_text)
            except TypeError:
                try:
                    result = func(body_text)
                except TypeError:
                    result = func()

            # Normalize result
            if result is None:
                # Handler performed side-effects; return 200 OK
                return ("200 OK", {"Content-Type": "text/plain; charset=utf-8"}, b"OK")

            if isinstance(result, (dict, list)):
                import json
                body_bytes = json.dumps(result).encode('utf-8')
                headers = {"Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(body_bytes))}
                return ("200 OK", headers, body_bytes)

            if isinstance(result, str):
                body_bytes = result.encode('utf-8')
                # Detect if it's HTML content
                content_type = "text/html; charset=utf-8" if result.strip().startswith('<!DOCTYPE') or result.strip().startswith('<html') else "text/plain; charset=utf-8"
                headers = {"Content-Type": content_type, "Content-Length": str(len(body_bytes))}
                return ("200 OK", headers, body_bytes)

            if isinstance(result, bytes):
                headers = {"Content-Type": "application/octet-stream", "Content-Length": str(len(result))}
                return ("200 OK", headers, result)

            # Fallback
            body_bytes = str(result).encode('utf-8')
            headers = {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(body_bytes))}
            return ("200 OK", headers, body_bytes)

        except Exception as e:
            # return 500
            err = str(e).encode('utf-8')
            return ("500 Internal Server Error", {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(err))}, err)

    def handle_static(self, req, resp):
        """
        Phục vụ file tĩnh (như index.html, style.css).
        Nó gọi hàm build_response từ response.py.
        """
        raw = resp.build_response(req) 
        # "__RAW__" là một mã đặc biệt để báo cho hàm send()
        # rằng đây là dữ liệu thô, không cần compose nữa.
        return ("__RAW__", None, raw)

    def send(self, resp, triple):
        """
        Hàm gửi cuối cùng.
        Nó nhận bộ 3 (status, headers, body) và gửi đi.
        """
        status, headers, body = triple
        if status == "__RAW__":
            # Dùng cho file tĩnh (từ handle_static)
            return self.conn.sendall(body)
        
        # Dùng cho các response 401, 200 (từ handle_login)
        return self.conn.sendall(resp.compose(status=status, headers=headers, body=body))
        
    # === CÁC HÀM CŨ (KHÔNG XÓA THEO YÊU CẦU) ===
    @property
    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.
        ... (docstring giữ nguyên) ...
        """
        cookies = {}
        # Sửa lỗi: 'headers' không tồn tại, phải dùng 'req.headers'
        headers = req.headers 
        # Sửa lỗi: req.headers là dict, không lặp (iterate) trực tiếp được
        # Cần lấy 'cookie' header
        cookie_header = headers.get('cookie', '')
        if cookie_header:
            cookie_str = cookie_header
            for pair in cookie_str.split(";"):
                try: # Thêm try-except để tránh lỗi
                    key, value = pair.strip().split("=")
                    cookies[key] = value
                except ValueError:
                    pass # Bỏ qua cookie sai định dạng
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 
        ... (docstring giữ nguyên) ...
        """
        response = Response()

        # Set encoding.
        # Lỗi: get_encoding_from_headers không tồn tại
        # response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        if resp: # Thêm kiểm tra
            response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        # Lỗi: extract_cookies gọi sai (thiếu @property) và logic sai
        # response.cookies = extract_cookies(req) 
        # Thay bằng cách gọi đúng:
        response.cookies = self.extract_cookies(req, resp)


        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    # def get_connection(self, url, proxies=None):
    #     ... (giữ nguyên) ...


    def add_headers(self, request):
        """
        Add headers to the request.
        ... (giữ nguyên) ...
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 
        ... (docstring giữ nguyên) ...
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("user1", "password")

        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers
