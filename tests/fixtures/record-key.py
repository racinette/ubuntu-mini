"""VM fixture: record the bytes Foot emits for one key combination."""
import json
from pathlib import Path
import select
import sys
import termios
import tty

fd = sys.stdin.fileno()
previous = termios.tcgetattr(fd)
try:
    tty.setraw(fd)
    if not select.select([fd], [], [], 300)[0]: raise TimeoutError('No key received')
    data = __import__('os').read(fd, 256)
    Path.home().joinpath('mini-os-key-bytes.json').write_text(json.dumps(list(data)) + '\n')
finally:
    termios.tcsetattr(fd, termios.TCSANOW, previous)
