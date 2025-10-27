# Logging
from logger import *

import os
import argparse

parser = argparse.ArgumentParser(
    prog="Media-Server",
    description="A simple media server for music and movies. Not very lightweight but good enough!",
    epilog="Please do a contribution at [link=https://github.com/Nautilus4K/Media-Server]Nautilus4K/Media-Server[/link]!"
)

parser.add_argument("-v", "--verbose", action="store_true")
parser.add_argument("directory")
parser.add_argument("-d", "--depth", action="store")

args = parser.parse_args()

con = ConsoleLogger(args.verbose)

dirname = str(args.directory)
depth = int(args.depth if args.depth else -1)
# if not depth: depth = -1

if __name__ == "__main__":
    con.logok(f"Initializing directory {dirname} with recursion depth of {"None" if depth == -1 else depth}.")