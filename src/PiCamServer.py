from email.policy import default
import io
import picamera
import logging
import socketserver
from threading import Condition, Thread
from http import server
import RPi.GPIO as GPIO
import time

Thread1:Thread = Thread()
Thread2:Thread = Thread()
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

PAGE="""\
    <html>
        <head>
        <title>Camera Test Module</title>
        </head>

        <body>
        <h1>Camera Test Module</h1>
        <img src="stream.mjpg" width="640" height="480"/>
        <br/>
        <form action="">
            <input type="hidden" name="StartSequence" id="StartSequence" value="true">
            <input type="submit" value="Start Sequence">
        </form>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/1.3.8/FileSaver.js"></script>
        <script type="text/javascript">
            function ChangeSequenceStatus() {
                var SequenceButton = document.getElementById("SequenceButton");
                var SequenceStatus = document.getElementById("SequenceStatus");
                if(SequenceStatus.value == 'false'){
                    SequenceStatus.value = 'true';
                }
                else{
                    SequenceStatus.value = 'false';
                }
                //var blob = new Blob([SequenceStatus.value],{type: "text/plain;charset=utf-8"});
                //saveAs(blob, "SequenceStatus.txt");
                SequenceButton.innerText= SequenceStatus.value == 'true' ? "Sequence Processing..." : "Start Sequence"; 
            }
            function ChangeStreamingStatus() {
                var StreamingButton = document.getElementById("StreamingButton");
                var StreamingStatus = document.getElementById("StreamingStatus");
                if(StreamingStatus.value == 'false'){
                    StreamingStatus.value = 'true';
                }
                else{
                    StreamingStatus.value = 'false';
                }
                StreamingButton.innerText= StreamingStatus.value == 'true' ? "스트리밍 중지" : "스트리밍 시작";
            }
        </script>
        <!-- <button id="SequenceButton" style="width:300;"  type="button" onclick="ChangeSequenceStatus()">
            Start Sequence
        </button> -->
    </html>
"""
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
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/index.html?StartSequence=true':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            SequenceProcessing()
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
        address = ('192.168.0.118', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()