import socket
import logging
import threading
from .logger import setup_logger
from .protocol import ProtocolManager, ConnectionClosed
from .encryption import EncryptionManager

# Use NATIVE WINDOWS RFCOMM SOCKETS instead of Bleak (Client) + Bleak (Server not work)
logger = setup_logger("bluetooth_client")

class BluetoothClient:
    def __init__(self, target_address):
        self.server_mac = target_address
        self.client_sock = None
        self.running = False
        self.on_message_received = None
        self.on_status_changed = None
        self.encryption_manager = None
        
    def start(self, encryption_key: bytes):
        self.encryption_manager = EncryptionManager(encryption_key)
        self.running = True
        self.protocol_manager = ProtocolManager()
        
        while self.running:
            try:
                if self.on_status_changed:
                    self.on_status_changed("Connecting", self.server_mac)
                    
                self.client_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                # RFCOMM Port 4 matching server
                logger.info(f"Connecting to {self.server_mac}:4...")
                self.client_sock.connect((self.server_mac, 4))
                
                logger.info("Connected!")
                if self.on_status_changed:
                    self.on_status_changed("Connected", self.server_mac)
                
                while self.running:
                    msg_type, payload = self.protocol_manager.receive_message(self.client_sock)
                    try:
                        decrypted_data = self.encryption_manager.decrypt(payload)
                        if self.on_message_received:
                            self.on_message_received(msg_type, decrypted_data)
                    except Exception as e:
                        logger.error(f"Decryption failed: {e}")
                        
            except ConnectionClosed:
                logger.warning("Connection closed by server.")
            except Exception as e:
                logger.error(f"Connection failed: {e}.")
                if self.on_status_changed:
                    self.on_status_changed("Disconnected", f"Retry: {e}")
                import time
                time.sleep(2.0)
            finally:
                if self.client_sock:
                    self.client_sock.close()
                    self.client_sock = None
                if not self.running:
                    break

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
