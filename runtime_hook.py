"""PyInstaller runtime hook — runs before the main script in frozen builds."""

import multiprocessing
multiprocessing.freeze_support()
