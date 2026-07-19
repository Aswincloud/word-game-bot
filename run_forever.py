import subprocess
import os
import sys
import time

# Auto restart when script gets killed

while True:
    if os.path.exists("stop.txt"):
        print("Stop file detected. Exiting...")
        break
    try:
        subprocess.run([sys.executable, "-m", "on9wordchainbot"])
        time.sleep(0.2)
    except KeyboardInterrupt:
        break