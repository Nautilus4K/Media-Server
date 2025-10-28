# Logging
from logger import *

import os
import argparse

parser = argparse.ArgumentParser(
    prog="Media-Server",
    description="A simple media server for music and movies. Not very lightweight but good enough!",
    epilog="Please do a contribution at Nautilus4K/Media-Server!"
)

parser.add_argument("-v", "--verbose", action="store_true", help="Enable log messages.")
parser.add_argument("directory", help="Surface directory to search. From this directory and going deeper, files are read (recursion).")
parser.add_argument("-d", "--depth", action="store", help="Recursive search depth.")

args = parser.parse_args()

con = ConsoleLogger(args.verbose)

dirname = str(args.directory)
depth_arg = int(args.depth if args.depth else -1)
# if not depth: depth = -1

valid_video_extensions = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
valid_audio_extensions = ['.mp3', '.ogg', '.wav']

def terminate():
    exit(0)

if __name__ == "__main__":
    con.log(f"Initializing directory [blue]{dirname}[/blue] with recursion depth of {"None" if depth_arg == -1 else depth_arg}.")

    if not os.path.exists(dirname):
        con.logerr(f"Given directory of [blue]{dirname}[/blue] DOES NOT EXISTS. Stopping right now...")
        terminate()

    discovered_video_entries = []
    discovered_audio_entries = []

    def discover_paths(d: int, cur_dir: str):
        if d == 0:
            # End of the line
            return

        # print(cur_dir)
        entries = os.listdir(cur_dir)

        for entry in entries:
            full_path = os.path.join(cur_dir, entry)
            name, ext = os.path.splitext(full_path)
            if os.path.isfile(full_path):
                if ext in valid_video_extensions:
                    discovered_video_entries.append(full_path)
                    con.log(f"VIDEO > [blue]{full_path}[/blue]")
                elif ext in valid_audio_extensions:
                    discovered_audio_entries.append(full_path)
                    con.log(f"AUDIO > [blue]{full_path}[/blue]")
            else:
                discover_paths(d - 1, full_path)

    con.log("Beginning recursive discovery.")
    discover_paths(depth_arg, dirname)
    con.logok(f"Successfully indexed entries with {len(discovered_video_entries)} video files and {len(discovered_audio_entries)} audio files.")
