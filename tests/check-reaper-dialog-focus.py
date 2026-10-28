#!/usr/bin/python3
"""Guard dialog highlights against stale data, wrong windows and hidden controls."""
import os
from pathlib import Path
import runpy
import tempfile
import time
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
focus = runpy.run_path(str(ROOT / 'setup/development/reaper-control-outline.py'))['dialog_focus']
with tempfile.TemporaryDirectory() as tmp:
    state = Path(tmp) / 'outline'
    sample = Path(str(state) + '.native-focus')
    mode = Path(tmp) / 'mode'
    mode.write_text('reaper\n')
    outline = Mock(pid=42)
    outline.owner.return_value = 42
    outline.viewable.return_value = True
    outline.geometry.return_value = (100, 50, 400, 300)
    node = dict(pid=42, window=80, focused=True, name='Add FX to Track 1',
                window_properties={'transient_for':70, 'window_type':'normal'})
    def check(text, expected):
        sample.write_text(text)
        assert focus(outline, [node], state) == expected
    hidden = (True, None, None)
    check('80 120 70 100 30', (True, (120, 70, 100, 30), 80))
    # The modal native record remains valid even when the Lua state is old.
    state.write_text('stale project selection')
    os.utime(state, (1, 1))
    check('80 120 70 100 30', (True, (120, 70, 100, 30), 80))
    check('70 120 70 100 30', hidden)  # Main window's focus cannot outline a dialog.
    check('80 90 40 600 500', (True, (103, 53, 394, 294), 80))
    for value in ('', 'truncated', '80 500 70 100 30', '80 120 70 0 30', '80 120 70 100000 30'):
        check(value, hidden)
    sample.unlink()
    assert focus(outline, [node], state) == hidden
    sample.write_text('80 120 70 100 30')
    os.utime(sample, (time.time()-2, time.time()-2))
    assert focus(outline, [node], state) == hidden
    sample.write_text('80 120 70 100 30')
    outline.owner.return_value = 99
    assert focus(outline, [node], state) == hidden
    outline.owner.return_value = 42
    outline.viewable.return_value = False
    assert focus(outline, [node], state) == hidden
    outline.viewable.return_value = True
    mode.write_text('desktop\n')
    assert focus(outline, [node], state) == hidden
    mode.write_text('reaper\n')
    for title in ('FX: Track 1', 'VST3: ReaEQ', 'REAPER gamepad controls'):
        assert focus(outline, [dict(node, name=title)], state) == (False, None, None)
    for updates in ({'pid':99}, {'focused':False}, {'window_properties':{}}):
        assert focus(outline, [dict(node, **updates)], state) == (False, None, None)
    assert focus(outline, [dict(node, window_properties={'window_type':'dialog'})], state)[0]
print('Passed: native dialog focus identity, freshness, mode, visibility, clipping and modal Lua independence.')
