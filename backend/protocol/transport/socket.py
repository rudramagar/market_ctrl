import socket

from backend.protocol.errors import (
    ConnectionClosedError,
    TransportError,
)

class TcpSocket:
    """TCP connection with exact-length reads."""

    def __init__(
        self,
        host,
        port,
        timeout_seconds=10.0,
    ):
        self.host = host
        self.port = int(port)
        self.timeout_seconds = float(timeout_seconds)
        self._socket = None

    def connect(self):
        if self.connected:
            return

        connection = None

        try:
            connection = socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout_seconds,
            )
            connection.settimeout(self.timeout_seconds)
            self._socket = connection

        except OSError as exc:
            if connection is not None:
                connection.close()

            raise TransportError(
                "failed to connect to %s:%d: %s"
                % (self.host, self.port, exc)
            ) from exc

    def send_all(self, data):
        if not self.connected:
            raise TransportError("socket is not connected")

        try:
            self._socket.sendall(data)
        except OSError as exc:
            raise TransportError(
                "failed to send data: %s" % exc
            ) from exc

    def read_exact(self, size):
        if not self.connected:
            raise TransportError("socket is not connected")

        if size < 0:
            raise ValueError("size cannot be negative")

        data = bytearray()

        while len(data) < size:
            try:
                chunk = self._socket.recv(size - len(data))
            except OSError as exc:
                raise TransportError(
                    "failed to receive data: %s" % exc
                ) from exc

            if not chunk:
                raise ConnectionClosedError(
                    "connection closed after %d of %d bytes"
                    % (len(data), size)
                )

            data.extend(chunk)

        return bytes(data)

    def set_timeout(self, timeout_seconds):
        self.timeout_seconds = float(timeout_seconds)

        if self.connected:
            self._socket.settimeout(self.timeout_seconds)

    def close(self):
        if self._socket is None:
            return

        try:
            self._socket.close()
        finally:
            self._socket = None

    @property
    def connected(self):
        return self._socket is not None

    @property
    def raw_socket(self):
        return self._socket
