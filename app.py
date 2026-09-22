from flask import Flask, send_file, abort, Response, request, render_template_string
import os
import time
import psutil
import json
import threading
import bcrypt
import secrets

from collections import deque

# Monitoring settings
MAX_SECONDS = 1800 # 30 minutes
SECONDS_INBETWEEN = 10 # 10 seconds apart between updates

# Other settings
VERSION = '26.9.21'
NAME = 'AETERNA'

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
sysPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

# WSGI routing
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


# Logging in
@app.route("/login")
def login_page():
    return render_template_string(
        open(dirPath + "login.html", "r", encoding='utf-8').read(), 
        version=VERSION, ip_addr=request.remote_addr, user_agent=request.user_agent.string,
        server_name=NAME
    ), 200

# For login requests
login_rate_limiter = {}
RATE_LIMIT_SECONDS = 30 # 30 seconds after over rate limit
RATE_LIMIT_REPEATS = 3

session_tokens = {}

@app.route("/login-auth")
def login_authorization():
    if request.remote_addr in login_rate_limiter:
        if time.time() - login_rate_limiter[request.remote_addr]["time"] > RATE_LIMIT_SECONDS:
            login_rate_limiter[request.remote_addr] = {
                "time": time.time(),
                "repeats": 1
            }
        else:
            # Smaller or equal to rate limit seconds
            login_rate_limiter[request.remote_addr]["repeats"] += 1

            if login_rate_limiter[request.remote_addr]["repeats"] > 3:
                return('{"success": false, "message": "Rate limited."}')
    else:
        login_rate_limiter[request.remote_addr] = {
            "time": time.time(),
            "repeats": 1
        }

    users = json.load(open(sysPath + "/users.json", "r", encoding='utf-8'))

    username = request.headers.get("Username")
    password = request.headers.get("Password")

    response_payload = {
        "success": False,
        "message": ""
    }

    if not password or not username or not username in users:
        response_payload["success"] = False
        # Stringing along the user. Either they got it both right or not
        # Keep it abstract. Keep them guessin
        response_payload["message"] = "Wrong username or password."
    else:
        # IT DOES EXISTS!111!!!!11!
        target_user_hashed_passwd = str(users[username]["passwd"]).encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), target_user_hashed_passwd):
            new_token = secrets.token_hex(16)

            session_tokens[new_token] = username

            response_payload["success"] = True
            response_payload["message"] = new_token
        else:
            response_payload["success"] = False
            response_payload["message"] = "Wrong username or password."

    return Response(json.dumps(response_payload), mimetype="application/json"), 200

# Normal file handling
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