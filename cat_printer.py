import os
import fcntl
import sys
import subprocess
import pathlib
import socket
from battery_util import nonlinear_voltage_to_percent
import re
from time import sleep, time
import struct

from image_processor import create_text, process_image_for_printing

# 스크립트가 위치한 디렉토리 기준으로 플래그 파일과 락 파일 경로 설정
class CatPrinter:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    FLAG_FILE = os.path.join(SCRIPT_DIR, ".bluez_deprecated_installed")
    LOCK_FILE = os.path.join(SCRIPT_DIR, ".cat_printer.lock")
    PRINTER_WIDTH = 384

    def __init__(self):
        self.soc = None
        self.lock_fd = None
        self._mac_address = None
        self._port = None

    def _acquire_lock(self):
        """단일 인스턴스 확인 (private)"""
        self.lock_fd = open(self.LOCK_FILE, 'w')
        try:
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except IOError:
            print("Another instance of cat-printer.py is already running.")
            sys.exit(1)

    def _install_bluez_deprecated_tools(self):
        """최초 1회 설치 (private)"""
        if not os.path.exists(self.FLAG_FILE):
            print("Installing bluez-deprecated-tools...")
            try:
                subprocess.run(["paru", "-S", "bluez-deprecated-tools"], check=True)
                pathlib.Path(self.FLAG_FILE).touch()
                print("bluez-deprecated-tools installed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to install bluez-deprecated-tools: {e}")

    def _setup_bluetooth(self):
        """블루투스 설정 (private)"""
        print("Setting up Bluetooth...")
        try:
            # 이미 페어링된 디바이스 확인
            result = subprocess.run(["bluetoothctl", "paired-devices"], capture_output=True, text=True)
            if self._mac_address not in result.stdout:
                bluetoothctl_commands = f"""
                pair {self._mac_address}
                trust {self._mac_address}
                exit
                """
                subprocess.run(["bluetoothctl"], input=bluetoothctl_commands, text=True, check=True)
            
            # rfcomm 바인딩 확인 및 실행
            if not os.path.exists("/dev/rfcomm2"):
                subprocess.run(["sudo", "rfcomm", "bind", "2", self._mac_address], check=True)
            print("Bluetooth setup completed.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to setup Bluetooth: {e}")

    def _initialize_printer(self):
        """Initialize connection to the printer (private)"""
        print("Connecting to printer...")
        self.soc = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.soc.connect((self._mac_address, self._port))
        self._get_printer_status()
        sleep(0.5)
        self._get_printer_serial_number()
        sleep(0.5)
        self._get_printer_product_info()
        sleep(0.5)

    def _initialize_printer_commands(self):
        """Send initialization command to printer (private)"""
        self.soc.send(b"\x1b\x40")

    def _get_printer_status(self):
        """Get printer status (private)"""
        self.soc.send(b"\x1e\x47\x03")
        return self.soc.recv(38)

    def _get_printer_voltage(self):
        """Get printer voltage (private)"""
        match = re.search(r'VOLT=(\d+)mv', self._get_printer_status().decode('utf-8'))
        if match:
            return int(match.group(1))
        return None

    def _get_printer_serial_number(self):
        """Get printer serial number (private)"""
        self.soc.send(b"\x1D\x67\x39")
        return self.soc.recv(21)

    def _get_printer_product_info(self):
        """Get printer product info (private)"""
        self.soc.send(b"\x1d\x67\x69")
        return self.soc.recv(16)

    def _send_start_print_sequence(self):
        """Send start print sequence (private)"""
        self.soc.send(b"\x1d\x49\xf0\x19")

    def _send_end_print_sequence(self):
        """Send end print sequence (private)"""
        self.soc.send(b"\x0a\x0a\x0a\x0a")

    def _send_image_data(self, im):
        """Send raw image data to printer (private)"""
        # Validate image dimensions and mode
        if im.width % 8 != 0:
            raise ValueError(f"Image width ({im.width}) must be a multiple of 8 for printing")
        if im.mode != '1':
            raise ValueError(f"Image mode ({im.mode}) must be '1' (1-bit) for printing")
        
        buf = b''.join((bytearray(b'\x1d\x76\x30\x00'), 
                                              struct.pack('2B', int(im.size[0] / 8 % 256), 
                                                          int(im.size[0] / 8 / 256)), 
                                                          struct.pack('2B', int(im.size[1] % 256), 
                                                                      int(im.size[1] / 256)), 
                                                                      im.tobytes()))
    
        # in debug mode, print the buf size in bytes and bits
        if os.getenv("DEBUG"):
            print(f"buf size: {len(buf)} bytes, {len(buf) * 8} bits")

        self._initialize_printer_commands()
        sleep(.5)
        self._send_start_print_sequence()
        sleep(.5)

        # split the buf into 25600 bytes chunks and send
        for i in range(0, len(buf), 25600):
            self.soc.send(buf[i:i+25600])
            sleep(.5)
        self._send_end_print_sequence()
        sleep(.5)

        # Update expected print time. It takes 31 seconds to print image of height 1120.
        # So, per-height print time is 31 / 1120 seconds.
        per_height_print_time = 31 / 1120
        expected_print_time = per_height_print_time * im.size[1]
        print(f"Expected print time: {expected_print_time} seconds")
        self._expected_print_finish_time = time() + expected_print_time

    def print_single_image(self, im):
        """Print a single image (public)"""
        processed_image = process_image_for_printing(im, self.PRINTER_WIDTH)
        self._send_image_data(processed_image)

    def wait_for_print_completion(self):
        """Wait for print completion (public)"""
        while time() < self._expected_print_finish_time:
            sleep(0.01)
        print("Print completed")
    
    def get_battery_percent(self):
        """Get battery percent (public)"""
        return nonlinear_voltage_to_percent(self._get_printer_voltage())

    def setup(self, mac_address='25:00:04:00:77:6A', port=2):
        """Setup the printer connection and configuration (public)"""
        self._mac_address = mac_address
        self._port = port
        self._acquire_lock()
        self._install_bluez_deprecated_tools()
        self._setup_bluetooth()
        self._initialize_printer()

    def close(self):
        """Close the printer connection and release lock (public)"""
        if self.soc:
            self.soc.close()
        if self.lock_fd:
            self.lock_fd.close()