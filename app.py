from flask import Flask, send_file, abort, Response, request, render_template_string, redirect, url_for
from werkzeug.datastructures import Headers
# from http.cookies import SimpleCookie
import os
import time
import psutil
import json
import threading
import bcrypt
import secrets

from collections import deque
from logger import ConsoleLogger
console = ConsoleLogger(True)

# Monitoring settings
MAX_SECONDS = 1800 # 30 minutes
SECONDS_INBETWEEN = 10 # 10 seconds apart between updates
HISTORY_LEN = int(MAX_SECONDS / SECONDS_INBETWEEN)

# Other settings
VERSION = '26.9.21'
NAME = 'AETERNA'

# Monitoring preparations variables
memory = psutil.virtual_memory()

# ----------------------------------------------------------------------------
# Monitoring functionality (live deques, capped to HISTORY_LEN samples)
# ----------------------------------------------------------------------------

# CPU: total (non-idle), user time %, system time %
cpu_total_mon_history   : deque[float] = deque(maxlen=HISTORY_LEN)
cpu_user_mon_history    : deque[float] = deque(maxlen=HISTORY_LEN)
cpu_system_mon_history  : deque[float] = deque(maxlen=HISTORY_LEN)

# Memory: used / buffers / cached / free, all in GiB
ram_used_mon_history    : deque[float] = deque(maxlen=HISTORY_LEN)
ram_buffers_mon_history : deque[float] = deque(maxlen=HISTORY_LEN)
ram_cached_mon_history  : deque[float] = deque(maxlen=HISTORY_LEN)
ram_free_mon_history    : deque[float] = deque(maxlen=HISTORY_LEN)

# Network: up / down, in Mbps (unchanged behaviour)
net_up_mon_history      : deque[float] = deque(maxlen=HISTORY_LEN)
net_down_mon_history    : deque[float] = deque(maxlen=HISTORY_LEN)

# Disk I/O: read / write throughput, in MB/s
disk_read_mon_history   : deque[float] = deque(maxlen=HISTORY_LEN)
disk_write_mon_history  : deque[float] = deque(maxlen=HISTORY_LEN)

ram_total        = float(memory.total) / (1024 ** 3)
disk_mon         = 0.0   # disk *space* used, in GB (decimal) - unrelated to disk I/O
disk_total       = float(psutil.disk_usage("/").total) / (1000 ** 3)
boot_time        = int(psutil.boot_time())

# Cached "as list" versions of the above (so the JSON route doesn't have to
# convert a deque -> list on every request)
cpu_total_history_list  : list[float] = []
cpu_user_history_list   : list[float] = []
cpu_system_history_list : list[float] = []

ram_used_history_list    : list[float] = []
ram_buffers_history_list : list[float] = []
ram_cached_history_list  : list[float] = []
ram_free_history_list    : list[float] = []

net_up_history_list   : list[float] = []
net_down_history_list : list[float] = []

disk_read_history_list  : list[float] = []
disk_write_history_list : list[float] = []

_stop_event = threading.Event()

net = psutil.net_io_counters()
old_bytes_sent = net.bytes_sent
old_bytes_recv = net.bytes_recv

_disk_io = psutil.disk_io_counters()
old_bytes_read    = _disk_io.read_bytes  if _disk_io else 0
old_bytes_written = _disk_io.write_bytes if _disk_io else 0


