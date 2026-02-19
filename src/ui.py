import sys
import os
import threading
import datetime
import platform
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLineEdit, QPushButton, QLabel, QStackedWidget,
    QFileDialog, QListWidget, QListWidgetItem, QMessageBox, QFrame,
    QSplitter, QSizePolicy, QStyle
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QObject, QMimeData, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QImage, QIcon, QAction, QPalette, QColor, QFont, QDragEnterEvent, QDropEvent, QKeySequence

from .config import (
    APP_UUID, DEFAULT_SECRET_KEY, MSG_TYPE_TEXT, MSG_TYPE_IMAGE, 
    MSG_TYPE_SYSTEM, PC_NAME
)
# We can't use config's logger exactly because we want potential GUI logs?
# But for now use standard logger
from .logger import setup_logger
from .bluetooth_server import BluetoothServer
from .bluetooth_client import BluetoothClient
from .image_handler import load_image_bytes, compress_image, validate_image_file

logger = setup_logger("ui")

# --- Bluetooth Helpers ---
def get_local_bt_mac():
    """Get local Bluetooth adapter MAC address. Tries multiple methods for Win10/11 compatibility."""
    
    # Method 1: Get-NetAdapter (works well on Win11)
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "Get-NetAdapter | Where-Object {$_.InterfaceDescription -like '*Bluetooth*'} | Select-Object -ExpandProperty MacAddress"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        mac = result.stdout.strip().split('\n')[0].strip()
        if mac and len(mac) >= 12 and mac != '':
            return mac.replace('-', ':')
    except Exception:
        pass
    
    # Method 2: Read from Windows Registry (works on Win10/11)
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             r"Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\' -Name 'LocalAddr' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalAddr"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        raw = result.stdout.strip()
        if raw:
            # Registry returns space-separated bytes like "0 17 34 51 68 85" or similar
            parts = raw.split()
            if len(parts) >= 6:
                mac = ':'.join(f'{int(b):02X}' for b in parts[:6])
                return mac
    except Exception:
        pass
    
    # Method 3: PnP Device ID parsing (broad compatibility)
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Where-Object {$_.FriendlyName -like '*Radio*' -or $_.FriendlyName -like '*Adapter*' -or $_.FriendlyName -like '*Bluetooth*'} | Select-Object -First 1 -ExpandProperty InstanceId"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        instance_id = result.stdout.strip()
        if instance_id and '_' in instance_id:
            # InstanceId format: BTHENUM\{...}_VID&..._AABBCCDDEEFF
            # or USB\VID_...\5&AABBCCDDEEFF
            # Extract last 12 hex chars
            import re
            hex_match = re.findall(r'([0-9A-Fa-f]{12})', instance_id)
            if hex_match:
                raw = hex_match[-1]
                mac = ':'.join(raw[i:i+2].upper() for i in range(0, 12, 2))
                return mac
    except Exception:
        pass
    
    logger.warning("Could not detect local BT MAC with any method.")
    return "NOT_DETECTED"


def get_paired_devices():
    """Get list of paired Bluetooth devices from Windows registry.
    Returns list of (name, mac) tuples."""
    devices = []
    try:
        # Get paired device MACs from registry
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             r"Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices' -ErrorAction SilentlyContinue | ForEach-Object { $mac = $_.PSChildName; $name = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).'FriendlyName'; if ($name) { Write-Output \"$name||$mac\" } }"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if '||' in line:
                parts = line.split('||', 1)
                name = parts[0].strip()
                raw_mac = parts[1].strip()
                # Format MAC: 001122334455 -> 00:11:22:33:44:55
                if len(raw_mac) == 12:
                    mac = ':'.join(raw_mac[i:i+2] for i in range(0, 12, 2))
                else:
                    mac = raw_mac
                devices.append((name, mac))
    except Exception as e:
        logger.warning(f"Could not scan paired devices: {e}")
    return devices

