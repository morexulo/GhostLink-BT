from cryptography.fernet import Fernet, InvalidToken
from .logger import setup_logger

logger = setup_logger("encryption_manager")

class EncryptionManager:
    """
    Handles symmetric AES encryption and decryption using Fernet (AES-128-CBC + HMAC-SHA256).
    Ensures message integrity and confidentiality.
    """
    def __init__(self, key: bytes):
        """
        Initialize the EncryptionManager with a symmetric key.
        :param key: A URL-safe base64-encoded 32-byte key.
        """
        try:
            self.cipher_suite = Fernet(key)
            logger.info("EncryptionManager initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize EncryptionManager: {e}")
            raise ValueError("Invalid encryption key provided.") from e

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypts raw bytes.
        :param data: The plaintext data to encrypt.
        :return: The encrypted ciphertext.
        """
        if not data:
            return b""
        try:
            encrypted_data = self.cipher_suite.encrypt(data)
            return encrypted_data
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, token: bytes) -> bytes:
        """
        Decrypts the ciphertext.
        :param token: The encrypted token (ciphertext).
        :return: The original plaintext data.
        :raises ValueError: If the token is invalid or tampered with.
        """
        if not token:
            return b""
        try:
            decrypted_data = self.cipher_suite.decrypt(token)
            return decrypted_data
        except InvalidToken:
            logger.warning("Decryption failed: Invalid token or integrity check failed.")
            raise ValueError("Decryption failed: Invalid token.")
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
