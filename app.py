from flask import Flask, send_file, abort, Response
import os
import time
import psutil
import json
import threading

from collections import deque

# Monitoring settings
MAX_SECONDS = 1800 # 30 minutes
SECONDS_INBETWEEN = 10 # 10 seconds apart between updates

# Monitoring preparations variables
memory = psutil.virtual_memory()

# Monitoring functionality
cpu_mon_history  : deque[float] = deque(maxlen = int(MAX_SECONDS / SECONDS_INBETWEEN))
ram_mon_history  : deque[float] = deque(maxlen = int(MAX_SECONDS / SECONDS_INBETWEEN))
# disk_mon_history : deque[float] = deque(maxlen = int(MAX_SECONDS / SECONDS_INBETWEEN))
net_up_mon_history  : deque[float] = deque(maxlen = int(MAX_SECONDS / SECONDS_INBETWEEN))
net_down_mon_history  : deque[float] = deque(maxlen = int(MAX_SECONDS / SECONDS_INBETWEEN))
ram_total        = float(memory.total) / (1024 ** 3)
disk_mon         = 0.0
disk_total       = float(psutil.disk_usage("/").total) / (1000 ** 3)
boot_time        = int(psutil.boot_time())

# Monitoring functionality history in list (cached so that converting wont have to happen again)
cpu_mon_history_list: list[float] = []
ram_mon_history_list: list[float] = []
net_up_history_list: list[float] = []
net_down_history_list: list[float] = []

_stop_event = threading.Event()

net = psutil.net_io_counters()
old_bytes_sent = net.bytes_sent
old_bytes_recv = net.bytes_recv

def start_monitoring():
    global old_bytes_recv, old_bytes_sent, disk_mon, cpu_mon_history_list, ram_mon_history_list, net_up_history_list, net_down_history_list

    psutil.cpu_percent(interval=None)  # discard meaningless first reading
    next_tick = time.monotonic() + SECONDS_INBETWEEN
    while True:
        remaining = next_tick - time.monotonic()
        # wait() returns True as soon as stop is signaled, instead of
        # blocking for the full interval like time.sleep would
        if remaining > 0 and _stop_event.wait(remaining):
            break
        if _stop_event.is_set():
            break

        memory = psutil.virtual_memory()
        net = psutil.net_io_counters()

        cpu_mon_history.append(psutil.cpu_percent(interval=None))
        ram_mon_history.append(float(memory.used) / (1024 ** 3))
        # disk_mon_history.append(float(psutil.disk_usage("/").used) / (1000 ** 3))
        disk_mon = float(psutil.disk_usage("/").used) / (1000 ** 3)
        bytes_sent = net.bytes_sent
        bytes_recv = net.bytes_recv

        net_up_mon_history.append(float(bytes_sent - old_bytes_sent) / 125000.0 / SECONDS_INBETWEEN)
        net_down_mon_history.append(float(bytes_recv - old_bytes_recv) / 125000.0 / SECONDS_INBETWEEN)
        old_bytes_sent = bytes_sent
        old_bytes_recv = bytes_recv

        cpu_mon_history_list = [*cpu_mon_history]
        ram_mon_history_list = [*ram_mon_history]
        net_up_history_list = [*net_up_mon_history]
        net_down_history_list = [*net_down_mon_history]

        next_tick += SECONDS_INBETWEEN  # absolute schedule, no cumulative drift

def stop_monitoring():
    _stop_event.set()

# This instance is my WSGI app
app = Flask(__name__)

dirPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/www/"

@app.route("/")
def home():
    return open(dirPath + "index.html", "r", encoding='utf-8').read(), 200

@app.route("/status")
def status():
    return open(dirPath + "status.html", "r", encoding='utf-8').read(), 200

@app.route("/get-status")
def get_status():
    # Function to get latest status in JSON form
    form = {
        "cpu": cpu_mon_history_list,
        "ram": ram_mon_history_list,
        "total_ram": ram_total,
        "disk": disk_mon,
        "disk_total": disk_total,
        "net_up": net_up_history_list,
        "net_down": net_down_history_list,
        "boot": boot_time
    }

    return Response(json.dumps(form), mimetype="application/json"), 200

@app.route("/<path:filename>")
def getfile(filename: str):
    if not filename.endswith(".html"):
        # As long as the file isn't an html
        filePath = dirPath + filename

        if os.path.exists(filePath):
            # return open(filePath, "r", encoding='utf-8').read(), 200
            return send_file(filePath), 200
        else: 
            return "404 Not Found", 404

    return "404 Not Found", 404