"""Lightweight MJPEG streaming server using only stdlib + cv2. No extra dependencies."""

import socket
import threading
import cv2
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

_latest_jpeg = None
_frame_event = threading.Event()
_frame_lock = threading.Lock()

JPEG_QUALITY = 85


def update_frame(frame):
    """Call from the CV loop to push the latest BGR/RGB frame (sent at native resolution)."""
    global _latest_jpeg
    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    with _frame_lock:
        _latest_jpeg = jpeg.tobytes()
    _frame_event.set()


class _StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/stream":
            self.send_response(302)
            self.send_header("Location", "/stream")
            self.end_headers()
            return

        # Disable Nagle and shrink send buffer to prevent frame queuing
        sock = self.request
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        try:
            while True:
                # Block until a new frame arrives (no polling)
                _frame_event.wait()
                _frame_event.clear()
                with _frame_lock:
                    jpeg = _latest_jpeg
                if jpeg is None:
                    continue
                self.wfile.write(
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                    + jpeg + b"\r\n"
                )
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, format, *args):
        pass


def _get_local_ip():
    """Get LAN IP address, or None if no network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def start(port=5000):
    """Start MJPEG server in a daemon thread. Returns True if started, False if no network."""
    ip = _get_local_ip()
    if ip is None:
        print("No network detected - streaming disabled")
        return False
    class _ThreadedServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
    server = _ThreadedServer(("0.0.0.0", port), _StreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Stream available at: http://{ip}:{port}/stream")
    return True
