import os
import fcntl
import sys
import subprocess
import pathlib
import socket
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageChops
import PIL.ImageOps
from time import sleep
import struct


printerMACAddress = '25:00:04:00:77:6A'
printerWidth = 384
port = 2

# 스크립트가 위치한 디렉토리 기준으로 플래그 파일과 락 파일 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FLAG_FILE = os.path.join(SCRIPT_DIR, ".bluez_deprecated_installed")
LOCK_FILE = os.path.join(SCRIPT_DIR, ".cat_printer.lock")

# 단일 인스턴스 확인
def acquire_lock():
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except IOError:
        print("Another instance of cat-printer.py is already running.")
        sys.exit(1)

# 최초 1회 설치
def install_bluez_deprecated_tools():
    if not os.path.exists(FLAG_FILE):
        print("Installing bluez-deprecated-tools...")
        try:
            subprocess.run(["paru", "-S", "bluez-deprecated-tools"], check=True)
            pathlib.Path(FLAG_FILE).touch()
            print("bluez-deprecated-tools installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install bluez-deprecated-tools: {e}")

# 블루투스 설정
def setup_bluetooth():
    print("Setting up Bluetooth...")
    try:
        # 이미 페어링된 디바이스 확인
        result = subprocess.run(["bluetoothctl", "paired-devices"], capture_output=True, text=True)
        if printerMACAddress not in result.stdout:
            bluetoothctl_commands = f"""
            pair {printerMACAddress}
            trust {printerMACAddress}
            exit
            """
            subprocess.run(["bluetoothctl"], input=bluetoothctl_commands, text=True, check=True)
        
        # rfcomm 바인딩 확인 및 실행
        if not os.path.exists("/dev/rfcomm2"):
            subprocess.run(["sudo", "rfcomm", "bind", "2", printerMACAddress], check=True)
        print("Bluetooth setup completed.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to setup Bluetooth: {e}")

def initilizePrinter(soc):
    soc.send(b"\x1b\x40")
    
def getPrinterStatus(soc):
    soc.send(b"\x1e\x47\x03")
    return soc.recv(38) 
    
def getPrinterSerialNumber(soc):
    soc.send(b"\x1D\x67\x39")
    return soc.recv(21)
    
def getPrinterProductInfo(soc):
    soc.send(b"\x1d\x67\x69")
    return soc.recv(16)
    
def sendStartPrintSequence(soc):
    soc.send(b"\x1d\x49\xf0\x19")   
  
def sendEndPrintSequence(soc):
    soc.send(b"\x0a\x0a\x0a\x0a")
    
    
def trimImage(im):
    bg = PIL.Image.new(im.mode, im.size, (255,255,255))
    diff = PIL.ImageChops.difference(im, bg)
    diff = PIL.ImageChops.add(diff, diff, 2.0)
    bbox = diff.getbbox()
    if bbox:
        return im.crop((bbox[0],bbox[1],bbox[2],bbox[3]+10)) # don't cut off the end of the image

def create_text(text, font_name="Lucon.ttf", font_size=12):
    img = PIL.Image.new('RGB', (printerWidth, 5000), color = (255, 255, 255))
    font = PIL.ImageFont.truetype(font_name, font_size)
    
    d = PIL.ImageDraw.Draw(img)
    lines = []
    for line in text.splitlines():
        lines.append(get_wrapped_text(line, font, printerWidth))
    lines = "\n".join(lines)
    d.text((0,0), lines, fill=(0,0,0), font=font)
    return trimImage(img)

def get_wrapped_text(text: str, font: PIL.ImageFont.ImageFont,
                     line_length: int):
    lines = ['']
    for word in text.split():
        line = f'{lines[-1]} {word}'.strip()
        if font.getlength(line) <= line_length:
            lines[-1] = line
        else:
            lines.append(word)
    return '\n'.join(lines)


def printImage(soc, im):
    if im.width > printerWidth:
        # image is wider than printer resolution; scale it down proportionately
        height = int(im.height * (printerWidth / im.width))
        im = im.resize((printerWidth, height))
        
    if im.width < printerWidth:
        # image is narrower than printer resolution; pad it out with white pixels
        padded_image = PIL.Image.new("1", (printerWidth, im.height), 1)
        padded_image.paste(im)
        im = padded_image
        
    
    im = im.rotate(180) #print it so it looks right when spewing out of the mouth
    
    # if image is not 1-bit, convert it
    if im.mode != '1':
        im = im.convert('1')
        
        
    # if image width is not a multiple of 8 pixels, fix that
    if im.size[0] % 8:
        im2 = Image.new('1', (im.size[0] + 8 - im.size[0] % 8, 
                        im.size[1]), 'white')
        im2.paste(im, (0, 0))
        im = im2
        
        
        
    # Invert image, via greyscale for compatibility
    #  (no, I don't know why I need to do this)
    im = PIL.ImageOps.invert(im.convert('L'))
    # ... and now convert back to single bit
    im = im.convert('1')

    buf = b''.join((bytearray(b'\x1d\x76\x30\x00'), 
                                          struct.pack('2B', int(im.size[0] / 8 % 256), 
                                                      int(im.size[0] / 8 / 256)), 
                                                      struct.pack('2B', int(im.size[1] % 256), 
                                                                  int(im.size[1] / 256)), 
                                                                  im.tobytes()))
    initilizePrinter(soc)  
    sleep(.5)    
    sendStartPrintSequence(soc)
    sleep(.5)
    soc.send(buf)
    sleep(.5)
    sendEndPrintSequence(soc)
    sleep(.5)

def main():
    # 락 획득
    lock_fd = acquire_lock()
    
    # 최초 1회 설치
    install_bluez_deprecated_tools()
    
    # 블루투스 설정
    setup_bluetooth()

    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    s.connect((printerMACAddress,port))

    print("Connecting to printer...")
    getPrinterStatus(s)
    sleep(0.5)
    getPrinterSerialNumber(s)
    sleep(0.5)
    getPrinterProductInfo(s)
    sleep(0.5)

    #Read Image File
    # img = PIL.Image.open("IMG_5737.png")

    # Create image from text
    text = "Line 1\nLine 2\nLine 3"
    img = create_text(text,font_size=65)


    printImage(s,img)
    s.close()

    # 락 해제
    lock_fd.close()

if __name__ == "__main__":
    main()

