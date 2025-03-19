# PI_imx500_detection

Pi + Pi imx500 AI camera. Tested on Pi4 and Pi5.

It is a modified version of imx500_object_detection_demo.py

Captures videos as .mp4 videos

v_width and v_height are set for a Pi GS camera, you may need to change to suit other cameras ....

Runs a pre-capture buffer of 1,2,3,5 or 10 seconds

you can set the objects to detect in line 49, objects = ["cat","bear","bird"], the objects must be in coco_labels.txt file

Copy imx500_detect_2.py into /home/USER/picamera2/examples/imx500

sudo apt install python3-opencv -y

Videos saved to ram and then copied to /home/USERNAME/Videos

stills saved to /home/USER/Pictures

to run ... python3 imx500_detect_2.py
