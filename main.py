from logger import *
from app import app, start_monitoring, stop_monitoring, VERSION

import argparse
import waitress
import threading
import os
import json
import bcrypt
import getpass
# import subprocess

parser = argparse.ArgumentParser(prog="Media-Server")
# parser.add_argument("-v", "--verbose", action="store_true", help="Console verbose loggings")
parser.add_argument("-t", "--threads", type=int, help="Thread count for this server")
parser.add_argument("-a", "--address", action="store", type=str, help="Address to host the website. Default 127.0.0.1")
parser.add_argument("-p", "--port", action="store", type=int, help="Port to host the website. Default 8000")
parser.add_argument("-u", "--users", action="store_true", help="Edit users settings")
# parser.add_argument("-d", "--disk", action="store", type=str, help="Target disk")
args = parser.parse_args()

HOST = args.address if args.address is not None else "127.0.0.1"
PORT = args.port if args.port is not None else 8000
THREADCOUNT = args.threads if args.threads is not None else 4
USERSEDITMODE = args.users

sysPath = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

console = ConsoleLogger(True)
if __name__ == "__main__":
    print(f"Media-Server version {VERSION}")

    if USERSEDITMODE:
        print("[!] USERS EDIT MODE ENABLED [!]")
        users = json.load(open(sysPath + "/users.json", "r", encoding='utf-8'))

        while True:
            print("[!] REGISTERED USERS [!]")
            for username in users:
                print(username)
                print("- Password Hash: " + users[username]["passwd"])

            print("")
            cmd = str(input("Enter action ([A]dd user/Edit user, [D]elete user, E[X]it): ")).lower()
            if cmd == "a":
                new_user = str(input("Username: "))

                while True:
                    new_passwd = str(getpass.getpass("Password: ", echo_char="*"))
                    confirm_passwd = str(getpass.getpass("Confirm Password: ", echo_char="*"))

                    if new_passwd == confirm_passwd: break
                    else: print("Passwords don't match!")

                salt = bcrypt.gensalt()
                new_passwd_hash = bcrypt.hashpw(new_passwd.encode('utf-8'), salt=salt)
                print("> Hashed password: " + new_passwd_hash.decode('utf-8'))

                users[new_user] = {
                    "passwd": new_passwd_hash.decode('utf-8')
                }
            elif cmd == "d":
                target_user = str(input("Username"))
                users.pop(target_user)
            elif cmd == "x":
                break

        json.dump(users, open(sysPath + "/users.json", "w", encoding='utf-8'))

    else:
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