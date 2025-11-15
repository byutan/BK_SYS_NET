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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""
from .dictionary import CaseInsensitiveDict



class Request():
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = None
        #: HTTP path
        self.path = None        
        # The cookies set used to create Cookie header
        self.cookies = None
        #: request body to send to the server.
        self.body = None
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None

    def extract_request_line(self, request):
        """
        Extract method, path and version from the first request line.
        Returns a 3-tuple or (None, None, None) on failure.
        NOTE: Do not rewrite "/" to "/index.html" here; leave routing to upper layers.
        """
        try:
            first_line = request.split('\r\n', 1)[0]
            method, path, version = first_line.strip().split()
            return method, path, version
        except Exception:
            return None, None, None

             
    def prepare_headers(self, request):
        """Prepares the given HTTP headers."""
        from .dictionary import CaseInsensitiveDict
        head = request.split('\r\n\r\n', 1)[0]
        lines = head.split('\r\n')
        headers = CaseInsensitiveDict()
        for line in lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key.strip()] = val.strip()
        return headers


    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""

        # Prepare the request line from the request header
        self.method, self.path, self.version = self.extract_request_line(request)

        #
        # @bksysnet Preapring the webapp hook with WeApRous instance
        # The default behaviour with HTTP server is empty routed
        #
        # TODO manage the webapp hook in this mounting point
        #

        # Routes / hook
        self.routes = routes or {}

        if self.routes:
            # Prefer (method, path), allow path-only fallback
            self.hook = self.routes.get((self.method, self.path)) or self.routes.get(self.path)
            # print("[Request] Hook {}".format(self.hook))

        # Headers
        self.headers = self.prepare_headers(request)

        # Cookies
        cookie_str = self.headers.get('Cookie', '') or self.headers.get('cookie', '')
        self.cookies = {}
        if cookie_str:
            for cookie_pair in cookie_str.split(';'):
                cookie_pair = cookie_pair.strip()
                if '=' in cookie_pair:
                    k, v = cookie_pair.split('=', 1)
                    self.cookies[k.strip()] = v.strip()

        # Body (bytes) — sliced by Content-Length if present
        head, body_bytes = self.split_head_body(request)
        try:
            cl = int(self.headers.get('Content-Length', '0') or 0)
        except Exception:
            cl = 0
        if cl > 0 and len(body_bytes) >= cl:
            body_bytes = body_bytes[:cl]
        self.body = body_bytes  # keep raw bytes; adapter can decode on demand

        return

    def prepare_body(self, data, files, json=None):
        self.prepare_content_length(self.body)
        self.body = body
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        return

    def prepare_content_length(self, body):
        self.headers["Content-Length"] = "0"
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        return


    def prepare_auth(self, auth, url=""):
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        return   


    def prepare_cookies(self, cookies):
        self.headers["Cookie"] = cookies

    def split_head_body(self, request: str):
        """
        Split raw HTTP message into (head:str, body:bytes).
        - Accepts either str or bytes as input.
        - Returns the header section as UTF-8 text (best-effort) and the raw body bytes.
        """
        if isinstance(request, bytes):
            raw = request
        else:
            # Best-effort encode so we can safely partition on CRLFCRLF
            raw = request.encode("utf-8", "ignore")

        # Split on the first empty line (CRLFCRLF)
        head_bytes, sep, body_bytes = raw.partition(b"\r\n\r\n")

        # Decode headers to str for easier parsing; keep body as bytes
        head_str = head_bytes.decode("utf-8", "ignore")
        return head_str, body_bytes
