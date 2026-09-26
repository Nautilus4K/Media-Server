"""
A separate script for setting up and running Minecraft servers (PurpurMC).

Designed to be launched as a subprocess by another script:
  - This script's stdout carries the Minecraft server's console output,
    line by line, in realtime, with no ANSI formatting / jline redraw
    codes in it.
  - This script's stdin is forwarded, line by line, straight into the
    Minecraft server's stdin, so commands typed/sent by the wrapping
    process reach the server console.
"""

import pathlib
import os
import re
import sys
import threading
import subprocess

import requests

sysPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
dirPath = sysPath + "/mc/"

# Matches ANSI/CSI escape sequences (colors, cursor movement, etc.).
# Used as a defensive strip in case anything still emits them even with
# jline disabled (see run_server()).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def check_latest_ver() -> tuple[str, str] | None:
    print("Checking new versions", flush=True)
    # Get the list of all Minecraft versions supported by Purpur
    versions_url = "https://api.purpurmc.org/v2/purpur"
    versions_response = requests.get(versions_url).json()
    print("> Fetched latest version info from PurpurMC", flush=True)

    # The last item in the 'versions' array is typically the latest Minecraft version
    latest_mc_version = versions_response["versions"][-1]

    # Get build information for that specific version
    builds_url = f"https://api.purpurmc.org/v2/purpur/{latest_mc_version}"
    builds_response = requests.get(builds_url).json()

    latest_build = builds_response["builds"]["latest"]
    print("> Fetched latest build info from PurpurMC", flush=True)

    if os.path.exists(dirPath + "purpur-" + latest_mc_version + "-" + latest_build + ".jar"):
        print("> Latest server jar already exists.", flush=True)
        return None

    return latest_mc_version, latest_build


def setup_server(latest_mc_version: str, latest_build: str) -> None:
    download_url = f"https://api.purpurmc.org/v2/purpur/{latest_mc_version}/latest/download"
    path = pathlib.Path(dirPath)
    path.mkdir(parents=True, exist_ok=True)

    existing_jar = ""
    mc_files = os.listdir(dirPath)
    for file in mc_files:
        if file.endswith(".jar") and file.startswith("purpur"):
            existing_jar = file

    if existing_jar.split('-')[1] != latest_mc_version:
        print(f"Latest version is a new major version {latest_mc_version}. Do you want to update? (Y/n)")
        r = str(input())
        if r.lower != "y":
            print("Skipping update.")
            return

    if existing_jar != "":
        print("Updating server jar", flush=True)
        os.remove(dirPath + existing_jar)
        print("> Removed old jar", flush=True)
    else:
        print("Setting up server jar", flush=True)
        with open(dirPath + "eula.txt", "w", encoding="utf-8") as f:
            f.write("eula=true")

    print("> Pulling file from PurpurMC's API", flush=True)
    with requests.get(download_url, stream=True) as response:
        response.raise_for_status()  # Check for HTTP errors
        with open(dirPath + "purpur-" + latest_mc_version + "-" + latest_build + ".jar", "wb") as file:
            # Iterates over the data in 8 KB chunks
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)


def _pump_output(proc: subprocess.Popen) -> None:
    """
    Reads the Minecraft server's stdout/stderr line by line and re-emits
    it on THIS script's stdout immediately, so a wrapping process reading
    this script's stdout gets the console in realtime, unformatted.
    """
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        if line == "":
            break
        sys.stdout.write(_ANSI_RE.sub("", line))
        sys.stdout.flush()


def _pump_input(proc: subprocess.Popen) -> None:
    """
    Reads commands from THIS script's stdin (fed by a wrapping process)
    line by line and forwards them straight into the server's stdin.
    """
    assert proc.stdin is not None
    for line in iter(sys.stdin.readline, ""):
        if line == "":
            break
        try:
            proc.stdin.write(line if line.endswith("\n") else line + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            break

    # Wrapping process closed our stdin (no more commands coming) -
    # close the server's stdin too so its console reader isn't left
    # blocking on a pipe that will never receive more input.
    try:
        proc.stdin.close()
    except OSError:
        pass


def run_server(jar_path: str) -> int:
    command = [
        "java",
        "-Xms4096M",
        "-Xmx4096M",
        "-XX:+AlwaysPreTouch",
        "-XX:+DisableExplicitGC",
        "-XX:+ParallelRefProcEnabled",
        "-XX:+PerfDisableSharedMem",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+UseG1GC",
        "-XX:G1HeapRegionSize=8M",
        "-XX:G1HeapWastePercent=5",
        "-XX:G1MaxNewSizePercent=40",
        "-XX:G1MixedGCCountTarget=4",
        "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1NewSizePercent=30",
        "-XX:G1RSetUpdatingPauseTimePercent=5",
        "-XX:G1ReservePercent=20",
        "-XX:InitiatingHeapOccupancyPercent=15",
        "-XX:MaxGCPauseMillis=200",
        "-XX:MaxTenuringThreshold=1",
        "-XX:SurvivorRatio=32",
        "-Dusing.aikars.flags=https://mcflags.emc.gs",
        "-Daikars.new.flags=true",
        "-jar",
        jar_path,
        "--nogui",
        # Disables JLine and makes the server emulate the plain Vanilla
        # console: no ANSI colour/cursor codes, no TAB-completion line
        # redraw hooks. This is what makes the stdout stream safe to
        # parse programmatically instead of only being fit for a real
        # terminal.
        "--nojline",
    ]

    proc = subprocess.Popen(
        command,
        cwd=dirPath,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
        encoding="utf-8",
        errors="replace",
    )

    out_thread = threading.Thread(target=_pump_output, args=(proc,), daemon=True)
    in_thread = threading.Thread(target=_pump_input, args=(proc,), daemon=True)
    out_thread.start()
    in_thread.start()

    exit_code = proc.wait()
    out_thread.join(timeout=5)

    return exit_code


if __name__ == "__main__":
    latest_tuple = check_latest_ver()

    if latest_tuple:
        latest_ver, latest_build = latest_tuple
        setup_server(latest_ver, latest_build)

    existing_jar = ""
    mc_files = os.listdir(dirPath)
    for file in mc_files:
        if file.endswith(".jar") and file.startswith("purpur"):
            existing_jar = file

    print("Running server", flush=True)
    run_server(dirPath + existing_jar)