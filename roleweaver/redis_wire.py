"""Small bounded RESP2 client; each call owns its socket (thread safe)."""

import socket


class Redis:
    def __init__(self, host="127.0.0.1", port=6379):
        self.address = (host, int(port))

    def call(self, *args):
        values = [str(v).encode("utf-8") for v in args]
        packet = b"*%d\r\n" % len(values) + b"".join(
            b"$%d\r\n" % len(v) + v + b"\r\n" for v in values
        )
        with socket.create_connection(self.address, timeout=2) as sock:
            sock.sendall(packet)
            with sock.makefile("rb") as stream:
                return self._read(stream)

    def _read(self, stream):
        line = stream.readline(65537)
        if not line.endswith(b"\r\n"):
            raise ConnectionError("Incomplete Redis response")
        kind, value = line[:1], line[1:-2]
        if kind == b"-":
            raise ConnectionError("Redis rejected command")
        if kind == b"+":
            return value.decode("utf-8")
        if kind == b":":
            return int(value)
        if kind == b"$":
            length = int(value)
            if length == -1:
                return None
            if not 0 <= length <= 1048576:
                raise ValueError("Redis payload too large")
            data = stream.read(length + 2)
            if len(data) != length + 2 or data[-2:] != b"\r\n":
                raise ConnectionError("Incomplete Redis payload")
            return data[:-2].decode("utf-8")
        raise ValueError("Unsupported Redis response")
