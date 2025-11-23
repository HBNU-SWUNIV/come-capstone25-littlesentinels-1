import socket
import json

class SocketSender:
    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        print(f"[SOCKET] Connected to {self.host}:{self.port}")

    def send_data(self, data: dict):
        if self.sock is None:
            raise RuntimeError("Socket not connected. Call connect() first.")
        try:
            json_data = json.dumps(data)
            self.sock.sendall(json_data.encode('utf-8'))
            print(f"[SOCKET] Sent: {json_data}")
        except Exception as e:
            print(f"[SOCKET] Error sending data: {e}")

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            print("[SOCKET] Connection closed.")
