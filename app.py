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
import subprocess
import datetime
import sys

from collections import deque
from logger import ConsoleLogger
console = ConsoleLogger(True)

dirPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/www/"
sysPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

# Monitoring settings
MAX_SECONDS = 1800 # 30 minutes
SECONDS_INBETWEEN = 10 # 10 seconds apart between updates
HISTORY_LEN = int(MAX_SECONDS / SECONDS_INBETWEEN)

# Other settings
VERSION = '26.9.21'
NAME = 'AETERNA'

# HTML/CSS classes depending on sites
# SELECTED_CLASSNAME = "selected"

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

# Minecraft server management
MC_SCRIPT = sysPath + "/minecraft_server.py"
 
mc_run_flag = False    # Should the minecraft server be (re)started? (one-shot)
mc_is_running = False  # Is the minecraft server currently running?
 
console_output = []    # This is the minecraft console output as lines. Basically the output but split("\n")
input_queue = deque()  # This is the input queue. Pending inputs are in here. The server manager should check
                        # its left element to see the current pending input, the element to be removed is the left since its the oldest
                        # in the queue.
 
_console_lock = threading.Lock()  # guards console_output, since both the
                                   # output reader thread and the input
                                   # feeder thread append to it
_mc_proc: subprocess.Popen | None = None  # the current server subprocess, if any
_shutdown_event = threading.Event()  # set by stop_server_manager() to unwind everything
 
RESTART_HOUR = 3
RESTART_MINUTE = 30
 
 
def _append_output(line: str) -> None:
    with _console_lock:
        console_output.append(line)
 
 
def _read_server_output(proc: subprocess.Popen) -> None:
    """Reads minecraft_server.py's stdout line by line, in realtime."""
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        if line == "":
            break
        _append_output(line.rstrip("\n"))
 
 
