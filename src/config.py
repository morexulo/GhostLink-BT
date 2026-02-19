APP_UUID = "e4d5f6a7-b8c9-4d0e-f1a2-b3c4d5e6f7a8"
SERVICE_UUID = "00001101-0000-1000-8000-00805F9B34FB" 
SERVICE_NAME = "GhostLinkBT"

# --- Communication Settings ---
BUFFER_SIZE = 4096 
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024 

# --- Protocol Constants ---
MSG_TYPE_TEXT = 0x01
MSG_TYPE_IMAGE = 0x02
MSG_TYPE_FILE = 0x03
MSG_TYPE_SYSTEM = 0xFF

HEADER_SIZE = 1 + 4 + 32 

# --- Encryption ---
DEFAULT_SECRET_KEY = b'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v=' 

# --- Timeout & Reconnection ---
SOCKET_TIMEOUT = 5.0
RECONNECT_INTERVAL = 2.0
MAX_RETRIES = 5

# --- Logging ---
import logging
import os
LOG_LEVEL = logging.DEBUG
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DIR = "logs"

# --- UI & Image Defaults ---
IMAGE_MAX_WIDTH = 1920
IMAGE_MAX_HEIGHT = 1080
IMAGE_QUALITY = 85
THUMBNAIL_SIZE = (300, 300)
PC_NAME = os.getenv('COMPUTERNAME', 'Unknown PC')

