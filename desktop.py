#!/usr/bin/env python3
"""
FNIRSI FNB58 Monitor - macOS desktop launcher

Runs the Flask/Socket.IO server on a loopback port and shows the dashboard in a
native window (WKWebView via pywebview). Quitting saves any recording in
progress and releases the meter. Packaged into "FNB58 Monitor.app" by
macos/build_app.sh; `python desktop.py` runs the same thing unbundled.
"""

import html
import logging
import logging.handlers
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = 'FNB58 Monitor'
HOST = '127.0.0.1'
PREFERRED_PORT = 5001  # stable origin keeps the dashboard's localStorage settings
DATA_DIR = Path.home() / 'Library' / 'Application Support' / APP_NAME
LOG_FILE = Path.home() / 'Library' / 'Logs' / APP_NAME / 'monitor.log'
BACKGROUND = '#0a0c10'  # --bg-primary in professional.css; avoids a white flash

log = logging.getLogger('fnb58.desktop')


# ==================== Setup ====================

def configure_logging():
    """Log to ~/Library/Logs (a Finder-launched app has no visible console)."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=2)]
    if sys.stderr is not None and sys.stderr.isatty():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'), handlers=handlers,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)  # per-request lines, dev-server banner


def configure_environment():
    """Point config.py at per-user data dirs. Must run before `app` is imported."""
    os.environ.setdefault('FLASK_CONFIG', 'production')
    os.environ.setdefault('SESSION_DIR', str(DATA_DIR / 'sessions'))
    os.environ.setdefault('EXPORT_DIR', str(DATA_DIR / 'exports'))
    os.environ.setdefault('SECRET_KEY', secrets.token_hex(32))


def pick_port():
    """PREFERRED_PORT if it is free on loopback, else any free port."""
    for port in (PREFERRED_PORT, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
            except OSError:
                continue
            return s.getsockname()[1]
    raise RuntimeError('No free TCP port on loopback')


# ==================== Server ====================

def start_server(server, port, timeout=20.0):
    """Run the Socket.IO server on a daemon thread and wait until it answers."""
    thread = threading.Thread(
        target=server.socketio.run, name='flask-server', daemon=True,
        args=(server.app,),
        kwargs={'host': HOST, 'port': port, 'debug': False, 'use_reloader': False,
                'log_output': False, 'allow_unsafe_werkzeug': True})
    thread.start()

    status_url = f'http://{HOST}:{port}/api/status'
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not thread.is_alive():
            raise RuntimeError('Server thread exited during startup')
        try:
            with urllib.request.urlopen(status_url, timeout=1):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    raise RuntimeError(f'Server did not answer on {status_url} within {timeout:.0f} s')


# ==================== Window ====================

def build_menu(url):
    """Extra menu-bar items for things the web UI can't do on its own."""
    from webview.menu import Menu, MenuAction, MenuSeparator

    def finder(*args):
        subprocess.run(['/usr/bin/open', *map(str, args)], check=False)

    return [Menu('Monitor', [
        MenuAction('Open Dashboard in Browser', lambda: webbrowser.open(url)),
        MenuSeparator(),
        MenuAction('Show Sessions in Finder', lambda: finder(os.environ['SESSION_DIR'])),
        MenuAction('Show Log in Finder', lambda: finder('-R', LOG_FILE)),
    ])]


def error_page(message):
    return f"""<body style="background:{BACKGROUND};color:#e8eaed;font:15px -apple-system;padding:40px">
<h2>{APP_NAME} could not start</h2><p>{html.escape(str(message))}</p>
<p style="color:#9aa0a6">Details are in {LOG_FILE}</p></body>"""


def main():
    configure_logging()
    configure_environment()
    import webview
    webview.settings['ALLOW_DOWNLOADS'] = True  # CSV / report exports open a save panel

    window_args = {'width': 1440, 'height': 900, 'min_size': (1000, 650),
                   'background_color': BACKGROUND}
    try:
        import app as server
        port = pick_port()
        start_server(server, port)
    except Exception as e:  # noqa: BLE001 - shown to the user instead of a silent exit
        log.exception('Startup failed')
        webview.create_window(APP_NAME, html=error_page(e), **window_args)
        webview.start()
        return

    url = f'http://{HOST}:{port}/'
    log.info('%s serving %s (data in %s)', APP_NAME, url, DATA_DIR)

    def on_closing():
        # Runs synchronously for both the close button and Cmd+Q; Cmd+Q never
        # returns from webview.start(), so cleanup cannot wait until after it.
        try:
            saved = server.shutdown()
            if saved:
                log.info('Recording saved on quit: %s', saved)
        except Exception:  # noqa: BLE001 - never block quitting
            log.exception('Shutdown cleanup failed')

    window = webview.create_window(APP_NAME, url, **window_args)
    window.events.closing += on_closing
    webview.start(debug=bool(os.environ.get('FNB58_DEBUG')), private_mode=False,
                  menu=build_menu(url))

    logging.shutdown()
    os._exit(0)  # server, USB and BLE threads are daemons; don't wait on them


if __name__ == '__main__':
    main()