# --- Styles ---
# Tactical Stealth Theme (GhostLink)
TACTICAL_STYLESHEET = """
QMainWindow {
    background-color: #0f1115; /* Deep tactical black */
}
QWidget {
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-size: 13px;
    color: #cfd8dc;
}
QFrame {
    border: none;
}
/* Header Area */
QFrame#headerFrame {
    background-color: #14171b;
    border-bottom: 2px solid #263238;
}
/* Lists and Inputs */
QListWidget {
    background-color: transparent;
    border: 1px solid #263238;
    border-radius: 0px;
    outline: none;
    /* Wallpaper settings - assuming image is in CWD or bundled */
    /* PyInstaller can't inject css variables easily for paths, so we might need inline style or assumption */
    /* Wait, standard css url() looks in CWD. If bundled, we need absolute path. */
    /* Solution: Dynamic setStyleSheet in init_ui with resource_path */
    border-image: none; 
    background-attachment: fixed;
}
QTextEdit {
    background-color: #0f1115;
    border: 1px solid #263238;
    border-radius: 0px;
    outline: none;
}
QLineEdit {
    background-color: #14171b;
    border: 1px solid #263238;
    border-left: 3px solid #ffb300; /* Amber Tactical Indicator */
    padding: 8px;
    color: #eceff1;
    border-radius: 0px;
    selection-background-color: #ffb300;
    selection-color: #000;
}
QLineEdit:focus {
    border: 1px solid #455a64;
    border-left: 3px solid #ffb300;
}
/* Buttons */
QPushButton {
    background-color: #1a1f24;
    color: #90a4ae;
    border: 1px solid #37474f;
    padding: 8px 16px;
    border-radius: 0px; /* Sharp corners */
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QPushButton:hover {
    background-color: #263238;
    border: 1px solid #ffb300; /* Amber glow */
    color: #ffb300;
}
QPushButton:pressed {
    background-color: #ffb300;
    color: #000000;
    border: 1px solid #ffb300;
}
QPushButton:disabled {
    background-color: #0f1115;
    border: 1px solid #263238;
    color: #455a64;
}
QPushButton#disconnectBtn {
    border: 1px solid #c62828;
    color: #ef5350;
}
QPushButton#disconnectBtn:hover {
    background-color: #c62828;
    color: #000;
}
/* Scrollbar */
QScrollBar:vertical {
    border: none;
    background: #0f1115;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #37474f;
    min-height: 20px;
}
/* Status Label */
QLabel#statusLabel {
    font-family: 'Consolas', monospace;
    font-weight: bold;
    color: #546e7a;
    padding-left: 5px;
}
"""

class BluetoothWorker(QObject):
    """
    Worker class to run Bluetooth logic in a separate thread.
    Bridges backend callbacks to Qt Signals.
    """
    msg_received = Signal(int, bytes) # type, payload
    status_changed = Signal(str, object) # status, extra_info
    
    def __init__(self, mode, target_address=None):
        super().__init__()
        self.mode = mode
        self.target_address = target_address
        self.bt_instance = None
        self._thread = None # Thread reference if needed

    def run(self):
        if self.mode == 'server':
            self.bt_instance = BluetoothServer()
        else:
            self.bt_instance = BluetoothClient(self.target_address)
            
        # Hook up callbacks
        self.bt_instance.on_message_received = self._on_msg
        self.bt_instance.on_status_changed = self._on_status
        
        # Start blocking loop
        # Note: BluetoothServer.start() loops forever until stopped
        # BluetoothClient.start() loops forever trying to connect/reconnect
        try:
            self.bt_instance.start(DEFAULT_SECRET_KEY)
        except Exception as e:
            logger.error(f"Worker crashed: {e}")
            self.status_changed.emit("Error", str(e))
            
    def _on_msg(self, msg_type, payload):
        self.msg_received.emit(msg_type, payload)
        
    def _on_status(self, status, info):
        self.status_changed.emit(status, info)

    def stop(self):
        if self.bt_instance:
            self.bt_instance.stop()


