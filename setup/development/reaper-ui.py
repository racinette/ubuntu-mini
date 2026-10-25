"""Locate native REAPER buttons from the current theme's exact rendered images.

Runs in the existing outline process. Captures only the reported native panels;
matching never moves/clicks the pointer and rejects ambiguous/hidden buttons.
"""
import collections
import configparser
import ctypes as C
import json
from pathlib import Path
import time
import zipfile

BUTTONS = {
    'Toolbar': (
        (40023,'New project',('toolbar_new',)), (40025,'Open project',('toolbar_load',)),
        (40026,'Save project',('toolbar_save',)), (40021,'Project settings',('toolbar_projprop',)),
        (40029,'Undo',('toolbar_undo',)), (40030,'Redo',('toolbar_redo',)),
        (40364,'Metronome',('toolbar_metro','toolbar_metro_on','toolbar_metro_off')),
        (40041,'Auto-crossfade',('toolbar_xfade_on','toolbar_xfade_off')),
        (1155,'Ripple editing',('toolbar_ripple_off','toolbar_ripple_one','toolbar_ripple_all')),
        (1156,'Grouping',('toolbar_group_on','toolbar_group_off')),
        (40145,'Grid',('toolbar_grid_on','toolbar_grid_off')),
        (1157,'Snapping',('toolbar_snap_on','toolbar_snap_off')),
        (1135,'Locking',('toolbar_lock_on','toolbar_lock_off')),
    ),
    'Transport': (
        (40042,'Go to start',('transport_home',)), (40043,'Go to end',('transport_end',)),
        (1016,'Stop',('transport_stop',)), (1007,'Play',('transport_play','transport_play_on','transport_play_sync','transport_play_sync_on')),
        (1008,'Pause',('transport_pause','transport_pause_on')), (1013,'Record',('transport_record','transport_record_on')),
        (1068,'Repeat',('transport_repeat_off','transport_repeat_on')),
    ),
}


class PNGImage(C.Structure):
    _fields_ = [('opaque',C.c_void_p),('version',C.c_uint32),('width',C.c_uint32),('height',C.c_uint32),
                ('format',C.c_uint32),('flags',C.c_uint32),('colormap_entries',C.c_uint32),
                ('warning_or_error',C.c_uint32),('message',C.c_char*64)]


def decode_png(data):
    png = C.CDLL('libpng16.so.16')
    png.png_image_begin_read_from_memory.argtypes = [C.POINTER(PNGImage),C.c_void_p,C.c_size_t]
    png.png_image_finish_read.argtypes = [C.POINTER(PNGImage),C.c_void_p,C.c_void_p,C.c_int32,C.c_void_p]
    png.png_image_free.argtypes = [C.POINTER(PNGImage)]
    image = PNGImage(); image.version = 1
    source = C.create_string_buffer(data)
    if not png.png_image_begin_read_from_memory(C.byref(image),source,len(data)):
        raise ValueError('Invalid theme image')
    try:
        if image.width * image.height > 4_000_000:
            raise ValueError('Theme image too large')
        image.format = 3 # RGBA, including indexed PNG themes.
        pixels = C.create_string_buffer(image.width*image.height*4)
        if not png.png_image_finish_read(C.byref(image),None,pixels,0,None):
            raise ValueError('Cannot decode theme image')
        return image.width,image.height,pixels.raw
    finally:
        png.png_image_free(C.byref(image))


def find_image(image, template):
    width,height,pixels = image
    tw,th,source = template
    if tw > width or th > height:
        return []
    points = [(x,y,source[(y*tw+x)*4:(y*tw+x)*4+4]) for y in range(th) for x in range(tw)
              if source[(y*tw+x)*4+3] == 255 and source[(y*tw+x)*4:(y*tw+x)*4+3] != b'\xff\0\xff']
    if len(points) < 8:
        return []
    counts = collections.Counter(p[2] for p in points)
    ax,ay,color = min(points,key=lambda p:counts[p[2]])
    matches,offset = [],0
    while True:
        position = pixels.find(color,offset)
        if position < 0:
            break
        offset = position+1
        if position % 4:
            continue
        sx,sy = position//4 % width-ax,position//4//width-ay
        if sx < 0 or sy < 0 or sx+tw > width or sy+th > height:
            continue
        if all(pixels[((sy+y)*width+sx+x)*4:((sy+y)*width+sx+x)*4+4] == c for x,y,c in points):
            matches.append((sx,sy,tw,th))
    return matches


_templates = {}
_retry_after = 0


def detect(outline, request):
    theme = Path(request['theme'])
    stamp = (str(theme),theme.stat().st_mtime_ns)
    if stamp not in _templates:
        with zipfile.ZipFile(theme) as archive:
            wanted = {icon for entries in BUTTONS.values() for _,_,icons in entries for icon in icons}
            templates = {}
            for name in archive.namelist():
                icon = Path(name).stem
                if name.endswith('.png') and icon in wanted:
                    w,h,pixels = decode_png(archive.read(name))
                    if w % 3:
                        continue
                    sw = w//3
                    for state in range(3):
                        sprite = b''.join(pixels[(y*w+state*sw)*4:(y*w+(state+1)*sw)*4] for y in range(h))
                        templates.setdefault(icon,[]).append((sw,h,sprite))
            _templates.clear(); _templates[stamp] = templates
    templates = _templates[stamp]
    # Default icons do not establish action identity after a user customizes
    # this toolbar. Until custom command/icon pairs are supported, omit it.
    customized = False
    menu = Path(request['resource'])/'reaper-menu.ini'
    if menu.exists():
        config = configparser.ConfigParser(strict=False,interpolation=None)
        config.read(menu)
        customized = config.has_section('Main toolbar')
    buttons = []
    for region,rect in request['panels'].items():
        if region not in BUTTONS or (region == 'Toolbar' and customized):
            continue
        image = outline.snapshot(tuple(rect))
        for command,label,icons in BUTTONS[region]:
            matches = set()
            for icon in icons:
                for template in templates.get(icon,[]):
                    matches.update(find_image(image,template))
            if len(matches) == 1:
                x,y,w,h = matches.pop()
                buttons.append((region,command,label,x+rect[0],y+rect[1],w,h))
    counts = collections.Counter((row[0],*row[3:]) for row in buttons)
    return [row for row in buttons if counts[(row[0],*row[3:])] == 1]


def update(outline, request_path, result_path, previous):
    global _retry_after
    try:
        request = json.loads(request_path.read_text())
        if request['generation'] == previous:
            return previous
        if time.monotonic() < _retry_after:
            return previous
        buttons = detect(outline,request)
        text = str(request['generation'])+'\n'+''.join('\t'.join(map(str,row))+'\n' for row in buttons)
        temporary = result_path.with_suffix('.tmp')
        temporary.write_text(text); temporary.replace(result_path)
        missing = set(request['panels'])-set(row[0] for row in buttons)
        if missing:
            _retry_after = time.monotonic()+1
            return previous
        return request['generation'] if buttons else previous
    except (OSError,ValueError,KeyError,zipfile.BadZipFile):
        return previous
