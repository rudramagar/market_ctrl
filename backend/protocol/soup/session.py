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
        self.tcp_socket = tcp_socket
        self.session = ""
        self.next_sequence = 1

    def connect(self):
        self.tcp_socket.connect()

    def login(
        self,
        username,
        password,
        session="",
        sequence=1,
    ):
        request = encode_login_request(
            username=username,
            password=password,
            session=session,
            sequence=sequence,
        )

        self.tcp_socket.send_all(request)

        packet = self.receive_packet()

        if packet.packet_type == "J":
            reason = decode_login_rejected(packet.payload)
            raise SoupLoginRejectedError(
                "Soup login rejected: %s" % reason
            )

        if packet.packet_type != "A":
            raise SoupError(
                "expected login accepted, received %r"
                % packet.packet_type
            )

        accepted = decode_login_accepted(packet.payload)

        self.session = accepted.session
        self.next_sequence = accepted.sequence

        return accepted

    def send_unsequenced(self, payload):
        self.tcp_socket.send_all(
            encode_packet("U", payload)
        )

    def send_heartbeat(self):
        self.tcp_socket.send_all(
            encode_packet("H")
        )

    def logout(self):
        if self.tcp_socket.connected:
            self.tcp_socket.send_all(
                encode_packet("O")
            )

    def receive_packet(self):
        length_data = self.tcp_socket.read_exact(2)
        packet_length = struct.unpack(">H", length_data)[0]

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

        body = self.tcp_socket.read_exact(packet_length)
        packet = decode_packet(body)

        if packet.packet_type == "Z":
            raise SoupEndOfSessionError(
                "Soup session ended"
            )

        if packet.packet_type == "S":
            self.next_sequence += 1

        return packet

    def receive_sequenced(self):
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
        self.tcp_socket.close()

    @property
    def connected(self):
        return self.tcp_socket.connected
