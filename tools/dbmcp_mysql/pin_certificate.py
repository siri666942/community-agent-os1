"""Bootstrap the named server's TLS certificate without transmitting credentials.

Trust on first use: inspect the fingerprint out of band if stronger identity
verification is required. Never replace an existing pin automatically.
"""
import hashlib
import re
import socket
import ssl
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
target = ROOT / ".dbmcp" / "server-cert.pem"
if target.exists():
    raise SystemExit("Certificate pin already exists; not replacing it")
config = (ROOT / "配置文件文字版.txt").read_text(encoding="utf-8-sig")
host = re.search(r"^主机\s*[：:]\s*(\S+)", config, re.M).group(1)
port = int(re.search(r"^端口\s*[：:]\s*(\d+)", config, re.M).group(1))

def exact(sock, length):
    result = b""
    while len(result) < length:
        chunk = sock.recv(length - len(result))
        if not chunk:
            raise RuntimeError("Incomplete MySQL handshake")
        result += chunk
    return result

with socket.create_connection((host, port), timeout=8) as sock:
    header = exact(sock, 4)
    exact(sock, int.from_bytes(header[:3], "little"))
    payload = struct.pack("<IIB23s", 1 | 512 | 2048 | 32768, 16777216, 45, b"")
    sock.sendall(len(payload).to_bytes(3, "little") + b"\x01" + payload)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Certificate discovery only; no authentication.
    with context.wrap_socket(sock, server_hostname=host) as secure:
        der = secure.getpeercert(binary_form=True)
target.parent.mkdir(exist_ok=True)
target.write_text(ssl.DER_cert_to_PEM_cert(der), encoding="ascii")
print("Saved initial server certificate; SHA256=" + hashlib.sha256(der).hexdigest())
