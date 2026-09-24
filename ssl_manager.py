"""
SSL certificate management for Media-Server.

Obtains and automatically renews a Let's Encrypt certificate for the
configured domain using certbot's "standalone" (HTTP-01) authenticator,
and runs a background scheduler that checks daily at 12:00 AM.

If a scheduled check is missed (process was down / machine rebooted or
lost power over the check window), the scheduler detects this on the
next startup via the persisted `ssl_state.json` timestamp and runs a
catch-up check immediately, rather than waiting for the next midnight.

Requires certbot to be installed and available on PATH.
"""

import datetime
import json
import os
import shutil
import ssl
import subprocess
import threading
import time

from logger import ConsoleLogger

console = ConsoleLogger(True)

# --- Configuration -----------------------------------------------------

SYS_PATH = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
STATE_FILE = SYS_PATH + "/ssl_state.json"

# certbot is told to keep all its state under our own project folder
# (rather than the system-wide /etc/letsencrypt) so the app is
# self-contained and doesn't need root-owned system paths.
CERTBOT_CONFIG_DIR = SYS_PATH + "/letsencrypt/config"
CERTBOT_WORK_DIR = SYS_PATH + "/letsencrypt/work"
CERTBOT_LOGS_DIR = SYS_PATH + "/letsencrypt/logs"

RENEWAL_HOUR = 0    # 12:00 AM
RENEWAL_MINUTE = 0
CATCHUP_WINDOW = datetime.timedelta(hours=24)


class SSLManager:
    def __init__(self, domain, email, staging=False):
        self.domain = domain
        self.email = email
        self.staging = staging
        self._stop_event = threading.Event()
        self._thread = None

        os.makedirs(CERTBOT_CONFIG_DIR, exist_ok=True)
        os.makedirs(CERTBOT_WORK_DIR, exist_ok=True)
        os.makedirs(CERTBOT_LOGS_DIR, exist_ok=True)

    # -- cert paths ---------------------------------------------------
    @property
    def live_dir(self):
        return f"{CERTBOT_CONFIG_DIR}/live/{self.domain}"

    @property
    def cert_path(self):
        return f"{self.live_dir}/fullchain.pem"

    @property
    def key_path(self):
        return f"{self.live_dir}/privkey.pem"

    def certs_exist(self):
        return os.path.isfile(self.cert_path) and os.path.isfile(self.key_path)

    # -- certbot invocation --------------------------------------------
    @staticmethod
    def _require_certbot():
        if shutil.which("certbot") is None:
            raise RuntimeError(
                "certbot was not found on PATH. Install it first, e.g. "
                "'sudo apt install certbot' on Debian/Ubuntu, or see "
                "https://certbot.eff.org for other platforms."
            )

    def obtain_certificate(self):
        self._require_certbot()
        console.log(f"[SSL] Requesting a new certificate for {self.domain} "
                    f"via certbot (standalone, port 80)...")
        args = [
            "certbot", "certonly",
            "--standalone",
            "--non-interactive",
            "--agree-tos",
            "--email", self.email,
            "-d", self.domain,
            "--config-dir", CERTBOT_CONFIG_DIR,
            "--work-dir", CERTBOT_WORK_DIR,
            "--logs-dir", CERTBOT_LOGS_DIR,
            "--http-01-port", "80",
        ]
        if self.staging:
            args.append("--staging")

        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            console.log(f"[SSL] certbot failed:\n{result.stdout}\n{result.stderr}")
            raise RuntimeError("certbot failed to obtain a certificate (see log above). "
                                "Check that port 80 is forwarded to this machine and that "
                                f"{self.domain} resolves to this machine's public IP.")
        console.log(f"[SSL] Certificate obtained for {self.domain}.")

    def renew_if_needed(self):
        """
        `certbot renew` only actually renews certs within its renewal
        window (default: 30 days of expiry), so it's safe to call this
        every day - most days it will be a no-op.
        """
        self._require_certbot()
        console.log("[SSL] Running certbot renewal check...")
        args = [
            "certbot", "renew",
            "--standalone",
            "--non-interactive",
            "--http-01-port", "80",
            "--config-dir", CERTBOT_CONFIG_DIR,
            "--work-dir", CERTBOT_WORK_DIR,
            "--logs-dir", CERTBOT_LOGS_DIR,
        ]
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            console.log(f"[SSL] certbot renew reported an error:\n{result.stdout}\n{result.stderr}")
        else:
            last_line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            console.log(f"[SSL] Renewal check complete. {last_line}")

    def ensure_certificate(self):
        """Obtain a first certificate if none exists yet, otherwise renew-if-needed."""
        if not self.certs_exist():
            self.obtain_certificate()
        else:
            self.renew_if_needed()

    def build_ssl_context(self):
        if not self.certs_exist():
            raise RuntimeError("No certificate available yet; call ensure_certificate() first.")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=self.cert_path, keyfile=self.key_path)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    # -- state persistence (drives the catch-up logic) ------------------
    @staticmethod
    def _load_state():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _save_state(state):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)

    # -- scheduling -------------------------------------------------------
    @staticmethod
    def _seconds_until_next_run():
        now = datetime.datetime.now()
        target = now.replace(hour=RENEWAL_HOUR, minute=RENEWAL_MINUTE, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return (target - now).total_seconds()

    def _run_check(self):
        try:
            self.ensure_certificate()
        except Exception as e:
            console.log(f"[SSL] Renewal check failed: {e}")
        finally:
            state = self._load_state()
            state["last_check"] = datetime.datetime.now().isoformat()
            self._save_state(state)

    def _loop(self):
        # Catch-up: if we don't have a record of a check in the last 24h
        # (first run ever, or the process was down over a scheduled
        # midnight check due to reboot/power loss), run one right now
        # instead of waiting for the next midnight.
        state = self._load_state()
        last_check = state.get("last_check")
        missed = True
        if last_check:
            try:
                last_dt = datetime.datetime.fromisoformat(last_check)
                missed = (datetime.datetime.now() - last_dt) > CATCHUP_WINDOW
            except ValueError:
                missed = True

        if missed:
            console.log("[SSL] No renewal check recorded in the last 24h "
                        "(first run, reboot, or downtime) - checking now.")
        self._run_check()

        while not self._stop_event.is_set():
            wait_s = self._seconds_until_next_run()
            console.log(f"[SSL] Next scheduled renewal check in {wait_s / 3600:.1f}h (12:00 AM).")
            # Sleep in short increments rather than one long sleep so
            # stop() and DST/clock changes are handled promptly.
            interval = 60
            waited = 0
            while waited < wait_s and not self._stop_event.is_set():
                time.sleep(min(interval, wait_s - waited))
                waited += interval
            if self._stop_event.is_set():
                break
            self._run_check()

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ssl-renewal")
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)