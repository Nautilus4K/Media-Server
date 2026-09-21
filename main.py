from logger import *
from app import app, start_monitoring, stop_monitoring

import argparse
import waitress
import threading
# import subprocess

parser = argparse.ArgumentParser(prog="Media-Server")
parser.add_argument("-v", "--verbose", action="store_true", help="Console verbose loggings")
parser.add_argument("-t", "--threads", type=int, help="Thread count for this server")
parser.add_argument("-a", "--address", action="store", type=str, help="Address to host the website. Default 127.0.0.1")
parser.add_argument("-p", "--port", action="store", type=int, help="Port to host the website. Default 8000")
# parser.add_argument("-d", "--disk", action="store", type=str, help="Target disk")
args = parser.parse_args()

HOST = args.address if args.address is not None else "127.0.0.1"
PORT = args.port if args.port is not None else 8000
THREADCOUNT = args.threads if args.threads is not None else 4
VERSION = '26.9.19'

console = ConsoleLogger(args.verbose)
if __name__ == "__main__":
    print(f"Media-Server version {VERSION}")

    console.log(f"Started performance monitoring service")
    perf_mon_thread = threading.Thread(target=start_monitoring)
    perf_mon_thread.start()

    console.log(f"Started server at {HOST}:{PORT} using {THREADCOUNT} threads.")

    try:
        waitress.serve(app, host=HOST, port=PORT, threads=THREADCOUNT)
        # subprocess.Popen([
        #     "mod_wsgi-express", "start-server", "app.py",
        #     "--port", str(PORT),
        #     "--host", HOST,
        #     "--threads", str(THREADCOUNT)
        # ])
    except KeyboardInterrupt:
        console.log("Shutting down...")
    finally:
        stop_monitoring()
        perf_mon_thread.join()