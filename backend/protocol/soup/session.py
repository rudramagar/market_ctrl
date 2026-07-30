import struct

from backend.protocol.errors import (
    SoupEndOfSessionError,
    SoupError,
    SoupLoginRejectedError,
)
from backend.protocol.soup.message_format import (
    MAX_SOUP_PACKET_SIZE,
    decode_login_accepted,
    decode_login_rejected,
    decode_packet,
    encode_login_request,
    encode_packet,
)


class SoupSession:
    """SoupBinTCP session shared by API and DROP clients."""

    def __init__(self, tcp_socket):
        if tcp_socket is None:
            raise ValueError(
                "TCP socket is required"
            )

        self.tcp_socket = tcp_socket

        self.requested_session = None
        self.requested_sequence = None

        self.accepted_session = None
        self.accepted_sequence = None

        # Compatibility properties used by existing clients.
        self.session = ""
        self.next_sequence = None

        self._login_accepted = None

    @property
    def connected(self):
        return self.tcp_socket.connected

    @property
    def logged_in(self):
        return (
            self._login_accepted is not None
            and self.connected
        )

    @property
    def login_accepted(self):
        return self._login_accepted

    def connect(self):
        """Open the underlying TCP connection."""

        if self.connected:
            return

        self.tcp_socket.connect()

    def login(
        self,
        username,
        password,
        session="",
        sequence=1,
    ):
        """Send a Soup login request and return its acceptance."""

        if not self.connected:
            raise SoupError(
                "TCP connection is not open"
            )

        if self._login_accepted is not None:
            raise SoupError(
                "Soup session is already logged in"
            )

        sequence = int(sequence)

        if sequence < 0:
            raise ValueError(
                "sequence cannot be negative"
            )

        requested_session = (
            session
            if session is not None
            else ""
        )

        request = encode_login_request(
            username=username,
            password=password,
            session=requested_session,
            sequence=sequence,
        )

        self.requested_session = (
            requested_session
        )
        self.requested_sequence = sequence

        self.tcp_socket.send_all(request)

        packet = self.receive_packet()

        if packet.packet_type == "J":
            reason = decode_login_rejected(
                packet.payload
            )

            raise SoupLoginRejectedError(
                reason=reason
            )

        if packet.packet_type != "A":
            raise SoupError(
                "expected login accepted, received %r"
                % packet.packet_type
            )

        accepted = decode_login_accepted(
            packet.payload
        )

        self.accepted_session = accepted.session
        self.accepted_sequence = accepted.sequence

        self.session = accepted.session
        self.next_sequence = accepted.sequence

        self._login_accepted = accepted

        return accepted

    def send_unsequenced(self, payload):
        """Send one unsequenced Soup payload."""

        self._require_login()

        self.tcp_socket.send_all(
            encode_packet(
                "U",
                payload,
            )
        )

    def send_heartbeat(self):
        """Send a Soup client heartbeat."""

        self._require_login()

        self.tcp_socket.send_all(
            encode_packet("H")
        )

    def logout(self):
        """Send a Soup logout packet when connected."""

        if not self.connected:
            return

        if self._login_accepted is None:
            return

        self.tcp_socket.send_all(
            encode_packet("O")
        )

    def receive_packet(self):
        """Receive and decode one Soup packet."""

        if not self.connected:
            raise SoupError(
                "TCP connection is not open"
            )

        length_data = self.tcp_socket.read_exact(
            2
        )

        packet_length = struct.unpack(
            ">H",
            length_data,
        )[0]

        if packet_length < 1:
            raise SoupError(
                "invalid Soup packet length: %d"
                % packet_length
            )

        if packet_length > MAX_SOUP_PACKET_SIZE:
            raise SoupError(
                "Soup packet exceeds maximum size: %d"
                % packet_length
            )

        body = self.tcp_socket.read_exact(
            packet_length
        )

        packet = decode_packet(body)

        if packet.packet_type == "Z":
            raise SoupEndOfSessionError(
                "Soup session ended"
            )

        if packet.packet_type == "S":
            if self.next_sequence is None:
                raise SoupError(
                    "Soup sequence is not initialized"
                )

            self.next_sequence += 1

        return packet

    def receive_sequenced(self):
        """Receive the next sequenced Soup payload."""

        self._require_login()

        while True:
            packet = self.receive_packet()

            if packet.packet_type == "H":
                continue

            if packet.packet_type != "S":
                raise SoupError(
                    "expected sequenced data, received %r"
                    % packet.packet_type
                )

            return packet.payload

    def close(self):
        """Close the TCP socket and reset session state."""

        self.tcp_socket.close()

        self._login_accepted = None

        self.requested_session = None
        self.requested_sequence = None

        self.accepted_session = None
        self.accepted_sequence = None

        self.session = ""
        self.next_sequence = None

    def _require_login(self):
        if not self.logged_in:
            raise SoupError(
                "Soup session is not logged in"
            )