class ChatWindow(QMainWindow):
    signal_send_msg = Signal(int, bytes) # Signal to request sending a message

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        if hasattr(sys, '_MEIPASS'):
            # When frozen, files are in root of MEIPASS (because of --add-data 'src;dest') wait, let's check
            # --add-data "assets\ghostbt.ico;assets" -> It will be in MEIPASS/assets/ghostbt.ico
            return os.path.join(sys._MEIPASS, "assets", relative_path)
        
        return os.path.join(os.path.abspath("."), "assets", relative_path)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GHOSTLINK // SECURE_COMM_TERMINAL")
        self.resize(900, 700)
        self.setStyleSheet(TACTICAL_STYLESHEET)
        
        # Backend State
        self.thread = None
        self.worker = None
        self.bt_instance = None # Access via worker if needed, but risky. Better via signals.
        self.is_connected = False
        
        # Custom Icon - Check if exists (Use resource path for bundle)
        icon_path = self.resource_path("ghostbt.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            # Set App Icon for Taskbar (Windows requires explicit AppUserModelID)
            try:
                import ctypes
                myappid = 'jaime.moreno.ghostlink.bt.v1' # arbitrary string
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except:
                pass

        self.init_ui()
    
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Header / Toolbar ---
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        # header_frame.setStyleSheet("background-color: #2d2d30; border-bottom: 1px solid #3e3e42;") # Moved to CSS
        header_layout = QHBoxLayout(header_frame)
        
        self.lbl_status = QLabel("OFFLINE")
        self.lbl_status.setObjectName("statusLabel")
        header_layout.addWidget(QLabel("LINK_STATUS >"))
        header_layout.addWidget(self.lbl_status)
        
        header_layout.addStretch()
        
        self.btn_server = QPushButton("[ HOST_SESSION ]")
        self.btn_server.clicked.connect(self.start_server)
        
        self.btn_client = QPushButton("[ JOIN_SESSION ]")
        self.btn_client.clicked.connect(self.start_client_dialog)
        
        self.btn_disconnect = QPushButton("[ ABORT ]")
        self.btn_disconnect.setObjectName("disconnectBtn")
        self.btn_disconnect.clicked.connect(self.disconnect_bt)
        self.btn_disconnect.setVisible(False)

        header_layout.addWidget(self.btn_server)
        header_layout.addWidget(self.btn_client)
        header_layout.addWidget(self.btn_disconnect)

        main_layout.addWidget(header_frame)
        
        # --- MAC Info ---
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #0f1115; font-size: 11px; color: #546e7a; border-bottom: 1px solid #1a1f24;")
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(10, 2, 10, 2)
        
        # Detect local BT MAC
        self.local_mac = get_local_bt_mac()
        mac_label = QLabel(f"DEVICE: {PC_NAME.upper()}  |  MAC: {self.local_mac}")
        mac_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        mac_label.setCursor(Qt.IBeamCursor)
        info_layout.addWidget(mac_label)
        info_layout.addStretch()
        
        self.btn_scan = QPushButton("[ SCAN_DEVICES ]")
        self.btn_scan.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        self.btn_scan.clicked.connect(self.scan_devices)
        info_layout.addWidget(self.btn_scan)
        
        main_layout.addWidget(info_frame)

        # --- Chat Area ---
        self.chat_list = QListWidget()
        self.chat_list.setIconSize(self.chat_list.size()) # For images? No.
        self.chat_list.setSelectionMode(QListWidget.NoSelection)
        self.chat_list.setFocusPolicy(Qt.NoFocus) # Keep focus on input
        
        # Dynamic Stylesheet for Wallpaper Path
        wp_path = self.resource_path("ghost_wallpaper.png")
        # Replace backslashes for CSS
        wp_path = wp_path.replace("\\", "/")
        self.chat_list.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                border: 1px solid #263238;
                border-image: url({wp_path}) 0 0 0 0 stretch stretch;
                background-attachment: fixed;
            }}
        """)
        
        main_layout.addWidget(self.chat_list)
        
        # --- Input Area ---
        input_frame = QFrame()
        # input_frame.setStyleSheet("background-color: #2d2d30; border-top: 1px solid #3e3e42;")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 10, 10, 10)
        
        self.btn_attach = QPushButton("+")
        self.btn_attach.setFixedSize(30, 30)
        self.btn_attach.clicked.connect(self.select_image)
        
        self.input_field = InputLineEdit()
        self.input_field.setPlaceholderText("ENTER MESSAGE... [CTRL+V FOR IMG]")
        self.input_field.returnPressed.connect(self.send_text_msg)
        self.input_field.paste_image.connect(self.send_image_bytes) # Use custom signal
        
        self.btn_send = QPushButton("SEND")
        self.btn_send.clicked.connect(self.send_text_msg)
        
        input_layout.addWidget(self.btn_attach)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.btn_send)
        
        main_layout.addWidget(input_frame)
        
        # --- Footer ---
        footer_lbl = QLabel("@jaimemorenoo1 || CODE: GHOST_PROTOCOL_V1 || jaicarmods@gmail.com || Stellaris Code")
        footer_lbl.setAlignment(Qt.AlignCenter)
        footer_lbl.setStyleSheet("color: #37474f; font-size: 10px; font-family: 'Consolas'; margin-top: 5px; margin-bottom: 2px;")
        main_layout.addWidget(footer_lbl)
        
        # --- Drag & Drop ---
        self.setAcceptDrops(True)

    # --- Scan Logic ---
    def scan_devices(self):
        """Scan and display paired Bluetooth devices."""
        self.add_system_message("SCANNING BT DEVICES...")
        devices = get_paired_devices()
        
        if not devices:
            self.add_system_message("NO PAIRED DEVICES FOUND. Pair devices in Windows Bluetooth Settings first.")
            return
        
        self.add_system_message(f"FOUND {len(devices)} PAIRED DEVICE(S):")
        for name, mac in devices:
            self.add_system_message(f"  > {name}  [{mac}]")

    # --- Start Logic ---
    def start_server(self):
        self._start_bt('server')
        
    def start_client_dialog(self):
        """Show device picker or manual MAC input."""
        devices = get_paired_devices()
        
        if devices:
            # Build selection list
            from PySide6.QtWidgets import QDialog, QDialogButtonBox
            
            dialog = QDialog(self)
            dialog.setWindowTitle("SELECT_TARGET")
            dialog.setStyleSheet(self.styleSheet())
            dialog.resize(450, 350)
            
            dlg_layout = QVBoxLayout(dialog)
            
            dlg_layout.addWidget(QLabel("DETECTED PAIRED DEVICES:"))
            
            device_list = QListWidget()
            device_list.setStyleSheet("QListWidget { background-color: #14171b; border: 1px solid #263238; }")
            for name, mac in devices:
                item = QListWidgetItem(f"{name}  [{mac}]")
                item.setData(Qt.UserRole, mac)
                device_list.addItem(item)
            dlg_layout.addWidget(device_list)
            
            dlg_layout.addWidget(QLabel("— OR ENTER MAC MANUALLY —"))
            manual_input = QLineEdit()
            manual_input.setPlaceholderText("00:11:22:33:44:55")
            dlg_layout.addWidget(manual_input)
            
            btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btn_box.accepted.connect(dialog.accept)
            btn_box.rejected.connect(dialog.reject)
            dlg_layout.addWidget(btn_box)
            
            if dialog.exec() == QDialog.Accepted:
                # Priority: selected device > manual input
                selected = device_list.currentItem()
                if selected:
                    mac = selected.data(Qt.UserRole)
                else:
                    mac = manual_input.text().strip()
                
                if mac:
                    self._start_bt('client', mac)
        else:
            # Fallback: simple manual input
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(self, 'TARGET_MAC', 'No paired devices found.\nEnter Host MAC Address (e.g. 00:11:22:33:44:55):')
            if ok and text:
                self._start_bt('client', text)

    def _start_bt(self, mode, target_address=None):
        self.btn_server.setEnabled(False)
        self.btn_client.setEnabled(False)
        self.btn_disconnect.setVisible(True)
        self.chat_list.clear() # Clear chat on new session?
        
        self.thread = QThread()
        self.worker = BluetoothWorker(mode, target_address)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.status_changed.connect(self.update_status)
        self.worker.msg_received.connect(self.handle_incoming_message)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()
        self.add_system_message(f"Starting {mode}...")

    def disconnect_bt(self):
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait() # Wait for loop to finish
            
        self.thread = None
        self.worker = None
        self.is_connected = False
        
        self.btn_server.setEnabled(True)
        self.btn_client.setEnabled(True)
        self.btn_disconnect.setVisible(False)
        self.btn_disconnect.setVisible(False)
        self.lbl_status.setText("OFFLINE")
        self.lbl_status.setStyleSheet("color: #546e7a;")
        self.add_system_message("UPLINK_TERMINATED")

    @Slot(str, object)
    def update_status(self, status, info):
        if status == "Connected":
            self.is_connected = True
            msg = f"LINK_ESTABLISHED :: TARGET [{info}]"
            self.lbl_status.setText("SECURE_LINK_ACTIVE")
            self.lbl_status.setStyleSheet("color: #ffb300;") # Amber
            self.add_system_message(msg)
        elif status == "Disconnected":
            self.is_connected = False
            self.lbl_status.setText("SEARCHING...")
            self.lbl_status.setStyleSheet("color: #ef5350;")
            self.add_system_message("LINK_LOST // RECONNECTING")
        elif status == "Scanning":
             self.lbl_status.setText("SCANNING_FREQ...")
        elif status == "Listening":
             self.lbl_status.setText(f"Waiting on Port {info}...")
        elif status == "Stopped":
             pass # Handled in disconnect_bt usually

    # --- Messaging Logic ---
    def send_text_msg(self):
        text = self.input_field.text().strip()
        if not text:
            return
            
        if not self.is_connected:
            self.add_system_message("Not connected.")
            return

        # Send via Worker logic? 
        # The worker owns the instance. We can access it directly knowing threads...
        # The bt_instance.send_message is thread-safe (uses Lock).
        # So we can call it from main thread safely.
        
        try:
            if self.worker and self.worker.bt_instance:
                self.worker.bt_instance.send_message(MSG_TYPE_TEXT, text.encode('utf-8'))
                self.add_chat_bubble(text, is_own=True, msg_type=MSG_TYPE_TEXT)
                self.input_field.clear()
        except Exception as e:
            logger.error(f"Send error: {e}")
            self.add_system_message(f"Error sending: {e}")

    @Slot(bytes)
    def send_image_bytes(self, image_data):
        if not self.is_connected:
            self.add_system_message("Not connected.")
            return
            
        # Compress/Validate
        compressed = compress_image(image_data)
        if not compressed:
            self.add_system_message("Failed to process image.")
            return
            
        try:
            if self.worker and self.worker.bt_instance:
                self.worker.bt_instance.send_message(MSG_TYPE_IMAGE, compressed)
                self.add_chat_bubble(compressed, is_own=True, msg_type=MSG_TYPE_IMAGE)
        except Exception as e:
            logger.error(f"Send error: {e}")
            self.add_system_message(f"Error sending image: {e}")

    def select_image(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select Image', '', "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if fname:
            data = load_image_bytes(fname)
            if data:
                self.send_image_bytes(data)

    @Slot(int, bytes)
    def handle_incoming_message(self, msg_type, payload):
        self.add_chat_bubble(payload, is_own=False, msg_type=msg_type)

    # --- UI Rendering ---
    def add_chat_bubble(self, content, is_own, msg_type):
        timestamp = datetime.datetime.now().strftime("%H:%M")
        
        item_widget = QWidget()
        layout = QVBoxLayout(item_widget)
        
        # Alignment
        alignment = Qt.AlignRight if is_own else Qt.AlignLeft
        
        # Tactical Colors
        # Own: Dark Blueish tint, Remote: Dark Grey/Black
        bg_color = "#1a242f" if is_own else "#131519" 
        border_color = "#ffb300" if is_own else "#37474f" 
        text_color = "#eceff1" if is_own else "#b0bec5"
        
        bubble_frame = QFrame()
        bubble_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid #1a1f24;
                border-left: 2px solid {border_color};
                padding: 10px;
            }}
        """)
        bubble_layout = QVBoxLayout(bubble_frame)
        
        # Content
        if msg_type == MSG_TYPE_TEXT:
            try:
                text = content.decode('utf-8') if isinstance(content, bytes) else content
            except: 
                text = "<Binary Data>"
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            lbl.setCursor(Qt.IBeamCursor)
            lbl.setStyleSheet(f"color: {text_color};")
            bubble_layout.addWidget(lbl)
        elif msg_type == MSG_TYPE_IMAGE:
             # Render Image
             pixmap = QPixmap()
             pixmap.loadFromData(content)
             
             # Scale strictly for display if huge
             if pixmap.width() > 400:
                 pixmap = pixmap.scaledToWidth(400, Qt.SmoothTransformation)
             
             img_lbl = QLabel()
             img_lbl.setPixmap(pixmap)
             bubble_layout.addWidget(img_lbl)
        
        # Time
        time_lbl = QLabel(timestamp)
        time_lbl.setStyleSheet("color: #ccc; font-size: 10px;")
        time_lbl.setAlignment(Qt.AlignRight)
        bubble_layout.addWidget(time_lbl)
        
        layout.addWidget(bubble_frame)
        layout.setAlignment(alignment)
        
        # Add to list
        item = QListWidgetItem(self.chat_list)
        item.setSizeHint(item_widget.sizeHint())
        self.chat_list.addItem(item)
        self.chat_list.setItemWidget(item, item_widget)
        self.chat_list.scrollToBottom()

    def add_system_message(self, text):
        item_widget = QWidget()
        layout = QHBoxLayout(item_widget)
        layout.setContentsMargins(20, 2, 20, 2)
        
        lbl = QLabel(f">> SYSTEM: {text}")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #546e7a; font-family: 'Consolas'; font-size: 10px;")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        lbl.setCursor(Qt.IBeamCursor)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        
        item = QListWidgetItem(self.chat_list)
        item.setSizeHint(item_widget.sizeHint())
        self.chat_list.addItem(item)
        self.chat_list.setItemWidget(item, item_widget)
        self.chat_list.scrollToBottom()

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    data = load_image_bytes(path)
                    if data:
                        self.send_image_bytes(data)
        elif mime.hasImage():
            # QImage from clipboard/drop
            qimg = mime.imageData() # returns QImage
            # Convert to bytes
            ba = QByteArray()
            buff = QBuffer(ba)
            buff.open(QIODevice.WriteOnly)
            qimg.save(buff, "PNG")
            self.send_image_bytes(ba.data())

    def closeEvent(self, event):
        self.disconnect_bt()
        event.accept()

# --- Custom Input for Clipboard Image Paste ---
class InputLineEdit(QLineEdit):
    paste_image = Signal(bytes)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime.hasImage():
                qimg = mime.imageData()
                if qimg:
                    ba = QByteArray()
                    buff = QBuffer(ba)
                    buff.open(QIODevice.WriteOnly)
                    qimg.save(buff, "PNG")
                    self.paste_image.emit(ba.data())
                    return
            
        super().keyPressEvent(event)

def run_ui():
    app = QApplication(sys.argv)
    app.setApplicationName("GhostLink BT")
    
    window = ChatWindow()
    window.show()
    
    sys.exit(app.exec())
