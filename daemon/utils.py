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

# Sửa lỗi: Import 'urlparse' và 'unquote' từ 'urllib.parse'
from urllib.parse import urlparse, unquote

def get_auth_from_url(url):
    """Given a url with authentication components, extract them into a tuple of
    username,password.

    :rtype: (str,str)
    """
    parsed = urlparse(url)

    try:
        # ---- START OF COMPLETED TODO ----
        
        # 'parsed.username' và 'parsed.password' lấy thông tin auth từ URL
        # 'unquote' dùng để xử lý các ký tự đặc biệt (ví dụ: 'user%40name' -> 'user@name')
        
        username = unquote(parsed.username) if parsed.username else ""
        password = unquote(parsed.password) if parsed.password else ""
        auth = (username, password)
        
        # ---- END OF COMPLETED TODO ----
        
    except (AttributeError, TypeError):
        # Fallback nếu parsed object không có thuộc tính username/password
        auth = ("", "")

    return auth