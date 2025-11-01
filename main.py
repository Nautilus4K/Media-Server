# Logging
from logger import *

import os
import time
import argparse
import traceback
import mimetypes
import json
import hashlib
import tinytag
import unicodedata
# import socket

# WSGI app
import waitress

parser = argparse.ArgumentParser(
    prog="Media-Server",
    description="A simple media server for music and movies made by Nautilus4K (a.k.a Quang Vinh). Not very lightweight but good enough!",
    epilog="Please do a contribution at Nautilus4K/Media-Server!"
)

parser.add_argument("-v", "--verbose", action="store_true", help="Enable log messages.")
parser.add_argument("directory", help="Surface directory to search. From this directory and going deeper, files are read (recursion).")
parser.add_argument("-d", "--depth", action="store", help="Recursive search depth.")

args = parser.parse_args()

dirPath = os.path.dirname(os.path.abspath(__file__))

con = ConsoleLogger(args.verbose)

dirname = str(args.directory)
depth_arg = int(args.depth if args.depth else -1)
# if not depth: depth = -1

valid_video_extensions = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
valid_audio_extensions = ['.mp3', '.ogg', '.wav']

HOST = "0.0.0.0"
PORT = 8000
VERSION = '31.10.25'

def terminate():
    exit(0)

def normalize_to_ascii(text: str) -> str:
    # Normalize to decomposed form (separate base char + accent)
    normalized = unicodedata.normalize('NFKD', text)
    # Encode to ASCII, ignore non-ASCII bytes (accents etc.)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return ascii_text

HASH_LENGTH = 8
def gen_id(file_unique_name):
    # return os.path.basename(os.path.abspath(file_unique_name)) + hashlib.sha256(file_unique_name.encode('utf-8')).hexdigest()[:HASH_LENGTH]
    hashed = hashlib.sha256(file_unique_name.encode('utf-8')).hexdigest()[:HASH_LENGTH]
    name, ext = os.path.splitext(os.path.basename(os.path.abspath(file_unique_name)))

    return normalize_to_ascii(name).replace(" ", "") + "-" + hashed

audio_entries = {}
video_entries = {}
safely_named = True
video_structure = {}
redact_file_path = True

# WSGI Interface area
# This is web app territory
# I have no goddamn clue on how should I factor this but it is really depressing to use
WEBROOT_PATH = dirPath + "/www"
INDEX_PATH = WEBROOT_PATH + "/index.html"

PLACEHOLDER_PREFIX = "%%"
PLACEHOLDER_SUFFIX = "%%"
PLACEHOLDER_DICTIONARY = { # This shouldnt have been required. Fucking shit.
    'ip_addr': '?',
    'webname': 'Orestia'
}

def api_requests(path) -> tuple[str, str]:
    status = '200 OK'
    return_data = {}

    return_data['api_version'] = VERSION
    return_data['path'] = path

    if path == "/api/music_list" or path == "/api/music_list/":
        # Good grief
        # We gotta get all the musics sorted out now
        id_list = []
        for _id in audio_entries:
            id_list.append(_id)
        
        return_data["result"] = id_list
    elif path.startswith("/api/get_music_data"):
        song_id = os.path.basename(path)
        if song_id == "get_music_data":
            return_data["msg"] = "Missing ID."
            status = "400 Bad Request"
        else:
            # Let's go
            if song_id not in audio_entries:
                # Fuck
                return_data["msg"] = "No song with given ID."
                status = "404 Not Found"
            else:
                return_data["result"] = audio_entries[song_id]

                # Remove the sensitive part: File path
                if redact_file_path: return_data["result"]["path"] = "REDACTED"

    return json.dumps(return_data), status

def webapplication(environ, start_response):
    """
    WSGI application.
    """
    status = '200 OK'
    headers = [('Content-type', 'text/plain; charset=utf-8')]

    method = environ['REQUEST_METHOD']
    path = environ['PATH_INFO']
    query = environ['QUERY_STRING']

    con.log(f"[green]{environ["REMOTE_ADDR"]}[/green] --> [blue]{path}[/blue]")

    if path == "/debug":
        return_string = f"Method: {method}\nPath: {path}\nQuery: {query}"
    elif path == "/":
        # Application root here.
        headers = [('Content-type', 'text/html; charset=utf-8')]
        with open(INDEX_PATH, "r", encoding='utf-8') as f:
            return_string = f.read()

            for item in PLACEHOLDER_DICTIONARY:
                return_string = return_string.replace(
                    PLACEHOLDER_PREFIX + item + PLACEHOLDER_SUFFIX, 
                    PLACEHOLDER_DICTIONARY[item]
                )
    elif path.startswith("/api/") or path == "/api":
        headers = [('Content-type', 'application/json; charset=utf-8')]
        return_string, status = api_requests(path)
    else:
        # Serve other files from WEBROOT_PATH
        full_path = os.path.join(WEBROOT_PATH, path.lstrip("/"))
        
        if not os.path.isfile(full_path):
            # File not found
            headers = [('Content-type', 'text/plain; charset=utf-8')]
            status = '404 Not Found'
            return_string = "404 Not Found"
        else:
            # Detect MIME type automatically
            mime_type, _ = mimetypes.guess_type(full_path)
            if mime_type is None:
                mime_type = "application/octet-stream"

            headers = [('Content-type', mime_type)]

            # Open as binary if not text
            if mime_type.startswith("text/") or mime_type in ("application/javascript", "application/json"):
                with open(full_path, "r", encoding="utf-8") as f:
                    return_string = f.read()
            else:
                with open(full_path, "rb") as f:
                    return_string = f.read()

    start_response(status, headers)
    return [return_string.encode('utf-8')]


