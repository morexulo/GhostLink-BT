import asyncio
import logging
from .logger import setup_logger
from .protocol import ProtocolManager
from .encryption import EncryptionManager
from .config import SERVICE_UUID

# BLE server on Windows/macOS is tricky.
# Bleak is MOSTLY a client library.
# However, PyBluetooth is often needed for server which Bleak doesn't fully support on all platforms yet.
# BUT, Bleak DOES support advertising on Windows 10 since 2024 (via WinRT).
# Wait, Bleak is mainly Client.
# On Windows, standard Bleak cannot easily create a GATT Server.
# We need `winsdk` or `bleak-winrt` for server, OR use the `bleak` peripheral mode if available.

# CRITICAL: Bleak is primarily a Central (Client) library.
# Creating a Peripheral (Server) on Windows with Python is complex and not fully supported by standard Bleak.
# We might need to use `bless` (Bluetooth Low Energy Server Supplement) which wraps Bleak/Bluez/CoreBluetooth.

# Let's check installed packages. If not installed, we can't run server easily.
# Alternative: RFCOMM via standard sockets (socket.AF_BLUETOOTH) IS supported on Windows 10 since build 10565.
# But `pybluez` failed.
# Let's try to stick to Bleak for Client, but for Server we need a solution.
# Actually, if we want PC-to-PC, both need to be Server/Client or one Central/One Peripheral.
# Windows 10/11 supports GATT Server.

# Let's try `bless` for server if we use BLE.
# OR, use standard `socket` with `socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM`.
# This is native in Python 3.9+ on Windows! We don't need pybluez!
# PyBluez is only for old Windows stacks or Linux.
# The user asked for "no internet", "native windows".
# Native sockets are the BEST options for RFCOMM on Windows.

# STRATEGY CHANGE:
# Instead of fighting with BLE Server on Windows (which is hard in Python),
# Let's use NATIVE PYTHON SOCKETS for RFCOMM.
# They work on Windows 10/11 without external libs (except standard library).
# We only need `pybluez` for SDP advertising, BUT we can simply bind to a known port
# and the client can connect to that MAC+Port.

logger = setup_logger("bluetooth_server")

import socket

class BluetoothServer:
    def __init__(self):
        self.server_sock = None
        self.client_sock = None
        self.running = False
        self.protocol_manager = None # Re-init below
        self.encryption_manager = None
        self.on_message_received = None
        self.on_status_changed = None

    def start(self, encryption_key: bytes):
        from .protocol import ProtocolManager # Use the ORIGINAL RFCOMM manager
        self.protocol_manager = ProtocolManager()
        self.encryption_manager = EncryptionManager(encryption_key)
        
        self.running = True
        
        try:
            # Native Windows RFCOMM
            self.server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            self.server_sock.bind((socket.BDADDR_ANY, 4)) # Port 4 (arbitrary, must match client)
            self.server_sock.listen(1)
            
            port = self.server_sock.getsockname()[1]
            logger.info(f"RFCOMM Server listening on channel {port}")
            
            if self.on_status_changed:
                self.on_status_changed("Listening", port)
                
            while self.running:
                logger.info("Waiting for connection...")
                try:
                    client, addr = self.server_sock.accept()
                    self.client_sock = client
                    logger.info(f"Accepted connection from {addr}")
                    
                    if self.on_status_changed:
                        self.on_status_changed("Connected", addr)
                        
                    self._handle_client()
                except OSError as e:
                    if self.running:
                        logger.error(f"Accept failed: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"Server Fatal Error: {e}")
            if self.on_status_changed:
                self.on_status_changed("Error", str(e))
        finally:
            self.stop()

    def _handle_client(self):
        try:
            while self.running and self.client_sock:
                msg_type, payload = self.protocol_manager.receive_message(self.client_sock)
                try:
                    decrypted = self.encryption_manager.decrypt(payload)
                    if self.on_message_received:
                        self.on_message_received(msg_type, decrypted)
                except Exception as e:
                    logger.error(f"Decryption error: {e}")
                    
        except Exception as e:
            logger.info(f"Client disconnected: {e}")
        finally:
            if self.client_sock:
                self.client_sock.close()
            self.client_sock = None
            if self.on_status_changed:
                self.on_status_changed("Disconnected", None)

    def send_message(self, msg_type: int, data: bytes):
        if not self.client_sock: 
            return
        try:
            encrypted = self.encryption_manager.encrypt(data)
            self.protocol_manager.send_message(self.client_sock, msg_type, encrypted)
        except Exception as e:
            logger.error(f"Send failed: {e}")

    def stop(self):
        self.running = False
        if self.client_sock:
            self.client_sock.close()
        if self.server_sock:
            self.server_sock.close()
