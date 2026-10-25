"""Locate native REAPER buttons from the current theme's exact rendered images.

Runs in the existing outline process. Captures only the reported native panels;
matching never moves/clicks the pointer and rejects ambiguous/hidden buttons.
"""
import collections
import configparser
import ctypes as C
import json
import re
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
        (42616,'Marquee selection',('toolbar_marquee_cursor_selection','toolbar_marquee_cursor_selection_on','toolbar_marquee_cursor_selection_off')),
        (42618,'Razor editing',('toolbar_razor_on','toolbar_razor_off')),
        (40070,'Move envelope points with items',('toolbar_envitem_on','toolbar_envitem_off','toolbar_v3_envitem')),
    ),
    'Transport': (
        (40042,'Go to start',('transport_home',)), (40043,'Go to end',('transport_end',)),
        (1016,'Stop',('transport_stop',)), (1007,'Play',('transport_play','transport_play_on','transport_play_sync','transport_play_sync_on')),
        (1008,'Pause',('transport_pause','transport_pause_on')), (1013,'Record',('transport_record','transport_record_on')),
        (1068,'Repeat',('transport_repeat_off','transport_repeat_on')),
        (1134,'Tap tempo',()),
    ),
}


# Field identifiers occupy a reserved range; they are never dispatched as native
# REAPER command IDs. These anchors remain exact rendered theme images.
FIELD_ANCHORS = {
    60001: ('Global automation override',tuple('global_'+name for name in
            ('off','trim','read','touch','latch','write','preview','bypass'))),
    60005: ('Project timebase',('transport_timebase_beat','transport_timebase_time')),
}

def transport_fields(request, anchors):
    """Resolve the installed Reapertips value fields from two visible anchors.

    Reapertips paints these fields inside one owner-drawn window, without native
    child HWNDs. Validate its WALTER cell sizes before using relative geometry.
    Other themes still retain exact matched buttons/anchors.
    """
    automation=anchors.get(60001); timebase=anchors.get(60005)
    if not automation or not timebase:
        return []
    with zipfile.ZipFile(request['theme']) as archive:
        configs=[n for n in archive.namelist() if n.endswith('/rtconfig.txt') and n.count('/')==1]
        if len(configs)!=1 or not configs[0].startswith('ReaperTips_'):
            return []
        walter=archive.read(configs[0]).decode(errors='replace')
    cells={name:tuple(map(int,(px,py,w,h))) for name,px,py,w,h in
           re.findall(r'^\s*size\s+(automode|bpm_tap|bpm_edit|timesig|timebase)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)',walter,re.M)}
    if cells!={'automode':(0,6,60,26),'bpm_tap':(0,7,33,24),'bpm_edit':(0,8,32,22),
               'timesig':(0,8,33,22),'timebase':(0,8,33,22)}:
        return []
    ax,ay,aw,ah=automation; tx,ty,tw,th=timebase
    scale=ah/26
    if scale not in (1,1.5,2) or abs(aw-60*scale)>1 or abs(tw-33*scale)>1 or abs(th-22*scale)>1:
        return []
    if abs(ty-(ay+2*scale))>2*scale:
        return []
    tap_x=ax+aw+12*scale; tempo_x=tap_x+33*scale
    gap=tx-(tempo_x+32*scale)
    if abs(gap)>scale and abs(gap-33*scale)>scale:
        return []
    result=[(1134,'Tap tempo',(tap_x,ay+scale,33*scale,24*scale)),
            (60002,'Tempo',(tempo_x,ay+2*scale,32*scale,22*scale))]
    if abs(gap-33*scale)<=scale:
        result.append((60003,'Time signature',(tempo_x+32*scale,ay+2*scale,33*scale,22*scale)))
    # In the single-row layout, this is the last cell before the panel margin.
    panel=request['panels']['Transport']; rate_x=tx+tw+12*scale
    rate_width=panel[0]+panel[2]-6*scale-rate_x
    if abs(panel[3]-36*scale)<=scale and 59*scale<=rate_width<=161*scale:
        rect=(rate_x-4*scale,ay-scale,rate_width+4*scale,28*scale) if rate_width<80*scale else (rate_x,ay+2*scale,rate_width,22*scale)
        result.append((60004,'Playback rate',rect))
    output=[]
    for command,label,rect in result:
        x,y,w,h=map(round,rect)
        if panel[0]<=x and panel[1]<=y and x+w<=panel[0]+panel[2] and y+h<=panel[1]+panel[3]:
            output.append(('Transport',command,label,x,y,w,h))
    return output


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
            wanted.update(icon for _,icons in FIELD_ANCHORS.values() for icon in icons)
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
        entries=list(BUTTONS[region])
        if region=='Transport':
            entries += [(command,label,icons) for command,(label,icons) in FIELD_ANCHORS.items()]
        anchors={}
        for command,label,icons in entries:
            matches = set()
            for icon in icons:
                for template in templates.get(icon,[]):
                    matches.update(find_image(image,template))
            if len(matches) == 1:
                x,y,w,h = matches.pop()
                absolute=(x+rect[0],y+rect[1],w,h)
                buttons.append((region,command,label,*absolute))
                if command in FIELD_ANCHORS: anchors[command]=absolute
        if region=='Transport': buttons.extend(transport_fields(request,anchors))
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
