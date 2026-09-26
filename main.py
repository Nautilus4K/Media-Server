from logger import *
from app import *
from ssl_manager import SSLManager

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
parser.add_argument("-s", "--ssl", action="store_true", help="Serve over HTTPS using an auto-renewing Let's Encrypt certificate")
parser.add_argument("--domain", action="store", type=str, default="nautilus4k.ddns.net", help="Domain name to request the SSL certificate for")
parser.add_argument("--email", action="store", type=str, help="Contact email for Let's Encrypt account (required with --ssl)")
parser.add_argument("--staging", action="store_true", help="Use Let's Encrypt's staging environment (for testing, avoids rate limits)")
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
                    new_passwd = str(getpass.getpass("Password: "))
                    confirm_passwd = str(getpass.getpass("Confirm Password: "))

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

        console.log(f"Started Minecraft server manager service")
        mc_sv_manager_thread = threading.Thread(target=start_server_manager)
        mc_sv_manager_thread.start()

        ssl_manager = None
        if args.ssl:
            if not args.email:
                parser.error("--email is required when --ssl is enabled (Let's Encrypt requires a contact email).")

            ssl_manager = SSLManager(domain=args.domain, email=args.email, staging=args.staging)

            console.log(f"[SSL] Ensuring certificate for {args.domain} before starting server...")
            ssl_manager.ensure_certificate()

            # Daily 12:00 AM renewal check, with automatic catch-up on
            # startup if a scheduled check was missed (reboot/power loss).
            ssl_manager.start()

        console.log(f"Started server at {HOST}:{PORT} using {THREADCOUNT} threads. "
                    f"(HTTPS: {'on, domain=' + args.domain if args.ssl else 'off'})")

        try:
            if args.ssl:
                # waitress has no built-in TLS support, so HTTPS is served
                # with cheroot instead, using the cert/key certbot manages.
                from cheroot.wsgi import Server as WSGIServer
                from cheroot.ssl.builtin import BuiltinSSLAdapter

                server = WSGIServer((HOST, PORT), app, numthreads=THREADCOUNT)
                server.ssl_adapter = BuiltinSSLAdapter(
                    certificate=ssl_manager.cert_path, # pyright: ignore[reportOptionalMemberAccess]
                    private_key=ssl_manager.key_path, # pyright: ignore[reportOptionalMemberAccess]
                )
                try:
                    server.start()
                except KeyboardInterrupt:
                    console.log("Shutting down...")
                    server.stop()
            else:
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
            if ssl_manager:
                ssl_manager.stop()
            stop_monitoring()
            stop_server_manager()
            perf_mon_thread.join()
            mc_sv_manager_thread.join()