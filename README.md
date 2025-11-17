Điều chỉnh lại IP cho khớp LAN IP trên máy -> wifi mình
Search IP LAN bằng cách: Terminal -> ipconfig -> dò IPv4 Address
Vào config -> proxy.conf -> ở dòng host " " chỉnh thành IP Máy mình -> thêm trường proxy pass theo IP mình (cùng port)

chạy các lệnh sau trên các terminal khác nhau
Terminal 1: python start_backend.py --server-ip <IP máy mày> --server-port 9000
Terminal 2: python start_proxy.py --server-ip 0.0.0.0 --server-port 8080
Terminal 3: python start_tracker.py --ip <IP máy mày> --server-port 9001
Terminal 4: python start_peer.py --ip <IP máy mày> --port 10000 --name Bao1 --tracker-ip <IP máy mày> --tracker-port 9001
Terminal 5-6-7-8: python start_peer.py --ip <IP máy mày> --port (bao nhiêu cũng đc) --name (tên gì cx dc) --tracker-ip <IP máy mày> --tracker-port 9001


Mở web: http://<IP máy mày>:8080/login.html -> username: admin / password: password -> F12 -> Tab Application -> Cookie thấy auth=true là đc

WebApp: http://<IP máy mày>:8080/chat -> Nhập đúng theo IP + Port mày đăng kí peer ở terminal là đc (Tên để gì cx đc) -> Select Channel (Sử dụng 2 hoặc nhiều máy kết nối cùng wifi hoặc bật nhiều tab google) -> Join Channel rồi gửi tin nhắn -> Kiểm tra F12 -> Network -> gói broadcast-peer -> 200 OK 
Kiểm tra cookie của WebAPP -> F12 -> Application -> Cookie auth=true

Test Local Trên Terminal: sau khi chạy start_peer.py, tiếp tục ghi #(Nhập channel mày chọn) VD: #general, rồi gửi tin nhắn bình thường, sang terminal có peer khác để check tin nhắn đã được gửi