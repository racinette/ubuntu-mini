#!/usr/bin/python3
"""Exercise the native window/region/control model with independent UI fixtures."""
import ctypes as C
import ctypes.util
import json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
code=r'''
local nodes,commands={},{}
local names={'Freq-Low Shelf','Gain-Low Shelf','BW-Low Shelf','Global Gain','Bypass','Wet','Delta'}
local function add(n,id,class,title,parent,x,y,w,h)
 nodes[n]={id=id,class=class,title=title,parent=parent,rect={x,y,x+w,y+h},style=0,check=1,combo=0}
end
add(1,0,'unknown','',nil,0,0,900,550)
add(2,0,'unknown','',1,150,90,750,460)
add(3,1076,'SysListView32','',1,0,40,140,430)
add(4,1075,'Button','Add',1,0,480,50,25)
add(5,1058,'Button','Remove',1,60,480,60,25)
add(6,1000,'combobox','Preset',1,150,40,500,25)
add(7,1034,'Static','ReaEQ',2,150,90,80,20)
add(8,1023,'REAPERhfader','',2,270,350,400,25)
add(9,1024,'REAPERhfader','',2,270,390,400,25)
add(10,1025,'REAPERhfader','',2,270,430,400,25)
add(11,1026,'SysTabControl32','',2,160,300,600,180)
add(12,1018,'Button','Add band',2,160,500,80,25)
add(13,1019,'Button','Remove band',2,250,500,100,25)
add(14,1022,'Button','Enabled',2,160,330,80,20)
add(15,1015,'combobox','Band',2,300,330,150,20)
add(16,1449,'REAPERknob','',1,780,40,25,25)
add(17,1426,'Button','',1,820,40,20,20)
local plugin='/opt/reaeq.vst.so<1'
local fx=0
reaper={
 JS_Window_ListAllChild=function(root)
  local result={}
  for id,node in pairs(nodes) do local parent=node.parent
   while parent do if parent==root then result[#result+1]=tostring(id);break end;parent=nodes[parent].parent end
  end
  table.sort(result);return true,table.concat(result,',')
 end,
 JS_Window_HandleFromAddress=function(id) return id end,
 JS_Window_AddressFromHandle=function(id) return id end,
 JS_Window_GetLong=function(id,key) return key=='STYLE' and nodes[id].style or nodes[id].id end,
 JS_Window_GetClassName=function(id) return nodes[id].class end,
 JS_Window_GetTitle=function(id) return nodes[id].title end,
 JS_Window_GetParent=function(id) return nodes[id].parent end,
 JS_Window_IsVisible=function(id) return nodes[id]~=nil end,
 JS_Window_GetRect=function(id) return true,table.unpack(nodes[id].rect) end,
 JS_WindowMessage_Send=function(hwnd,msg,value,high,pointer)
  if msg=='CB_GETCOUNT' then return 3
  elseif msg=='CB_GETCURSEL' then return nodes[hwnd].combo
  elseif msg=='CB_SETCURSEL' then nodes[hwnd].combo=value
  elseif msg=='BM_GETCHECK' then return nodes[hwnd].check
  elseif msg=='BM_SETCHECK' then nodes[hwnd].check=value
  elseif msg=='WM_COMMAND' then commands[#commands+1]={owner=hwnd,id=value,notification=high,pointer=pointer} end
  return 0
 end,
 TrackFX_GetCount=function() return 2 end,
 TrackFX_GetNumParams=function() return #names end,
 TrackFX_GetChainVisible=function() return fx end,
 TrackFX_GetParamName=function(_,_,p) return true,names[p+1] end,
 TrackFX_GetParamIdent=function(_,_,p) return true,p==4 and '4:bypass' or p==5 and '5:wet' or tostring(p) end,
 TrackFX_GetNamedConfigParm=function() return true,plugin end,
 TrackFX_GetFXGUID=function() return '{fx-guid}' end,
 TrackFX_Show=function(_,index) fx=index end,
 time_precise=function() return 1 end
}
local ui=dofile(MODULE)
local area={id=30,track='track',fx=0,hwnd=1,kind='chain',page=2,focused=true}
ui.areas={{id=20,key='Tracks'},{id=20,key='Timeline'},area}
assert(#ui.windows()==2 and ui.window_neighbor(20,-1).id==30 and ui.window_neighbor(30,1).id==20)
local regions=ui.fx_regions(area,0,0,1)
assert(#regions==3 and regions[1].key=='effects' and regions[2].key=='header' and regions[3].key=='plugin')
local state=ui.fx_memory[30]
local function choose(region,key)
 state.region=region;state.selection[region]=key
 local node=ui.fx_current(30);assert(node and node.key==key);return node
end
assert(ui.fx_current(30).key=='eq:freq')
local band=choose('plugin','eq:band');assert(band.rect[4]==24)
choose('plugin','eq:freq')
local spatial=dofile(NAVIGATION)
ui.fx_move(30,'down',spatial);assert(ui.fx_current(30).key=='eq:gain' and #commands==0)
choose('plugin','eq:add');ui.fx_activate(30)
assert(commands[#commands].owner==2 and commands[#commands].id==1018 and commands[#commands].pointer==12)
choose('effects','effects:remove');ui.fx_activate(30)
assert(commands[#commands].owner==1 and commands[#commands].id==1058 and commands[#commands].pointer==5)
choose('plugin','eq:enabled');ui.fx_activate(30)
assert(nodes[14].check==0 and commands[#commands].id==1022)
ui.fx_step(30,'right');assert(nodes[14].check==1)
choose('plugin','eq:type');ui.fx_activate(30);assert(state.editing)
ui.fx_move(30,'right',spatial);assert(nodes[15].combo==1 and commands[#commands].notification==1)
assert(ui.fx_cancel(30) and nodes[15].combo==0 and not state.editing)
choose('effects','effects:list');ui.fx_activate(30)
assert(ui.fx_move(30,'down',spatial)==1 and fx==1)
assert(ui.fx_cancel(30) and fx==0)
-- Removed, disabled and foreign controls cannot retain a stale activation target.
nodes[12].style=0x08000000;ui.fx_regions(area,0,0,2)
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.key~='eq:add') end end
nodes[12].style=0;nodes[12].rect={1000,500,1080,525};ui.fx_regions(area,0,0,2)
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.key~='eq:add') end end
plugin='/opt/unknown.vst.so<9';state.region='plugin';ui.fx_regions(area,0,0,2)
assert(state.region=='effects' and ui.fx_current(30).kind~='param')
local saved=nodes[1];nodes[1]=nil;ui.fx_regions(area,0,0,3);assert(not ui.fx_current(30));nodes[1]=saved
assert(ui.window_neighbor(999,1).id==20 and ui.window_neighbor(999,-1).id==30)
print('Passed: deduplicated window cycling, scoped regions, spatial widgets, tab-strip geometry, owner-bound commands, toggles, selectors/cancel and disabled/clipped/foreign-control guards.')
'''.replace('MODULE',json.dumps(str(PROJECT/'setup/development/reaper-ui.lua'))).replace('NAVIGATION',json.dumps(str(PROJECT/'setup/development/reaper-control-navigation.lua')))
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