def _feed_server_input(proc: subprocess.Popen) -> None:
    """Watches input_queue and forwards pending commands to the server's stdin."""
    assert proc.stdin is not None
    while proc.poll() is None:
        if input_queue:
            command = input_queue.popleft()
            try:
                proc.stdin.write(command if command.endswith("\n") else command + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                break
            _append_output("> " + command)
        else:
            time.sleep(0.05)
 
 
def _run_minecraft_process() -> None:
    """Starts minecraft_server.py and blocks until it exits."""
    global mc_is_running, _mc_proc, console_output
    console_output = [] # Restarting the output
 
    proc = subprocess.Popen(
        [sys.executable, MC_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
        encoding="utf-8",
        errors="replace",
    )
    _mc_proc = proc
    mc_is_running = True
 
    out_thread = threading.Thread(target=_read_server_output, args=(proc,), daemon=True)
    in_thread = threading.Thread(target=_feed_server_input, args=(proc,), daemon=True)
    out_thread.start()
    in_thread.start()
 
    proc.wait()  # blocks the calling (manager) thread until the server exits
    out_thread.join(timeout=5)
    # in_thread exits on its own the moment proc.poll() stops returning None
 
    mc_is_running = False
    _mc_proc = None
 
 
def _restart_scheduler() -> None:
    """Triggers a graceful stop + kickstart every day at 3:30 AM."""
    global mc_run_flag
 
    while not _shutdown_event.is_set():
        now = datetime.datetime.now()
        target = now.replace(hour=RESTART_HOUR, minute=RESTART_MINUTE, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
 
        # Event.wait() returns True if the event was set before the
        # timeout elapsed - use that to bail out early instead of
        # sleeping through a shutdown request.
        if _shutdown_event.wait(timeout=(target - now).total_seconds()):
            return
 
        if mc_is_running:
            input_queue.append("stop")
            # Wait for the current process to actually exit before asking
            # for it to be started again - mc_run_flag only does anything
            # while mc_is_running is False.
            while mc_is_running:
                if _shutdown_event.wait(timeout=1):
                    return
            if not _shutdown_event.is_set():
                mc_run_flag = True
        # If it was already off at 3:30, leave it off - mc_run_flag is an
        # explicit "please start" signal, not something the scheduler
        # should invent on its own.
 
 
def start_server_manager() -> None:
    """
    Monitors mc_run_flag / mc_is_running and (re)starts minecraft_server.py
    whenever a start is requested while nothing is running. Runs forever -
    call this from its own thread.
    """
    global mc_run_flag, mc_is_running
 
    threading.Thread(target=_restart_scheduler, daemon=True).start()
 
    while not _shutdown_event.is_set():
        if mc_run_flag and not mc_is_running and not _shutdown_event.is_set():
            mc_run_flag = False
            _run_minecraft_process()  # blocks here until the server stops
        else:
            _shutdown_event.wait(timeout=1)
 
 
def stop_server_manager(timeout: float = 60) -> None:
    """
    Call this from the parent thread when the app wants to shut down.
 
    Gracefully stops the Minecraft server if one is running, and tells
    start_server_manager()'s loop (and the restart scheduler) to return
    instead of continuing to run forever. Blocks until the server has
    actually exited, or until `timeout` seconds pass - at which point it
    force-kills the process rather than hanging indefinitely.
 
    After calling this, the thread(s) running start_server_manager() will
    finish on their own shortly; join() them if you need to be sure they
    have before your program exits.
    """
    _shutdown_event.set()
 
    if not mc_is_running:
        return
 
    proc_ref = _mc_proc  # snapshot before it can be cleared out from under us
    input_queue.append("stop")
 
    deadline = time.monotonic() + timeout
    while mc_is_running and time.monotonic() < deadline:
        time.sleep(0.5)
 
    if mc_is_running and proc_ref is not None:
        _append_output(f"> [manager] server did not stop within {timeout}s, forcing shutdown")
        try:
            proc_ref.terminate()
            proc_ref.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc_ref.kill()
        except OSError:
            pass
 



# This instance is my WSGI app
app = Flask(__name__)

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

# Selected highlights
# DASHBOARD_SELECTED = 0x2FFF
# FILES_SELECTED = 0x3FFF
# MINECRAFT_SELECTED = 0x4FFF
def serve_generic_site(path: str, headers: Headers):
    if (check_token(headers)):
        # OK
        # if selected_highlight == DASHBOARD_SELECTED:
        #     return render_template_string(
        #         open(path, "r", encoding='utf-8').read(),
        #         server_name=NAME, user_name=get_user(headers), dashboard_selected=SELECTED_CLASSNAME
        #     ), 200
        # elif selected_highlight == FILES_SELECTED:
        #     return render_template_string(
        #         open(path, "r", encoding='utf-8').read(),
        #         server_name=NAME, user_name=get_user(headers), files_selected=SELECTED_CLASSNAME
        #     ), 200
        # elif selected_highlight == MINECRAFT_SELECTED:
        #     return render_template_string(
        #         open(path, "r", encoding='utf-8').read(),
        #         server_name=NAME, user_name=get_user(headers), minecraft_selected=SELECTED_CLASSNAME
        #     ), 200
        # else:
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

@app.route("/minecraft")
def minecraft():
    return serve_generic_site(dirPath + "minecraft.html", request.headers)

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

# Minecraft server
SERVER_PROPERTIES_PATH = sysPath + "/mc/server.properties"

@app.route("/mc-get-console")
def mc_get_console():
    # Get console output
    # But we need to make sure the user is an actually real user
    if request.headers.get("Token") in session_tokens:
        start_index = request.headers.get("Start")
        if start_index:
            return Response(json.dumps(console_output[int(start_index):]), mimetype="application/json"), 200
        else:
            return Response(json.dumps(console_output), mimetype="application/json"), 200
    return Response("[]", mimetype="application/json"), 403

@app.route("/mc-get-status")
def mc_get_status():
    # Get current mc server status
    return Response(json.dumps(mc_is_running), mimetype="application/json"), 200

@app.route("/mc-kickstart")
def mc_start_server():
    # Kickstart the server up
    if request.headers.get("Token") in session_tokens:
        global mc_run_flag
        mc_run_flag = True
        return Response("{}", mimetype="application/json"), 200
    return Response("{}", mimetype="application/json"), 403

@app.route("/mc-input-command")
def mc_input_command():
    # Input command into minecraft server
    if request.headers.get("Token") in session_tokens:
        command = request.headers.get("Command")
        input_queue.append(command)
        return Response("{}", mimetype="application/json"), 200
    return Response("{}", mimetype="application/json"), 403

@app.route("/mc-get-properties")
def mc_get_properties():
    # Get server.properties
    if request.headers.get("Token") in session_tokens:
        with open(SERVER_PROPERTIES_PATH, "r", encoding='utf-8') as f:
            return Response(json.dumps(f.read()), mimetype="application/json"), 200
    return Response("\"\"", mimetype="application/json"), 403

@app.route("/mc-apply-properties", methods=['POST'])
def mc_apply_properties():
    if request.headers.get("Token") in session_tokens:
        with open(SERVER_PROPERTIES_PATH, "w", encoding='utf-8') as f:
            f.write(request.get_json()["data"])

        return Response("{}", mimetype="application/json"), 200
    return Response("{}", mimetype="application/json"), 403

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