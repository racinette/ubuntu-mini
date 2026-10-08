#!/usr/bin/env python3
"""VM-only X11 keyboard/clipboard fixture; Ctrl+S saves the actual entry text."""
import json
from pathlib import Path
import tkinter as tk

root = tk.Tk(className='MiniOSXwayland')
root.title('Mini OS Xwayland test')
tk.Label(root, text='X11 entry: type, paste, then Ctrl+S to save').pack()
entry = tk.Entry(root, font=('DejaVu Sans', 20), width=40)
entry.pack()
entry.focus_set()
entry.bind('<Control-a>', lambda event: (entry.selection_range(0, tk.END), 'break')[-1])
entry.bind('<Control-c>', lambda event: (entry.event_generate('<<Copy>>'), 'break')[-1])
entry.bind('<Control-v>', lambda event: (entry.event_generate('<<Paste>>'), 'break')[-1])
def save(event=None):
    Path.home().joinpath('mini-os-xwayland-result.json').write_text(
        json.dumps({'text': entry.get()}, ensure_ascii=False) + '\n')
root.bind('<Control-s>', save)
root.mainloop()
