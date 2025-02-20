import subprocess
import os

run=True
while run:
    if os.path.exists("stop.txt"):
        print("Stop file detected. Exiting...")
        run=False
        break
    try:
        subprocess.run(["python3.9", "-m", "on9wordchainbot"])
    except KeyboardInterrupt:
        break