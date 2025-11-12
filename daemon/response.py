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
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class: `Response <Response>` object to manage and persist 
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests. 

The current version supports MIME type detection, content loading and header formatting
"""
import datetime
import os
import mimetypes
from .dictionary import CaseInsensitiveDict

BASE_DIR = ""

class Response():   
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    :class:`Response <Response>` object encapsulates headers, content, 
    status code, cookies, and metadata related to the request-response cycle.
    It is used to construct and serve HTTP responses in a custom web server.

    :attrs status_code (int): HTTP status code (e.g., 200, 404).
    :attrs headers (dict): dictionary of response headers.
    :attrs url (str): url of the response.
    :attrsencoding (str): encoding used for decoding response content.
    :attrs history (list): list of previous Response objects (for redirects).
    :attrs reason (str): textual reason for the status code (e.g., "OK", "Not Found").
    :attrs cookies (CaseInsensitiveDict): response cookies.
    :attrs elapsed (datetime.timedelta): time taken to complete the request.
    :attrs request (PreparedRequest): the original request object.

    Usage::

      >>> import Response
      >>> resp = Response()
      >>> resp.build_response(req)
      >>> resp
      <Response>
    """

    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body",
        "reason",
    ]


    def __init__(self, request=None):
        """
        Initializes a new :class:`Response <Response>` object.

        : params request : The originating request object.
        """

        self._content = False
        self._content_consumed = False
        self._next = None

        #: Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code = None

        #: Case-insensitive Dictionary of Response Headers.
        #: For example, ``headers['content-type']`` will return the
        #: value of a ``'Content-Type'`` response header.
        self.headers = {}

        #: URL location of Response.
        self.url = None

        #: Encoding to decode with when accessing response text.
        self.encoding = None

        #: A list of :class:`Response <Response>` objects from
        #: the history of the Request.
        self.history = []

        #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
        self.reason = None

        #: A of Cookies the response headers.
        self.cookies = CaseInsensitiveDict()

        #: The amount of time elapsed between sending the request
        self.elapsed = datetime.timedelta(0)

        #: The :class:`PreparedRequest <PreparedRequest>` object to which this
        #: is a response.
        self.request = None


    def get_mime_type(self, path):
        """
        Determines the MIME type of a file based on its path.

        "params path (str): Path to the file.

        :rtype str: MIME type string (e.g., 'text/html', 'image/png').
        """

        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'


    def prepare_content_type(self, mime_type='text/html'):
        """
        Prepares the Content-Type header and determines the base directory
        for serving the file based on its MIME type.

        :params mime_type (str): MIME type of the requested resource.

        :rtype str: Base directory path for locating the resource.

        :raises ValueError: If the MIME type is unsupported.
        """
        #Kiểm tra đảm bảo đầu vào là một chuỗi hợp lệ
        if not isinstance(mime_type, str) or '/' not in mime_type:
            raise ValueError("Invalid MIME type format: {!r}".format(mime_type))
        #Tách chuỗi MIME type thành hai phần.
        main_type, sub_type = mime_type.split('/', 1)
        #.strip() và .lower() để loại bỏ khoảng trắng thừa và chuẩn hóa chữ thường.
        main_type, sub_type = main_type.strip().lower(), sub_type.strip().lower()
        print("[Response] processing MIME main_type={} | sub_type={}".format(main_type, sub_type))

        # Khởi tạo headers nếu chưa có
        if not hasattr(self, "headers") or self.headers is None:
            self.headers = {}

       
        # NOTE: Keep www/ for html, static/ for assets, apps/ for app bundles.
        base_map = {
            "text/html":     os.path.join(BASE_DIR, "www"),
            "text/css":      os.path.join(BASE_DIR, "static"),
            "text/plain":    os.path.join(BASE_DIR, "static"),
            "text/javascript": os.path.join(BASE_DIR, "static"),
            "application/javascript": os.path.join(BASE_DIR, "static"),
            "image":         os.path.join(BASE_DIR, "static"),
            "font":          os.path.join(BASE_DIR, "static"),
            "audio":         os.path.join(BASE_DIR, "static"),
            "video":         os.path.join(BASE_DIR, "static"),
            # For app payloads served as files (e.g., zip, wasm):
            "application":   os.path.join(BASE_DIR, "apps"),
        }

        # Decide base_dir
        full = f"{main_type}/{sub_type}"
        if full in base_map:
            base_dir = base_map[full]
        elif main_type in base_map:
            base_dir = base_map[main_type]
        else:
            # Fallback to static for unknown types
            base_dir = os.path.join(BASE_DIR, "static")

        if main_type == "text":
            self.headers["Content-Type"] = f"{full}; charset={'utf-8'}"
        elif main_type == "application" and sub_type in {"json", "xml"}:
            self.headers["Content-Type"] = full
        elif main_type in {"image", "audio", "video", "font"}:
            self.headers["Content-Type"] = full
        else:
            self.headers["Content-Type"] = full or "application/octet-stream"

        return base_dir


    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.

        :params path (str): relative path to the file.
        :params base_dir (str): base directory where the file is located.

        :rtype tuple: (int, bytes) representing content length and content data.
        """

        filepath = os.path.join(base_dir, path.lstrip('/'))

        print("[Response] serving the object at location {}".format(filepath))
        #đọc file và trả về nội dung
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            return len(content), content
        except Exception as e:
            print("[Response] Error reading file: {}".format(e))
            return 0, b""


    def build_response_header(self, request):
        """
        Constructs the HTTP response headers based on the class:`Request <Request>
        and internal attributes.

        :params request (class:`Request <Request>`): incoming request object.

        :rtypes bytes: encoded HTTP response header.
        """
        reqhdr = request.headers
        rsphdr = self.headers

        #Build dynamic headers
        headers = {
                "Accept": "{}".format(reqhdr.get("Accept", "application/json")),
                "Accept-Language": "{}".format(reqhdr.get("Accept-Language", "en-US,en;q=0.9")),
                "Authorization": "{}".format(reqhdr.get("Authorization", "Basic <credentials>")),
                "Cache-Control": "no-cache",
                "Content-Type": "{}".format(self.headers['Content-Type']),
                "Content-Length": "{}".format(len(self._content)),
#                "Cookie": "{}".format(reqhdr.get("Cookie", "sessionid=xyz789")), #dummy cooki
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
                "Date": "{}".format(datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")),
                "Max-Forward": "10",
                "Pragma": "no-cache",
                "Proxy-Authorization": "Basic dXNlcjpwYXNz",  # example base64
                "Warning": "199 Miscellaneous warning",
                "User-Agent": "{}".format(reqhdr.get("User-Agent", "Chrome/123.0.0.0")),
            }

        # Header text alignment
        fmt_header = "HTTP/1.1 {} {}\r\n".format(self.status_code, self.reason)
        
        for key, value in headers.items():
            fmt_header += "{}: {}\r\n".format(key, value)
        
        #
        # TODO prepare the request authentication
        fmt_header += "\r\n"
        return fmt_header.encode('utf-8')


    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.

        :rtype bytes: Encoded 404 response.
        """

        return (
                "HTTP/1.1 404 Not Found\r\n"
                "Accept-Ranges: bytes\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 13\r\n"
                "Cache-Control: max-age=86000\r\n"
                "Connection: close\r\n"
                "\r\n"
                "404 Not Found"
            ).encode('utf-8')


    def build_response(self, request):
        """
        Builds a full HTTP response including headers and content based on the request.

        :params request (class:`Request <Request>`): incoming request object.

        :rtype bytes: complete HTTP response using prepared headers and content.
        """

        path = request.path

        mime_type = self.get_mime_type(path)
        print("[Response] {} path {} mime_type {}".format(request.method, request.path, mime_type))

        base_dir = ""

        try:
            base_dir = self.prepare_content_type(mime_type=mime_type)
        except ValueError:
            print("[Response] Error preparing content type: {}".format())
            return self.build_notfound()

        print("[Response] base_dir {}".format(base_dir))
        print("[Response] path {}".format(path))

        c_len, self._content = self.build_content(path, base_dir)
     #Kiểm tra file rỗng/không tồn tại
        if c_len <= 0:
            return self.build_notfound()

        self._header = self.build_response_header(request)

        return self._header + self._content
    def compose(self, status: str = "200 OK", headers: dict | None = None, body: bytes | str = b""):
        """
        Build a full HTTP response bytes from status, headers and body.
        This keeps one unified way to return responses from handlers.
        """
        headers = headers or {}
        # Chuyển body sang bytes nếu nó là str
        if isinstance(body, str):
            body = body.encode("utf-8", "ignore")

        # Đo độ dài body và thêm các header cần thiết
        if "Content-Length" not in headers:
            headers["Content-Length"] = str(len(body))
        #Nếu  chưa set, nó tự động thêm Connection: close
        if "Connection" not in headers:
            headers["Connection"] = "close"

        # Status-Line + headers
        status_line = f"HTTP/1.1 {status}\r\n"
        head = status_line + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"

        return head.encode("utf-8") + body
