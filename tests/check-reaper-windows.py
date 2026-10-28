#!/usr/bin/python3
"""Check compositor focus guards and current-project FX ownership for L2."""
import ctypes as C
import ctypes.util
import json
from pathlib import Path
import runpy
import tempfile
from unittest.mock import Mock, patch

PROJECT=Path(__file__).resolve().parents[1]
module=runpy.run_path(str(PROJECT/'setup/development/reaper-control-outline.py'))
with tempfile.TemporaryDirectory() as tmp:
    state=Path(tmp)/'outline'
    outline=Mock(pid=42)
    outline.owner.return_value=42
    outline.viewable.return_value=True
    outline.geometry.return_value=(0,0,400,300)
    tree={'nodes':[{'id':7,'pid':42,'window':70,'name':'Project - REAPER v7','focused':True},
                   {'id':8,'pid':42,'window':80,'name':'FX: Track 1 "One"'},
                   {'id':9,'pid':99,'window':90,'name':'Foreign'}]}
    calls=[]
    def ipc(kind,payload=''):
        if kind==4:return tree
        calls.append(payload)
        for node in tree['nodes']:node['focused']=node['id']==int(payload.split('=')[1].split(']')[0])
        return [{'success':True}]
    picker=module['WindowPicker'](state,outline)
    # run_path function globals belong to its separate execution dictionary.
    with patch.dict(picker.update.__globals__,ipc=ipc):
        Path(str(state)+'.focus').write_text('1 8')
        picker.update()
        assert calls==['[con_id=8] focus']
        assert Path(str(state)+'.focused').read_text()=='1 1'
        assert 'Foreign' not in Path(str(state)+'.windows').read_text()
        picker.update();assert len(calls)==1, 'Repeated request focused twice'
        tree['nodes'][0]['focused']=False;tree['nodes'][1]['focused']=False;tree['nodes'][2]['focused']=True
        Path(str(state)+'.focus').write_text('2 7');picker.update()
        assert len(calls)==1 and Path(str(state)+'.focused').read_text()=='2 0'
        tree['nodes'][2]['focused']=False;tree['nodes'][0]['focused']=True
        Path(str(state)+'.focus').write_text('3 404');picker.update()
        assert len(calls)==1 and Path(str(state)+'.focused').read_text()=='3 0'
        Path(str(state)+'.focus').write_text('4 9');picker.update()
        assert len(calls)==1 and Path(str(state)+'.focused').read_text()=='4 0'
        outline.viewable.return_value=False
        Path(str(state)+'.focus').write_text('5 8');picker.update()
        assert len(calls)==1 and Path(str(state)+'.focused').read_text()=='5 0'
        assert len(Path(str(state)+'.windows').read_text().splitlines())==1
        # Explicit native commands focus a child dialog of their project only.
        import time
        outline.viewable.return_value=True
        tree['nodes'].append({'id':11,'pid':42,'window':110,'name':'Add FX to Track 1',
                              'window_properties':{'transient_for':70}})
        popup=Path(str(state)+'.popup')
        popup.write_text(f'{int(time.time())}\t7\t7,8,9\tAdd FX ')
        picker.update()
        assert calls[-1]=='[con_id=11] focus' and len(calls)==2 and not popup.exists()
        for node in tree['nodes']:node['focused']=node['id']==9
        popup.write_text(f'{int(time.time())}\t7\t7,8,9\tAdd FX ')
        picker.update();assert len(calls)==2 and not popup.exists()
        for node in tree['nodes']:node['focused']=node['id']==7
        tree['nodes'][-1]['window_properties']['transient_for']=999
        popup.write_text(f'{int(time.time())}\t7\t7,8,9\tAdd FX ')
        picker.update();assert len(calls)==2
        popup.write_text(f'{int(time.time())-4}\t7\t7,8,9\tAdd FX ')
        picker.update();assert not popup.exists() and len(calls)==2

print('Passed: exact compositor IDs, single dispatch, foreign PID/closed target rejection and no background focus stealing.')
# Sway's child order follows tab placement even when IDs and focus history do
# not. Preserve it across nested tab groups and a later tab rearrangement.
with tempfile.TemporaryDirectory() as tmp:
    state=Path(tmp)/'outline'
    outline=Mock(pid=42)
    outline.owner.return_value=42
    outline.viewable.return_value=True
    outline.geometry.return_value=(0,0,400,300)
    def window(id):return dict(id=id,pid=42,window=id*10,name=f'Window {id}')
    tabs={'layout':'tabbed','focus':[8,30,7],
          'nodes':[window(30),{'layout':'splith','nodes':[window(7),window(8)]}]}
    tree={'nodes':[tabs]}
    picker=module['WindowPicker'](state,outline)
    with patch.dict(picker.update.__globals__,ipc=lambda *_:tree):
        def order():
            picker.update()
            return [int(row.split('\t')[0]) for row in Path(str(state)+'.windows').read_text().splitlines()[1:]]
        assert order()==[30,7,8]
        tabs['nodes'].reverse()
        assert order()==[7,8,30], 'Tab moves must update the exported order'

