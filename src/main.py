import sys
import threading
import time
import argparse
from .config import DEFAULT_SECRET_KEY, MSG_TYPE_TEXT, MSG_TYPE_SYSTEM
from .logger import setup_logger
from .bluetooth_server import BluetoothServer
from .bluetooth_client import BluetoothClient

logger = setup_logger("main")

def run_server():
    server = BluetoothServer()
    
    # Start server in a separate thread so we can send input from main thread
    server_thread = threading.Thread(target=server.start, args=(DEFAULT_SECRET_KEY,), daemon=True)
    server_thread.start()
    
    logger.info("Server running in background. Type messages to send.")
    logger.info("Type '/quit' to exit.")
    
    try:
        while True:
            msg = input()
            if msg == '/quit':
                break
            if server.client_sock:
                server.send_message(MSG_TYPE_TEXT, msg.encode('utf-8'))
            else:
                logger.warning("No client connected. Cannot send.")
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        sys.exit(0)

def run_client(target_address=None):
    client = BluetoothClient(target_address)
    
    # Start client connection loop in background
    client_thread = threading.Thread(target=client.start, args=(DEFAULT_SECRET_KEY,), daemon=True)
    client_thread.start()
    
    logger.info("Client running in background. Type messages to send.")
    logger.info("Type '/quit' to exit.")
    
    try:
        while True:
            msg = input()
            if msg == '/quit':
                break
            if client.connected:
                client.send_message(MSG_TYPE_TEXT, msg.encode('utf-8'))
            else:
                logger.warning("Not connected. Cannot send.")
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        sys.exit(0)

from .ui import run_ui

def main():
    parser = argparse.ArgumentParser(description="GhostLink Bluetooth P2P Chat")
    parser.add_argument('mode', nargs='?', choices=['server', 'client', 'ui'], default='ui', help="Run mode: server/client (CLI) or ui (Graphic)")
    parser.add_argument('--address', help="Target Bluetooth MAC Address (for client CLI)", default=None)
    
    args = parser.parse_args()
    
    if args.mode == 'server':
        run_server()
    elif args.mode == 'client':
        run_client(args.address)
    else:
        # For UI, we need qasync ideally, or run asyncio in a separate thread.
        # Our current UI implementation uses QThread -> Worker -> sync methods.
        # We need to update UI to run an event loop or use qasync.
        # But for now, let's keep run_ui() which will handle the loop internally in the worker.
        run_ui()

if __name__ == "__main__":
    main()
