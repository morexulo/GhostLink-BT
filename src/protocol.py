import struct
import hashlib
import socket
from typing import Optional, Tuple, Generator
from .logger import setup_logger
from .config import HEADER_SIZE, BUFFER_SIZE

logger = setup_logger("protocol_manager")

class ProtocolError(Exception):
    pass

class IntegrityError(ProtocolError):
    pass

class ConnectionClosed(ProtocolError):
    pass

class ProtocolManager:
    """
    Handles the low-level framing, verification, and chunking of messages.
    Protocol Layout:
    [Header (37 bytes)] + [Payload (Variable Size)]
    
    Header Format:
    ! (Network Endian)
    B (1 byte)  : Message Type
    I (4 bytes) : Payload Length (unsigned int)
    32s (32 bytes): SHA-256 Hash of the payload
    """
    
    def __init__(self):
        self.header_struct = struct.Struct('!BI32s')
        if self.header_struct.size != HEADER_SIZE:
             raise ValueError(f"Header size mismatch. Expected {HEADER_SIZE}, got {self.header_struct.size}")

    def create_packet(self, msg_type: int, payload: bytes) -> bytes:
        payload_size = len(payload)
        payload_hash = hashlib.sha256(payload).digest()
        
        header = self.header_struct.pack(msg_type, payload_size, payload_hash)
        return header + payload

    def send_message(self, sock: socket.socket, msg_type: int, payload: bytes):
        try:
            packet = self.create_packet(msg_type, payload)
            sock.sendall(packet) # Blocking send
            logger.debug(f"Sent message type {msg_type}, size {len(payload)} bytes.")
        except OSError as e:
            logger.error(f"Socket error during send: {e}")
            raise ConnectionClosed("Socket connection failed during send.") from e

    def receive_message(self, sock: socket.socket) -> Tuple[int, bytes]:
        try:
            # 1. Read Header
            header_data = self._recv_all(sock, HEADER_SIZE)
            if not header_data:
                raise ConnectionClosed("Socket closed while reading header.")
            
            msg_type, payload_size, expected_hash = self.header_struct.unpack(header_data)
            
            # 2. Read Payload
            payload_data = self._recv_all(sock, payload_size)
            if not payload_data:
                raise ConnectionClosed("Socket closed while reading payload.")
            
            # 3. Validate Integrity
            actual_hash = hashlib.sha256(payload_data).digest()
            if actual_hash != expected_hash:
                logger.error("Hash mismatch! Potential data corruption or tampering.")
                raise IntegrityError("Payload hash verification failed.")
            
            logger.debug(f"Received message type {msg_type}, size {payload_size} bytes.")
            return msg_type, payload_data
            
        except ConnectionClosed:
            raise
        except struct.error as e:
            logger.error(f"Header parsing error: {e}")
            raise ProtocolError("Invalid header format.") from e
        except OSError as e:
            logger.error(f"Socket error during receive: {e}")
            raise ConnectionClosed("Socket error.") from e

    def _recv_all(self, sock: socket.socket, num_bytes: int) -> Optional[bytes]:
        data = bytearray()
        while len(data) < num_bytes:
            try:
                # sock.recv(bufsize, flags)
                chunk = sock.recv(min(BUFFER_SIZE, num_bytes - len(data)))
                if not chunk:
                    if len(data) == 0:
                        return None 
                    else:
                         logger.warning(f"Incomplete read. Expected {num_bytes}, got {len(data)}")
                         return None
                data.extend(chunk)
            except OSError as e:
                logger.error(f"Receive error: {e}")
                raise
        return bytes(data)
