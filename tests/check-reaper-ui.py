#!/usr/bin/python3
"""Check exact native button discovery, ambiguity rejection and cached geometry."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
from unittest.mock import Mock, patch
import zipfile
import zlib

PROJECT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reaper_ui',PROJECT/'setup/development/reaper-ui.py')
ui=importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)

def png(width,height,pixels):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+pixels[y*width*4:(y+1)*width*4] for y in range(height))))+chunk(b'IEND',b'')

icon=bytes(sum(([40+x*20,50+y*20,70+x*y,255] for y in range(4) for x in range(4)),[]))
def canvas(positions):
    image=bytearray(bytes([9,9,9,255])*24*12)
    for x,y in positions:
        for row in range(4):image[((y+row)*24+x)*4:((y+row)*24+x+4)*4]=icon[row*16:(row+1)*16]
    return 24,12,bytes(image)

assert ui.find_image(canvas([(2,3)]),(4,4,icon))==[(2,3,4,4)]
assert ui.find_image(canvas([(2,3),(15,4)]),(4,4,icon))==[(2,3,4,4),(15,4,4,4)]
assert not ui.find_image(canvas([]),(4,4,icon))
assert not ui.find_image((2,2,b'\0'*16),(4,4,icon))
assert ui.decode_png(png(4,4,icon))==(4,4,icon)
with tempfile.TemporaryDirectory(prefix='reaper-ui-check-') as name:
    root=Path(name);theme=root/'Theme.ReaperThemeZip'
    sprite=b''.join(icon[y*16:(y+1)*16]*3 for y in range(4))
    with zipfile.ZipFile(theme,'w') as archive:archive.writestr('Theme/toolbar_new.png',png(12,4,sprite))
    request={'generation':1,'theme':str(theme),'resource':str(root),'panels':{'Toolbar':[10,20,24,12]}}
    outline=Mock();outline.snapshot.return_value=canvas([(2,3)])
    with patch.object(ui,'BUTTONS',{'Toolbar':((40023,'New project',('toolbar_new',)),)}):
        assert ui.detect(outline,request)==[('Toolbar',40023,'New project',12,23,4,4)]
        outline.snapshot.return_value=canvas([(2,3),(15,4)])
        assert ui.detect(outline,request)==[], 'Ambiguous button accepted'
        outline.snapshot.return_value=canvas([(2,3)])
        source=root/'request';result=root/'buttons';source.write_text(json.dumps(request))
        assert ui.update(outline,source,result,None)==1
        assert result.read_text()=='1\nToolbar\t40023\tNew project\t12\t23\t4\t4\n'
        outline.reset_mock();assert ui.update(outline,source,result,1)==1;outline.snapshot.assert_not_called()
        (root/'reaper-menu.ini').write_text('[Main toolbar]\nitem_0=123\n')
        assert ui.detect(outline,request)==[], 'Default action assumed for a customized toolbar'
print('Passed: PNG decoding, exact themed button positions, hidden/ambiguous rejection, generation caching and customized-toolbar refusal.')
