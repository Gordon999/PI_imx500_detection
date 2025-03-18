#!/usr/bin/env python3

"""Based on imx500_object_detection_demo.py."""

"""Copyright (c) 2025
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

#v0.4

import argparse
import sys
from functools import lru_cache
import cv2
import numpy as np
import os
import time
import datetime
import glob
import shutil
from picamera2 import MappedArray, Picamera2, Preview
from picamera2.devices import IMX500
from picamera2.devices.imx500 import (NetworkIntrinsics,postprocess_nanodet_detection)
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput2, PyavOutput
from libcamera import controls
from gpiozero import LED

import pygame, sys
from pygame.locals import *
pygame.init()
windowSurfaceObj = pygame.display.set_mode((320,450),1, 24)
pygame.display.set_caption("Review Captures" ) 

# detection objects
objects      = ["cat","bear","clock","person"]
threshold    = 0.5   # set detection threshold   

# video settings
v_width      = 1456  # video width
v_height     = 1088  # video height
v_length     = 5     # seconds
show_detects = 0     # show detections on video
mp4_anno     = 1     # annotate date & time on mp4

# camera settings
mode     = 1     # camera mode, 0-3 = manual,normal,short,long
speed    = 1000  # manual shutter speed in mS
gain     = 0     # set camera gain, 0 = auto
led      = 21    # set gpio for recording led

# shutdown time
sd_hour  = 20    # hour
sd_mins  = 0     # minute
auto_sd  = 0     # set to 1 to shutdown at set time

# ram limit
ram_limit = 150  # stops recording if ram below this

# initialise
last_detections = []
label    = " ( "
Users    = []
Users.append(os.getlogin())
user     = Users[0]
h_user   = "/home/" + os.getlogin( )
m_user = "/media/" + os.getlogin( )
encoding = False
rec_led  = LED(led)
rec_led.off()
mp4_timer = 10

# mp4_annotation parameters
colour    = (255, 255, 255)
origin    = (184, int(v_height - 35))
font      = cv2.FONT_HERSHEY_SIMPLEX
scale     = 1
thickness = 2

config_file = "Det_Config02.txt"

# check Det_configXX.txt exists, if not then write default values
if not os.path.exists(config_file):
    defaults = [mode,speed,gain]
    with open(config_file, 'w') as f:
        for item in defaults:
            f.write("%s\n" % item)

# read config file
defaults = []
with open(config_file, "r") as file:
   line = file.readline()
   while line:
      defaults.append(line.strip())
      line = file.readline()
defaults = list(map(int,defaults))
mode  = defaults[0]
speed = defaults[1]
gain  = defaults[2]

def text(msg,cr,cg,cb,x,y,ft,bw):
    pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(x,y,bw,20))
    if os.path.exists ('/usr/share/fonts/truetype/freefont/FreeSerif.ttf'):
        fontObj = pygame.font.Font('/usr/share/fonts/truetype/freefont/FreeSerif.ttf',ft)
    else:
        fontObj = pygame.font.Font(None,ft)
    msgSurfaceObj = fontObj.render(msg, False, (cr,cg,cb))
    msgRectobj = msgSurfaceObj.get_rect()
    msgRectobj.topleft = (x,y)
    windowSurfaceObj.blit(msgSurfaceObj, msgRectobj)
    pygame.display.update()

start_up = time.monotonic()
startmp4 = time.monotonic()
p = 0
modes = ['manual','normal','short','long']
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(1,1,80,50),1)
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(80,1,80,50),1)
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(160,1,80,50),1)
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(240,1,80,50),1)
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(1,400,80,50),1)
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(80,400,80,50),1)
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(240,400,80,50),1)
text("PREV",100,100,100,10,15,18,60)
pygame.draw.rect(windowSurfaceObj,(100,100,100),Rect(160,400,80,50),1)
text("NEXT",100,100,100,90,15,18,60)
text("MODE",100,100,100,90,402,18,60)
text(str(modes[mode]),100,100,100,95,420,18,60)
if mode == 0:
    text("SPEED",100,100,100,170,402,18,60)
    text(str(speed),100,100,100,170,420,18,60)
text("GAIN",100,100,100,250,402,18,60)
if gain != 0:
    text(str(gain),100,100,100,250,420,18,60)
else:
    text("Auto",100,100,100,250,420,18,60)
text("Please wait...",100,100,100,10,60,18,60)
#time.sleep(10)
text("",100,100,100,10,60,18,100)

# show last captured image
Pics = glob.glob(h_user + '/Pictures/*.jpg')
Pics.sort()
if len(Pics) > 0:
    p = len(Pics) - 1
    image = pygame.image.load(Pics[p])
    image = pygame.transform.scale(image,(320,320))
    windowSurfaceObj.blit(image,(0,51))
    text(str(p+1) + "/" + str(p+1),100,120,100,10,375,18,60)
    pic = Pics[p].split("/")
    pipc = h_user + '/Videos/' + pic[4][:-3] + "mp4"
    text(str(pic[4]),100,120,100,160,375,18,320)
    if os.path.exists(pipc):
        text("DELETE",100,100,100,163,15,18,60)
        text("DEL ALL",100,100,100,10,415,16,60)
        USB_Files  = []
        USB_Files  = (os.listdir(m_user))
        if len(USB_Files) > 0:
            text("  to USB",100,100,100,243,15,18,60)
    pygame.display.update()
pygame.display.update()

class Detection:
    def __init__(self, coords, category, conf, metadata):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        self.box = imx500.convert_inference_coords(coords, metadata, picam2)

def Camera_Version():
    global cam1
    if os.path.exists('/run/shm/libcams.txt'):
        os.rename('/run/shm/libcams.txt', '/run/shm/oldlibcams.txt')
    os.system("rpicam-vid --list-cameras >> /run/shm/libcams.txt")
    time.sleep(0.5)
    # read libcams.txt file
    camstxt = []
    with open("/run/shm/libcams.txt", "r") as file:
        line = file.readline()
        while line:
            camstxt.append(line.strip())
            line = file.readline()
    cam1 = camstxt[2][4:10]
    
def parse_detections(metadata: dict):
    """Parse the output tensor into a number of detected objects, scaled to the ISP output."""
    global last_detections
    bbox_normalization = intrinsics.bbox_normalization
    bbox_order = intrinsics.bbox_order
    threshold = args.threshold
    iou = args.iou
    max_detections = args.max_detections

    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    input_w, input_h = imx500.get_input_size()
    if np_outputs is None:
        return last_detections
    if intrinsics.postprocess == "nanodet":
        boxes, scores, classes = \
            postprocess_nanodet_detection(outputs=np_outputs[0], conf=threshold, iou_thres=iou,
                                          max_out_dets=max_detections)[0]
        from picamera2.devices.imx500.postprocess import scale_boxes
        boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False, False)
    else:
        boxes, scores, classes = np_outputs[0][0], np_outputs[1][0], np_outputs[2][0]
        if bbox_normalization:
            boxes = boxes / input_h

        if bbox_order == "xy":
            boxes = boxes[:, [1, 0, 3, 2]]
        boxes = np.array_split(boxes, 4, axis=1)
        boxes = zip(*boxes)

    last_detections = [
        Detection(box, category, score, metadata)
        for box, score, category in zip(boxes, scores, classes)
        if score > threshold
    ]
    return last_detections

@lru_cache
def get_labels():
    labels = intrinsics.labels

    if intrinsics.ignore_dash_labels:
        labels = [label for label in labels if label and label != "-"]
    return labels


def draw_detections(request, stream="main"):
    """Draw the detections for this request onto the ISP output."""
    global label,show_detects, mp4_anno
    detections = last_results
    if detections is None:
        return
    labels = get_labels()
    with MappedArray(request, stream) as m:
        for detection in detections:
            x, y, w, h = detection.box
            label = f"{labels[int(detection.category)]} ({detection.conf:.2f})"
            if show_detects == 1:
                # Calculate text size and position
                (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                text_x = x + 5
                text_y = y + 15

                # Create a copy of the array to draw the background with opacity
                overlay = m.array.copy()

                # Draw the background rectangle on the overlay
                cv2.rectangle(overlay,
                          (text_x, text_y - text_height),
                          (text_x + text_width, text_y + baseline),
                          (255, 255, 255),  # Background color (white)
                          cv2.FILLED)

                alpha = 0.30
                cv2.addWeighted(overlay, alpha, m.array, 1 - alpha, 0, m.array)

                # Draw text on top of the background
                cv2.putText(m.array, label, (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

                # Draw detection box
                cv2.rectangle(m.array, (x, y), (x + w, y + h), (0, 255, 0, 0), thickness=2)

        if intrinsics.preserve_aspect_ratio:
            b_x, b_y, b_w, b_h = imx500.get_roi_scaled(request)
            color = (255, 0, 0)  # red
            cv2.putText(m.array, "ROI", (b_x + 5, b_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            cv2.rectangle(m.array, (b_x, b_y), (b_x + b_w, b_y + b_h), (255, 0, 0, 0))
    # apply timestamp to video
    if mp4_anno == 1:
        timestamp = time.strftime("%Y/%m/%d %T")
        with MappedArray(request, "main") as m:
            lst = list(origin)
            lst[0] += 365
            lst[1] -= 20
            end_point = tuple(lst)
            cv2.rectangle(m.array, origin, end_point, (0,0,0), -1) 
            cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, help="Path of the model",
                        default="/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk")
    parser.add_argument("--fps", type=int, help="Frames per second")
    parser.add_argument("--bbox-normalization", action=argparse.BooleanOptionalAction, help="Normalize bbox")
    parser.add_argument("--bbox-order", choices=["yx", "xy"], default="yx",
                        help="Set bbox order yx -> (y0, x0, y1, x1) xy -> (x0, y0, x1, y1)")
    parser.add_argument("--threshold", type=float, default=0.55, help="Detection threshold")
    parser.add_argument("--iou", type=float, default=0.65, help="Set iou threshold")
    parser.add_argument("--max-detections", type=int, default=10, help="Set max detections")
    parser.add_argument("--ignore-dash-labels", action=argparse.BooleanOptionalAction, help="Remove '-' labels ")
    parser.add_argument("--postprocess", choices=["", "nanodet"],
                        default=None, help="Run post process of type")
    parser.add_argument("-r", "--preserve-aspect-ratio", action=argparse.BooleanOptionalAction,
                        help="preserve the pixel aspect ratio of the input tensor")
    parser.add_argument("--labels", type=str,
                        help="Path to the labels file")
    parser.add_argument("--print-intrinsics", action="store_true",
                        help="Print JSON network_intrinsics then exit")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()

    # This must be called before instantiation of Picamera2
    imx500 = IMX500(args.model)
    intrinsics = imx500.network_intrinsics
    if not intrinsics:
        intrinsics = NetworkIntrinsics()
        intrinsics.task = "object detection"
    elif intrinsics.task != "object detection":
        print("Network is not an object detection task", file=sys.stderr)
        exit()

    # Override intrinsics from args
    for key, value in vars(args).items():
        if key == 'labels' and value is not None:
            with open(value, 'r') as f:
                intrinsics.labels = f.read().splitlines()
        elif hasattr(intrinsics, key) and value is not None:
            setattr(intrinsics, key, value)

    # Defaults
    if intrinsics.labels is None:
        with open("assets/coco_labels.txt", "r") as f:
            intrinsics.labels = f.read().splitlines()
    intrinsics.update_with_defaults()

    if args.print_intrinsics:
        print(intrinsics)
        exit()

    # get camera version
    Camera_Version()

    # Configure and start Picamera2.
    model_h, model_w = imx500.get_input_size()
    video_w, video_h = v_width,v_height
    main  = {'size': (video_w, video_h), 'format': 'YUV420'}
    lores = {'size': (model_w, model_h), 'format': 'YUV420'}
    picam2 = Picamera2(imx500.camera_num)
    config = picam2.create_preview_configuration(main, lores=lores,controls={"FrameRate": intrinsics.inference_rate}, buffer_count=12)
    imx500.show_network_fw_progress_bar()
    picam2.configure(config)
    encoder = H264Encoder(bitrate=2000000)
    circular = CircularOutput2(buffer_duration_ms=5000)
    picam2.start_preview(Preview.QTGL, x=0, y=0, width=480, height=480)
    picam2.start_recording(encoder, circular)
    if intrinsics.preserve_aspect_ratio:
        imx500.set_auto_aspect_ratio()

    last_results = None
    picam2.pre_callback = draw_detections

    while True:
        last_results = parse_detections(picam2.capture_metadata())
        # capture frame
        frame = picam2.capture_array('lores')
        frame = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
        frame = frame[0:320, 0:320]
        # detected label
        data = label.split("(")
        category = data[0][:-1]
        value = data[1][:-1]
        if category in objects and float(value) > threshold:
            startrec = time.monotonic()
            # start recording
            if not encoding:
                encoding = True
                now = datetime.datetime.now()
                timestamp = now.strftime("%y%m%d_%H%M%S")
                print("New  Detection",timestamp,label)
                circular.open_output(PyavOutput("/run/shm/" + timestamp +".mp4"))
                # save lores image
                cv2.imwrite(h_user + "/Pictures/" + str(timestamp) + ".jpg",frame)
                rec_led.on()
                # show captured lores trigger image
                Pics = glob.glob(h_user + '/Pictures/*.jpg')
                Pics.sort()
                p = len(Pics)-1
                img = cv2.cvtColor(frame,cv2.COLOR_RGB2BGR)
                image = pygame.surfarray.make_surface(img)
                image = pygame.transform.scale(image,(320,320))
                image = pygame.transform.rotate(image,int(90))
                image = pygame.transform.flip(image,0,1)
                windowSurfaceObj.blit(image,(0,51))
                text(str(p+1) + "/" + str(p+1),100,120,100,10,375,18,60)
                pic = Pics[p].split("/")
                text(str(pic[4]),100,120,100,160,375,18,320)
                text("    ",100,100,100,163,15,18,70)
                text("    ",100,100,100,243,15,18,70)
                pygame.display.update()
        # stop recording
        if encoding and (time.monotonic() - startrec > v_length):
            time.sleep(5) 
            now = datetime.datetime.now()
            timestamp2 = now.strftime("%y%m%d_%H%M%S")
            print("Stopped Record", timestamp2)
            circular.close_output()
            encoding = False
            rec_led.off()
        category = ""
        value = 0.0
        label = " ( "
        # move mp4s
        if time.monotonic() - startmp4 > mp4_timer and not encoding:
                startmp4 = time.monotonic()
                Videos = glob.glob('/run/shm/*.mp4')
                Videos.sort()
                # move Video RAM mp4s to SD card
                for xx in range(0,len(Videos)):
                    if not os.path.exists(h_user + "/" + '/Videos/' + Videos[xx]):
                        shutil.move(Videos[xx], h_user + '/Videos/')
                Pics = glob.glob(h_user + '/Pictures/*.jpg')
                Pics.sort()
                if len(Pics) > 0:
                  pic = Pics[p].split("/")
                  pipc = h_user + '/Videos/' + pic[4][:-3] + "mp4"
                  if os.path.exists(pipc):
                    text("DELETE",100,100,100,163,15,18,60)
                    text("DEL ALL",100,100,100,10,415,16,60)
                    USB_Files  = []
                    USB_Files  = (os.listdir(m_user))
                    if len(USB_Files) > 0:
                        text("  to USB",100,100,100,243,15,18,60)
                  else:
                    text("    ",100,100,100,163,15,18,70)
                    text("    ",100,100,100,243,15,18,70)
                    text("    ",100,100,100,10,415,18,70)
                else:
                    text("    ",100,100,100,163,15,18,70)
                    text("    ",100,100,100,243,15,18,70)
                    text("    ",100,100,100,10,415,18,70)

                # auto shutdown
                if auto_sd == 1:
                    # check if clock synchronised
                    if "System clock synchronized: yes" in os.popen("timedatectl").read().split("\n"):
                        synced = 1
                    else:
                        synced = 0
                    # check current hour and shutdown
                    now = datetime.datetime.now()
                    sd_time = now.replace(hour=sd_hour, minute=sd_mins, second=0, microsecond=0)
                    if now >= sd_time and time.monotonic() - startup > 300 and synced == 1:
                        # move jpgs and mp4s to USB if present
                        time.sleep(2 * mp4_timer)
                        USB_Files  = []
                        USB_Files  = (os.listdir(m_user))
                        if len(USB_Files) > 0:
                            usedusb = os.statvfs(m_user + "/" + USB_Files[0] + "/")
                            USB_storage = ((1 - (usedusb.f_bavail / usedusb.f_blocks)) * 100)
                        if len(USB_Files) > 0 and USB_storage < 90:
                            Videos = glob.glob(h_user + '/Videos/*.mp4')
                            Videos.sort()
                            for xx in range(0,len(Videos)):
                                movi = Videos[xx].split("/")
                                if not os.path.exists(m_user + "/" + USB_Files[0] + "/Videos/" + movi[4]):
                                    shutil.move(Videos[xx],m_user + "/" + USB_Files[0] + "/Videos/")
                            Pics = glob.glob(h_user + '/Pictures/*.jpg')
                            Pics.sort()
                            for xx in range(0,len(Pics)):
                                pic = Pics[xx].split("/")
                                if not os.path.exists(m_user + "/" + USB_Files[0] + "/Pictures/" + pic[4]):
                                    shutil.move(Pics[xx],m_user + "/" + USB_Files[0] + "/Pictures/")
                        time.sleep(5)
                        # shutdown
                        os.system("sudo shutdown -h now")

        #check for any mouse button presses
        for event in pygame.event.get():
                    if (event.type == MOUSEBUTTONUP):
                        mousex, mousey = event.pos
                        # delete ALL Pictures and Videos
                        if mousex < 80 and mousey > 400 and event.button == 3:
                            Videos = glob.glob(h_user + '/Videos/*.mp4')
                            Videos.sort()
                            for w in range(0,len(Videos)):
                                os.remove(Videos[w])
                            Pics = glob.glob(h_user + '/Pictures/*.jpg')
                            Pics.sort()
                            for w in range(0,len(Pics)):
                                os.remove(Pics[w])
                            pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,371,320,28))
                            pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,51,320,320))
                            p = 0
                        # camera control
                        # MODE
                        if mousex > 80 and mousex < 160 and mousey > 400:
                            if event.button == 3 or event.button == 5:
                                mode -=1
                                if mode < 0:
                                    mode = 3
                            else:
                                mode +=1
                                if mode > 3:
                                    mode = 0
                            text(str(modes[mode]),100,100,100,95,420,18,60)
                            if mode == 0:
                                picam2.set_controls({"AeEnable": False,"ExposureTime": speed,"AnalogueGain": gain})
                                text("SPEED",100,100,100,170,402,18,60)
                                text(str(speed),100,100,100,170,420,18,60)
                            else:
                                if mode == 1:
                                    picam2.set_controls({"AeEnable": True,"AeExposureMode": controls.AeExposureModeEnum.Normal,"AnalogueGain": gain})
                                elif mode == 2:
                                    picam2.set_controls({"AeEnable": True,"AeExposureMode": controls.AeExposureModeEnum.Short,"AnalogueGain": gain})
                                elif mode == 3:
                                    picam2.set_controls({"AeEnable": True,"AeExposureMode": controls.AeExposureModeEnum.Long,"AnalogueGain": gain})
                                text(" ",100,100,100,170,402,18,60)
                                text(" ",100,100,100,170,420,18,60)
                        # SHUTTER SPEED
                        if mousex > 160 and mousex < 240 and mousey > 400 and mode == 0:
                            if event.button == 3 or event.button == 5:
                                speed -=1000
                                speed = max(1000,speed)
                            else:
                                speed += 1000
                                speed = min(100000,speed)
                            picam2.set_controls({"AeEnable": False,"ExposureTime": speed,"AnalogueGain": gain})
                            text("SPEED",100,100,100,170,402,18,60)
                            text(str(speed),100,100,100,170,420,18,60)
                        # GAIN
                        if mousex > 240 and mousey > 400:
                            if event.button == 3 or event.button == 5:
                                gain -=1
                                gain = max(0,gain)
                            else:
                                gain +=1
                                gain = min(64,gain)
                            picam2.set_controls({"AnalogueGain": gain})
                            text("GAIN",100,100,100,250,402,18,60)
                            if gain != 0:
                                text(str(gain),100,100,100,250,420,18,60)
                            else:
                                text("Auto",100,100,100,250,420,18,60)
                        # show previous
                        elif mousex < 80 and mousey < 50:
                            Pics = glob.glob(h_user + '/Pictures/*.jpg')
                            Pics.sort()
                            p -= 1
                            if p < 0:
                                p = 0
                            if len(Pics) > 0:
                                image = pygame.image.load(Pics[p])
                                image = pygame.transform.scale(image,(320,320))
                                windowSurfaceObj.blit(image,(0,51))
                                text(str(p+1) + "/" + str(p+1),100,120,100,10,375,18,60)
                                pic = Pics[p].split("/")
                                text(str(pic[4]),100,120,100,160,375,18,320)
                                pygame.display.update()
                        # show next
                        elif mousex > 80 and mousex < 160 and mousey < 50:
                            Pics = glob.glob(h_user + '/Pictures/*.jpg')
                            Pics.sort()
                            p += 1
                            if p > len(Pics)-1:
                                p = len(Pics)-1
                            if len(Pics) > 0:
                                image = pygame.image.load(Pics[p])
                                image = pygame.transform.scale(image,(320,320))
                                windowSurfaceObj.blit(image,(0,51))
                                pic = Pics[p].split("/")
                                text(str(pic[4]),100,120,100,160,375,18,320)
                                text(str(p+1) + "/" + str(p+1),100,120,100,10,375,18,60)
                                pygame.display.update()
                        # delete picture and video
                        elif mousex > 160 and mousex < 240 and mousey < 50 and event.button == 3:
                            pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,51,320,320))
                            Pics = glob.glob(h_user + '/Pictures/*.jpg')
                            Pics.sort()
                            Videos = glob.glob(h_user + '/Videos/*.mp4')
                            Videos.sort()
                            if len(Pics) > 0:
                                pic = Pics[p].split("/")
                                pipc = h_user + '/Videos/' + pic[4][:-3] + "mp4"
                                if os.path.exists(pipc):
                                   os.remove(Pics[p])
                                   if len(Videos) > 0:
                                       os.remove(pipc)
                                       print("DELETED", pipc)
                                Videos = glob.glob(h_user + '/Videos/*.mp4')
                                Videos.sort()
                                Pics = glob.glob(h_user + '/Pictures/*.jpg')
                                Pics.sort()
                            if p > len(Pics) - 1:
                                p -= 1
                            if len(Pics) > 0:
                                image = pygame.image.load(Pics[p])
                                image = pygame.transform.scale(image,(320,320))
                                windowSurfaceObj.blit(image,(0,51))
                                pic = Pics[p].split("/")
                                text(str(pic[4]),100,120,100,160,375,18,320)
                            else:
                                pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,375,320,20))
                            pygame.display.update()
                        # move picture and video to USB
                        elif mousex > 240 and mousey < 50  and event.button != 3:
                            pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,51,320,320))
                            Pics = glob.glob(h_user + '/Pictures/*.jpg')
                            Pics.sort()
                            Videos = glob.glob(h_user + '/Videos/*.mp4')
                            Videos.sort()
                            if len(Pics) > 0:
                                pic = Pics[p].split("/")
                                pipc = h_user + '/Videos/' + pic[4][:-3] + "mp4"
                                print(pipc)
                                # move mp4s to USB if present, and less than 90% full
                                USB_Files  = []
                                USB_Files  = (os.listdir(m_user))
                                if len(USB_Files) > 0:
                                    if not os.path.exists(m_user + "/'" + USB_Files[0] + "'/Videos/") :
                                        os.system('mkdir ' + m_user + "/'" + USB_Files[0] + "'/Videos/")
                                    if not os.path.exists(m_user + "/'" + USB_Files[0] + "'/Pictures/") :
                                        os.system('mkdir ' + m_user + "/'" + USB_Files[0] + "'/Pictures/")
                                    usedusb = os.statvfs(m_user + "/" + USB_Files[0] + "/")
                                    USB_storage = ((1 - (usedusb.f_bavail / usedusb.f_blocks)) * 100)
                                    print(USB_storage)
                                if len(USB_Files) > 0 and USB_storage < 90 and os.path.exists(pipc):
                                    if not os.path.exists(m_user + "/" + USB_Files[0] + "/Pictures/" + pic[4]):
                                        shutil.move(Pics[p],m_user + "/" + USB_Files[0] + "/Pictures/")
                                    if os.path.exists(pipc):
                                        vid = pipc.split("/")
                                        if not os.path.exists(m_user + "/" + USB_Files[0] + "/Videos/" + vid[4]):
                                            shutil.move(Videos[p],m_user + "/" + USB_Files[0] + "/Videos/")
                                Videos = glob.glob(h_user + '/Videos/*.mp4')
                                Videos.sort()
                                Pics = glob.glob(h_user + '/Pictures/*.jpg')
                                Pics.sort()
                            if p > len(Pics) - 1:
                                p -= 1
                            if len(Pics) > 0:
                                image = pygame.image.load(Pics[p])
                                image = pygame.transform.scale(image,(320,320))
                                windowSurfaceObj.blit(image,(0,51))
                                pic = Pics[p].split("/")
                                text(str(pic[4]),100,120,100,160,375,18,320)
                            else:
                                pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,375,320,20))
                            pygame.display.update()
                            
                        # move ALL pictures and videos to USB
                        elif mousex > 240 and mousey < 50 and event.button == 3:
                            pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,51,320,320))
                            Pics = glob.glob(h_user + '/Pictures/*.jpg')
                            Pics.sort()
                            Videos = glob.glob(h_user + '/Videos/*.mp4')
                            Videos.sort()
                            if len(Pics) > 0 or len(Videos) > 0:
                                # move mp4s and jpgs to USB if present, and USB storage < 90% full
                                USB_Files  = []
                                USB_Files  = (os.listdir(m_user))
                                if len(USB_Files) > 0:
                                    # make directories (if required)
                                    if not os.path.exists(m_user + "/'" + USB_Files[0] + "'/Videos/") :
                                        os.system('mkdir ' + m_user + "/'" + USB_Files[0] + "'/Videos/")
                                    if not os.path.exists(m_user + "/'" + USB_Files[0] + "'/Pictures/") :
                                        os.system('mkdir ' + m_user + "/'" + USB_Files[0] + "'/Pictures/")
                                    usedusb = os.statvfs(m_user + "/" + USB_Files[0] + "/")
                                    USB_storage = ((1 - (usedusb.f_bavail / usedusb.f_blocks)) * 100)
                                    print(USB_storage)
                                if len(USB_Files) > 0 and USB_storage < 90:
                                    for w in range(0,len(Pics)):
                                        pic = Pics[w].split("/")
                                        if not os.path.exists(m_user + "/" + USB_Files[0] + "/Pictures/" + pic[4]):
                                            shutil.move(Pics[w],m_user + "/" + USB_Files[0] + "/Pictures/")
                                    for w in range(0,len(Videos)):
                                        vid = Videos[w].split("/")
                                        if not os.path.exists(m_user + "/" + USB_Files[0] + "/Videos/" + vid[4]):
                                            shutil.move(Videos[w],m_user + "/" + USB_Files[0] + "/Videos/")
                                Videos = glob.glob(h_user + '/Videos/*.mp4')
                                Videos.sort()
                                Pics = glob.glob(h_user + '/Pictures/*.jpg')
                                Pics.sort()
                            if p > len(Pics) - 1:
                                p -= 1
                            if len(Pics) > 0:
                                image = pygame.image.load(Pics[p])
                                image = pygame.transform.scale(image,(320,320))
                                windowSurfaceObj.blit(image,(0,51))
                                pic = Pics[p].split("/")
                                text(str(pic[4]),100,120,100,160,375,18,320)
                            else:
                                pygame.draw.rect(windowSurfaceObj,(0,0,0),Rect(0,375,320,20))
                            pygame.display.update()
                        Videos = glob.glob(h_user + '/Videos/*.mp4')
                        Videos.sort()
                        Pics = glob.glob(h_user + '/Pictures/*.jpg')
                        Pics.sort()
                        Pics = glob.glob(h_user + '/Pictures/*.jpg')
                        Pics.sort()
                        if len(Pics) > 0:
                            pic = Pics[p].split("/")
                            pipc = h_user + '/Videos/' + pic[4][:-3] + "mp4"
                            if os.path.exists(pipc):
                                text("DELETE",100,100,100,163,15,18,60)
                                text("DEL ALL",100,100,100,10,415,16,60)
                                USB_Files  = []
                                USB_Files  = (os.listdir(m_user))
                                if len(USB_Files) > 0:
                                    text("  to USB",100,100,100,243,15,18,60)
                            else:
                                text("    ",100,100,100,163,15,18,70)
                                text("    ",100,100,100,243,15,18,70)
                                text("    ",100,100,100,10,415,18,70)
                        else:
                            text("    ",100,100,100,163,15,18,70)
                            text("    ",100,100,100,243,15,18,70)
                            text("    ",100,100,100,10,415,18,70)

                        if len(Pics) > 0:
                            msg = str(p+1) + "/" + str(len(Pics))
                            pic = Pics[p].split("/")
                            text(str(pic[4]),100,120,100,160,375,18,320)
                        else:
                            msg = str(len(Pics))
                        text(msg,100,120,100,10,375,18,60)
                        pygame.display.update()

                        defaults[0] = mode
                        defaults[1] = speed
                        defaults[2] = gain
                        with open(config_file, 'w') as f:
                            for item in defaults:
                                f.write("%s\n" % item)

            