def start_monitoring():
    global old_bytes_recv, old_bytes_sent, old_bytes_read, old_bytes_written, disk_mon
    global cpu_total_history_list, cpu_user_history_list, cpu_system_history_list
    global ram_used_history_list, ram_buffers_history_list, ram_cached_history_list, ram_free_history_list
    global net_up_history_list, net_down_history_list
    global disk_read_history_list, disk_write_history_list

    psutil.cpu_percent(interval=None)        # discard meaningless first reading
    psutil.cpu_times_percent(interval=None)  # discard meaningless first reading
    next_tick = time.monotonic() + SECONDS_INBETWEEN
    while True:
        remaining = next_tick - time.monotonic()
        # wait() returns True as soon as stop is signaled, instead of
        # blocking for the full interval like time.sleep would
        if remaining > 0 and _stop_event.wait(remaining):
            break
        if _stop_event.is_set():
            break

        # ---- CPU: total / user / system -----------------------------------
        cpu_total = psutil.cpu_percent(interval=None)
        cpu_times = psutil.cpu_times_percent(interval=None)
        cpu_total_mon_history.append(cpu_total)
        cpu_user_mon_history.append(cpu_times.user)
        cpu_system_mon_history.append(cpu_times.system)

        # ---- Memory: used / buffers / cached / free ------------------------
        mem = psutil.virtual_memory()
        ram_used_mon_history.append(float(mem.used) / (1024 ** 3))
        # buffers/cached are Linux-only fields on psutil; fall back to 0 elsewhere
        ram_buffers_mon_history.append(float(getattr(mem, "buffers", 0)) / (1024 ** 3))
        ram_cached_mon_history.append(float(getattr(mem, "cached", 0)) / (1024 ** 3))
        ram_free_mon_history.append(float(mem.free) / (1024 ** 3))

        # ---- Disk: space used (GB) + I/O throughput (MB/s) ------------------
        disk_mon = float(psutil.disk_usage("/").used) / (1000 ** 3)

        disk_io = psutil.disk_io_counters()
        if disk_io:
            bytes_read = disk_io.read_bytes
            bytes_written = disk_io.write_bytes
            disk_read_mon_history.append(float(bytes_read - old_bytes_read) / (1024 ** 2) / SECONDS_INBETWEEN)
            disk_write_mon_history.append(float(bytes_written - old_bytes_written) / (1024 ** 2) / SECONDS_INBETWEEN)
            old_bytes_read = bytes_read
            old_bytes_written = bytes_written
        else:
            disk_read_mon_history.append(0.0)
            disk_write_mon_history.append(0.0)

        # ---- Network: up / down (Mbps) --------------------------------------
        net = psutil.net_io_counters()
        bytes_sent = net.bytes_sent
        bytes_recv = net.bytes_recv

        net_up_mon_history.append(float(bytes_sent - old_bytes_sent) / 125000.0 / SECONDS_INBETWEEN)
        net_down_mon_history.append(float(bytes_recv - old_bytes_recv) / 125000.0 / SECONDS_INBETWEEN)
        old_bytes_sent = bytes_sent
        old_bytes_recv = bytes_recv

        # ---- snapshot deques into plain lists for the JSON route ------------
        cpu_total_history_list  = [*cpu_total_mon_history]
        cpu_user_history_list   = [*cpu_user_mon_history]
        cpu_system_history_list = [*cpu_system_mon_history]

        ram_used_history_list    = [*ram_used_mon_history]
        ram_buffers_history_list = [*ram_buffers_mon_history]
        ram_cached_history_list  = [*ram_cached_mon_history]
        ram_free_history_list    = [*ram_free_mon_history]

        net_up_history_list   = [*net_up_mon_history]
        net_down_history_list = [*net_down_mon_history]

        disk_read_history_list  = [*disk_read_mon_history]
        disk_write_history_list = [*disk_write_mon_history]

        next_tick += SECONDS_INBETWEEN  # absolute schedule, no cumulative drift

def stop_monitoring():
    _stop_event.set()

# This instance is my WSGI app
app = Flask(__name__)

dirPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/www/"
sysPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

# Login token special checkers
session_tokens = {}

def parse_cookies(cookie_str : str) -> dict:
    cookie_dict = {
        item.split("=")[0].strip(): item.split("=")[1].strip()
        for item in cookie_str.split(";")
        if "=" in item
    }

    return cookie_dict


def check_token(headers: Headers) -> bool:
    cookies_str = headers.get("Cookie")

    if not cookies_str: return False

    token = parse_cookies(cookies_str)["token"]

    return token in session_tokens

def get_user(headers: Headers) -> str | None:
    cookies_str = headers.get("Cookie")
    if not cookies_str: return None

    token = parse_cookies(cookies_str)["token"]

    if not token in session_tokens: return ""
    else: return session_tokens[token]

def serve_generic_site(path: str, headers: Headers):
    if (check_token(headers)):
        # OK
        return render_template_string(
            open(path, "r", encoding='utf-8').read(),
            server_name=NAME, user_name=get_user(headers)
        ), 200
    else:
        return redirect(url_for('login_page'))

# WSGI routing
@app.route("/")
def home():
    # print(request.headers)
    return serve_generic_site(dirPath + "index.html", request.headers)

@app.route("/status")
def status():
    return open(dirPath + "status.html", "r", encoding='utf-8').read(), 200

@app.route("/get-status")
def get_status():
    # Function to get latest status in JSON form
    form = {
        "cpu_total": cpu_total_history_list,
        "cpu_user": cpu_user_history_list,
        "cpu_system": cpu_system_history_list,

        "ram_used": ram_used_history_list,
        "ram_buffers": ram_buffers_history_list,
        "ram_cached": ram_cached_history_list,
        "ram_free": ram_free_history_list,
        "total_ram": ram_total,

        "disk": disk_mon,
        "disk_total": disk_total,
        "disk_read": disk_read_history_list,
        "disk_write": disk_write_history_list,

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

@app.route("/check-auth")
def login_token_checker():
    return json.dumps(request.headers.get("Token") in session_tokens), 200

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

            # print("New login")
            console.log(f"New login: {request.remote_addr}: {username}/{new_token}")
        else:
            response_payload["success"] = False
            response_payload["message"] = "Wrong username or password."

    return Response(json.dumps(response_payload), mimetype="application/json"), 200

@app.route("/logout")
def login_remove_token():
    cookies_str = request.headers.get("Cookie")
    if cookies_str:
        token = parse_cookies(cookies_str)["token"]

        if token in session_tokens: del session_tokens[token]

    return redirect(url_for('login_page'))

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