# The popup must belong to this PID and be an override-redirect native menu.
outline=object.__new__(module['Outline'])
outline.pid,outline.root,outline.display=42,1,None
outline.children=lambda root:[7]
outline.owner=lambda window:42
outline.title=lambda window:'menu'
flags={'override':True,'visible':True}
def attributes(display,window,pointer):
    pointer._obj.override_redirect=flags['override']
    pointer._obj.map_state=2 if flags['visible'] else 0
    return 1
outline.x=Mock();outline.x.XGetWindowAttributes.side_effect=attributes
assert outline.native_menu()
flags['override']=False;assert not outline.native_menu()
flags['override']=True;flags['visible']=False;assert not outline.native_menu()
flags['visible']=True;outline.owner=lambda window:99;assert not outline.native_menu()
outline.owner=lambda window:42;outline.title=lambda window:'tooltip';assert not outline.native_menu()
print('Passed: owned native menu detection, override-redirect/visibility checks and foreign-window rejection.')


with tempfile.TemporaryDirectory() as tmp:
    code=r'''
local path=ROOT..'/outline'
local clock=100
local tracks={{name='One',fx=1},{name='Two',fx=0}}
local rects={main={0,0,400,300},chain={400,0,800,300},floating={800,0,1000,200}}
local titles={main='Project - REAPER v7',chain='FX: Track 1 "One"',floating='VST: Plugin'}
reaper={
 JS_Window_IsVisible=function(hwnd) return rects[hwnd]~=nil end,
 JS_Window_GetRect=function(hwnd) return true,table.unpack(rects[hwnd]) end,
 JS_Window_GetTitle=function(hwnd) return titles[hwnd] end,
 JS_Window_Find=function(title)
  for hwnd,value in pairs(titles) do if title==value then return hwnd end end
 end,
 GetMainHwnd=function() return 'main' end,
 CountTracks=function() return #tracks end,
 GetTrack=function(_,i) return tracks[i+1] end,
 GetTrackName=function(t) return true,t.name end,
 GetSetMediaTrackInfo_String=function(t,key,_,set)
  assert(key=='P_NAME' and not set);return true,t.name
 end,
 TrackFX_GetChainVisible=function(t) return t==tracks[1] and t.fx or t.chain or -1 end,
 TrackFX_GetCount=function() return 2 end,
 TrackFX_GetFloatingWindow=function(t,i) return t==tracks[2] and i==0 and 'floating' or nil end
}
local ui=dofile(MODULE)
ui.panels={Timeline={200,50,200,200},Tracks={0,50,200,200},Toolbar={0,0,200,50},Transport={0,250,400,50}}
local function write(suffix,text) local f=assert(io.open(path..suffix,'w'));f:write(text);f:close() end
local function scan(stamp)
 write('.windows',(stamp or os.time())..'\n7\t0\t0\t0\t400\t300\tProject - REAPER v7\n8\t1\t400\t0\t400\t300\tFX: Track 1 "One"\n9\t0\t800\t0\t200\t200\tVST: Plugin\n10\t0\t1100\t0\t200\t200\tFX: Track 7 "Foreign project"')
 ui.scan_windows(path)
end
scan();assert(#ui.areas==6)
for i=1,4 do assert(ui.areas[i].main==i-1 and ui.areas[i].id==7) end
assert(ui.areas[5].key=='fx:8' and ui.areas[5].track==tracks[1] and ui.areas[5].fx==1 and ui.areas[5].focused)
assert(ui.areas[6].key=='fx:9' and ui.areas[6].track==tracks[2] and ui.areas[6].fx==0)
assert(#ui.windows()==3 and ui.focused_window().id==8)
assert(ui.window_neighbor(7,1).id==8 and ui.window_neighbor(7,-1).id==9)
assert(ui.window_neighbor(9,1).id==7 and ui.window_neighbor(8,-1).id==7)
-- Equal-sized tabs have no useful spatial difference; row order is authoritative.
local saved_rects=rects
rects={main={0,0,400,300},chain={0,0,400,300},floating={0,0,400,300}}
local rows={
 '9\t0\t0\t0\t400\t300\tVST: Plugin',
 '8\t1\t0\t0\t400\t300\tFX: Track 1 "One"',
 '99\t0\t0\t0\t400\t300\tDevice gamepad',
 '7\t0\t0\t0\t400\t300\tProject - REAPER v7'}
local function tabs()
 write('.windows',os.time()..'\n'..table.concat(rows,'\n'));ui.scan_windows(path)
end
tabs();local ordered=ui.windows()
assert(#ordered==3 and ordered[1].id==9 and ordered[2].id==8 and ordered[3].id==7)
assert(ui.window_neighbor(9,1).id==8 and ui.window_neighbor(9,-1).id==7)
assert(ui.window_neighbor(7,1).id==9 and ui.window_neighbor(7,-1).id==8)
assert(ui.focused_window().id==8,'Focus must not reorder tabs')
rows[1],rows[4]=rows[4],rows[1];tabs()
ordered=ui.windows();assert(ordered[1].id==7 and ordered[2].id==8 and ordered[3].id==9)
assert(ui.window_neighbor(8,1).id==9 and ui.window_neighbor(8,-1).id==7)
-- Unnamed track chains omit the quoted name entirely. They must participate
-- in the same visible tab order, including empty chains and later renaming.
tracks[2].name='';tracks[2].chain=0
titles.second='FX: Track 2';rects.second={0,0,400,300}
rows[#rows+1]='19\t0\t0\t0\t400\t300\tFX: Track 2'
tabs();ordered=ui.windows()
assert(#ordered==4 and ordered[4].id==19 and ordered[4].track==tracks[2])
assert(ui.window_neighbor(9,1).id==19 and ui.window_neighbor(7,-1).id==19)
assert(ui.window_neighbor(19,1).id==7 and ui.window_neighbor(19,-1).id==9)
tracks[2].chain=-2;tabs();assert(#ui.windows()==4,'Empty unnamed chain must remain reachable')
tracks[2].name='Track 2';titles.second='FX: Track 2 "Track 2"'
rows[#rows]='19\t0\t0\t0\t400\t300\tFX: Track 2 "Track 2"'
tabs();assert(#ui.windows()==4,'Explicit default-looking names still have quotes')
tracks[2].chain=-1;tabs();assert(#ui.windows()==3,'Closed unnamed chain must disappear')
rects=saved_rects
-- Closed chains and stale discovery cannot leave an editable ghost target.
tracks[1].fx=-1;scan();assert(#ui.areas==5 and ui.areas[5].key=='fx:9')
scan(os.time()-5);assert(#ui.areas==0)
scan();local area=ui.areas[5]
ui.focus(path,area,clock);assert(ui.pending.area==area)
assert(ui.focus_result(path,clock+.2)==nil)
write('.focused','1 1');local result,ok=ui.focus_result(path,clock+.3)
assert(result==area and ok and not ui.pending)
ui.focus(path,area,clock);write('.focused','1 1') -- Old acknowledgement ignored.
assert(ui.focus_result(path,clock+.3)==nil)
result,ok=ui.focus_result(path,clock+2);assert(result==area and not ok)
ui.focus(path,area,clock);ui.cancel_focus(path);assert(not ui.pending and not io.open(path..'.focus'))
print('Passed: main regions, track-chain/floating ownership, stable IDs, closed/stale discovery, focus acknowledgement, timeout and cancellation.')
'''.replace('ROOT',json.dumps(tmp)).replace('MODULE',json.dumps(str(PROJECT/'setup/development/reaper-ui.lua')))
    lua=C.CDLL(ctypes.util.find_library('lua5.4') or 'liblua5.4.so.0')
    lua.luaL_newstate.restype=C.c_void_p
    lua.luaL_openlibs.argtypes=[C.c_void_p]
    lua.luaL_loadstring.argtypes=[C.c_void_p,C.c_char_p]
    lua.lua_pcallk.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ssize_t,C.c_void_p]
    lua.lua_tolstring.argtypes=[C.c_void_p,C.c_int,C.c_void_p];lua.lua_tolstring.restype=C.c_char_p
    lua.lua_close.argtypes=[C.c_void_p]
    state=lua.luaL_newstate();lua.luaL_openlibs(state)
    try:
        result=lua.luaL_loadstring(state,code.encode()) or lua.lua_pcallk(state,0,0,0,0,None)
        if result:raise RuntimeError(lua.lua_tolstring(state,-1,None).decode())
    finally:lua.lua_close(state)
