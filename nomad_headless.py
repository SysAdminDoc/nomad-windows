"""
N.O.M.A.D. Headless Server — Docker/CLI mode without desktop GUI.
Runs Flask on 0.0.0.0:8080 with full API access.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger('nomad.headless')

# Set headless flag before imports
os.environ['NOMAD_HEADLESS'] = '1'

# Set data directory from environment
data_dir = os.environ.get('NOMAD_DATA_DIR', '')
if data_dir:
    os.makedirs(data_dir, exist_ok=True)
    # Write config to point to the data directory
    from config import save_config
    save_config({'data_dir': data_dir})

# Bootstrap dependencies
def _bootstrap():
    if getattr(sys, 'frozen', False):
        return
    deps = ['flask', 'requests', 'PIL', 'psutil']
    pkg_names = {'PIL': 'pillow'}
    for dep in deps:
        try:
            __import__(dep)
        except ImportError:
            import subprocess
            pkg = pkg_names.get(dep, dep)
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

_bootstrap()

from db import init_db, log_activity
from web.app import create_app

VERSION = '1.0.0'
PORT = int(os.environ.get('NOMAD_PORT', 8080))


def main():
    log.info(f'N.O.M.A.D. Headless Server v{VERSION}')
    log.info(f'Data directory: {os.environ.get("NOMAD_DATA_DIR", "default")}')
    log.info(f'Listening on 0.0.0.0:{PORT}')

    init_db()
    log_activity('headless_started', detail=f'v{VERSION} on port {PORT}')

    from web.app import set_version
    set_version(VERSION)
    app = create_app()

    # Run Flask directly (no pywebview, no tray)
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
