# PI_imx500_detection

Pi + Pi imx500 AI camera

It is a modified version of imx500_object_detection_demo.py

Captures videos as .mp4 videos

v_width and v_height are set for a Pi GS camera, you may need to change to suit other cameras ....

Runs a pre-capture buffer of approx 5 seconds

you can set the objects to detect in line 29, objects = ["cat","bear","bird"], the objects must be in coco.txt file

Copy imx500_detect_2.py into /home/USER/picamera2/examples/imx500

Videos saved in /home/USERNAME/Videos

to run ... python3 imx500_detect_2.py
