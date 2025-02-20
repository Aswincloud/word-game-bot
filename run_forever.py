import subprocess
import os

while True:
    if os.path.exists("stop.txt"):
        print("Stop file detected. Exiting...")
        break
    try:
        subprocess.run(["python3.9", "-m", "on9wordchainbot"])
    except KeyboardInterrupt:
        break