# Main area of code
if __name__ == "__main__":
    con.logok("Started media server. Thank you for choosing this shitty ass software!!!")
    con.log("")
    # con.log("")
    con.log(f"Initializing directory [blue]{dirname}[/blue] with recursion depth of {"None" if depth_arg == -1 else depth_arg}.")

    if not os.path.exists(dirname):
        con.logerr(f"Given directory of [blue]{dirname}[/blue] DOES NOT EXISTS. Stopping right now...")
        terminate()

    discovered_video_entries = []
    discovered_audio_entries = []

    def discover_paths(d: int, cur_dir: str):
        global safely_named, discovered_video_entries, discovered_audio_entries

        if d == 0:
            # End of the line
            return

        # print(cur_dir)
        try:
            entries = os.listdir(cur_dir)
        except Exception as e:
            con.logerr(f"Failure to list directory [blue]{cur_dir}[/blue] with error [red]{e}[/red]")
            return

        for entry in entries:
            full_path = os.path.join(cur_dir, entry)
            name, ext = os.path.splitext(full_path)
            if os.path.isfile(full_path):
                if ext in valid_video_extensions:
                    discovered_video_entries.append(full_path)
                    con.log(f"VIDEO > [blue]{full_path}[/blue]")

                    if not name.isascii(): safely_named = False
                elif ext in valid_audio_extensions:
                    discovered_audio_entries.append(full_path)
                    con.log(f"AUDIO > [blue]{full_path}[/blue]")

                    if not name.isascii(): safely_named = False
            else:
                if not os.path.islink(full_path): discover_paths(d - 1, full_path)

    con.log("Beginning recursive discovery.")
    discovertime_begin = time.time()
    
    try:
        discover_paths(depth_arg, dirname)
    except Exception as e:
        con.logerr("Error discovering media files:")
        traceback.print_exc()

    discovertime_total = time.time() - discovertime_begin
    con.logok(f"Successfully indexed entries with {len(discovered_video_entries)} video files and {len(discovered_audio_entries)} audio files in {discovertime_total} seconds.")

    if not safely_named:
        con.logwarn("Files are [bold red]NOT[/bold red] safely named (not entirely ASCII characters). This may cause some problems later on or problems with certain filesystems. [italic]Be aware[/italic] of the risks.")

    # It wouldn't hurt to cache this first
    for entry in discovered_audio_entries:
        _id = gen_id(entry)
        audio_entries[_id] = {}
        audio_entries[_id]["path"] = entry
        
        try:
            tag = tinytag.TinyTag.get(entry)

            audio_entries[_id]["title"] = tag.title
            audio_entries[_id]["artist"] = tag.artist
            audio_entries[_id]["album"] = tag.album
            audio_entries[_id]["genre"] = tag.genre
            audio_entries[_id]["year"] = tag.year
            audio_entries[_id]["duration"] = tag.duration
            audio_entries[_id]["bitrate"] = tag.bitrate
        except Exception as e:
            con.logerr(f"Error while loading tag of file {entry}")
            traceback.print_exc()


    con.logok("Generated unique identifiers for music files.")

    # With all that bs done. Its time for us to try making this into a dict
    # In that dict, we will have to create key : value pairs that represents folders and each of its contents (this is for videos only)
    # Should work I guess.
    # path_cache = {}

    for entry in discovered_video_entries:
        # Each of these are video entries (yes they are files with paths. Thank you!)
        dir_entry = os.path.dirname(entry)
        nickname_entry = os.path.basename(dir_entry)

        if nickname_entry in video_structure:
            # if path_cache[nickname_entry]
            # I cant be bothered to care if this folder has the same name but different path like come on dude its just fuck it bro.
            video_structure[nickname_entry].append(entry)
        else:
            # Entry isnt in video structure???
            # Ugh! This is bad. Gotta make a new one
            video_structure[nickname_entry] = [entry]

    con.logok("Refactored video files into a structure:")
    console.print_json(json.dumps(video_structure))

    con.log(f"Started web server on http://{HOST}:{PORT}/")
    waitress.serve(webapplication, host=HOST, port=PORT)