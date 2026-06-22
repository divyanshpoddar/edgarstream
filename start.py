import os
import subprocess
import sys

service = os.getenv("SERVICE_TYPE", "worker")

if service == "poller":
    subprocess.run([sys.executable, "services/listener/rss_poller.py"])
else:
    subprocess.run([sys.executable, "services/workers/pipeline_worker.py"])
