from email.policy import default
import io
import picamera
import logging
import socketserver
from threading import Condition, Thread
from http import server
import RPi.GPIO as GPIO
import time
import codecs


Thread1:Thread = Thread()
Thread2:Thread = Thread()
StopTrigger:bool = False
Switch1 = 3
Switch2 = 5
Motor1 = 16
Motor2 = 18

GPIO.setmode(GPIO.BOARD)
GPIO.setup(Switch1, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(Switch2, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(Motor1, GPIO.OUT)
GPIO.setup(Motor2, GPIO.OUT)

GPIO.output(Motor1, GPIO.LOW)
GPIO.output(Motor2, GPIO.LOW)

PAGE=codecs.open("./index.html", "r").read()

server_socket = default
client_socket = default

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    IsClosing = False
    def do_GET(self):
        global IsClosing
        IsClosing = False
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif '/index.html' in self.path:
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            if 'sequence=true' in self.path:
                SequenceProcessing()
            elif 'continuous-left=true' in self.path:
                MoveLeftContinuous()
            elif 'continuous-right=true' in self.path:
                MoveRightContinuous()
            elif 'left=true' in self.path:
                MoveLeft()
            elif 'right=true' in self.path:
                MoveRight()
            elif 'stop=true' in self.path:
                Stop()

        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while not IsClosing:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()
            
    def finish(self,*args,**kw):
        try:
            global IsClosing
            IsClosing = True
            if not self.wfile.closed:
                self.wfile.flush()
                self.wfile.close()
        except:
            pass
        self.rfile.close()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def MoveLeft():
    global Thread1
    global Thread2
    global StopTrigger
    if((not Thread1.is_alive()) and (not Thread2.is_alive())):
        print("Move Left")
        Thread1 = Thread(target=MoveMotorLeft)
        Thread1.start()

def MoveRight():
    global Thread1
    global Thread2
    if((not Thread1.is_alive()) and (not Thread2.is_alive())):
        print("Move Right")
        Thread1 = Thread(target=MoveMotorRight)
        Thread1.start()

def MoveLeftContinuous():
    global Thread1
    global Thread2
    if((not Thread1.is_alive()) and (not Thread2.is_alive())):
        print("Move Right Continuous")
        Thread1 = Thread(target=MoveMotorLeftContinuous)
        Thread1.start()

def MoveRightContinuous():
    global Thread1
    global Thread2
    if((not Thread1.is_alive()) and (not Thread2.is_alive())):
        print("Move Right Continuous")
        Thread1 = Thread(target=MoveMotorRightContinuous)
        Thread1.start()
        
def Stop():
    global StopTrigger
    StopTrigger = True

def MoveMotorLeftContinuous():
    global StopTrigger
    StopTrigger = False
    while not StopTrigger:
        MoveMotorLeft()
        time.sleep(0.5)
        
def MoveMotorRightContinuous():
    global StopTrigger
    StopTrigger = False
    while not StopTrigger:
        MoveMotorRight()
        time.sleep(0.5)

def MoveMotorRight():
    print("우측로 1회 이동")
    
def MoveMotorLeft():
    print("좌측으로 1회 이동")

def SequenceProcessing():
    global Thread1
    global Thread2
    print("Start Sequence!!")
    if((not Thread1.is_alive())):
        Thread1 = Thread(target=SequenceA)
        Thread1.start()
    if((not Thread2.is_alive())):
        Thread2 = Thread(target=SequenceB)
        Thread2.start()
    
def SequenceA():
    print("Move Motor1")
    time.sleep(1)
    print("Switch1 Enabled")
    time.sleep(5)
    print("Stop Motor1")
    # Sequence Code Here
    #GPIO.output(Motor1, GPIO.HIGH)
    #while True:
    #    pass
    #GPIO.output(Motor1, GPIO.LOW)
    
def SequenceB():
    print("Move Motor2")
    time.sleep(2)
    print("Switch2 Enabled")
    time.sleep(2)
    print("Stop Motor2")
    # Sequence Code Here
    #GPIO.output(Motor2, GPIO.HIGH)
    #while GPIO.input(Switch2) == GPIO.LOW:
    #    pass
    #GPIO.output(Motor2, GPIO.LOW)
with picamera.PiCamera(resolution='640x480', framerate=24) as camera:
   output = StreamingOutput()
   camera.start_recording(output, format='mjpeg')
   try:
       address = ('192.168.35.44', 4000)
       server = StreamingServer(address, StreamingHandler)
       server.serve_forever()
   finally:
       camera.stop_recording()
