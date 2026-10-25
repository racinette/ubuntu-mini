#!/usr/bin/python3
"""Exercise native FX widget selection, deferred EQ tabs and clipping in Lua."""
import ctypes as C
import ctypes.util
import json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
code=r'''
local nodes,children,messages={},{},{}
local plugin,name,ident='/opt/REAPER/Plugins/FX/reaeq.vst.so<1','Freq-Band 2','3:_Freq'
local function add(n,id,class,title,parent,rect)
 nodes[n]={id=id,class=class,title=title,parent=parent,rect=rect,visible=true}
end
add(1,0,'unknown','','',{0,0,500,400})
add(2,0,'unknown','',1,{0,40,500,400})
add(3,1034,'Static','ReaEQ',2,{0,40,100,60})
add(4,1026,'SysTabControl32','',2,{0,60,450,400})
add(5,1023,'REAPERhfader','',2,{120,100,300,130})
add(6,1024,'REAPERhfader','',2,{120,150,300,180})
add(7,1025,'REAPERhfader','',2,{120,200,300,230})
add(8,1047,'REAPERvfader','',2,{400,80,430,300})
add(9,1449,'REAPERknob','',1,{400,4,430,34})
add(10,1426,'Button','',1,{450,4,470,24})
reaper={
 JS_Window_ListAllChild=function(root)
  local result={}
  for id,node in pairs(nodes) do
   local parent=node.parent
   while nodes[parent] do if parent==root then result[#result+1]=tostring(id);break end;parent=nodes[parent].parent end
  end
  table.sort(result);return true,table.concat(result,',')
 end,
 JS_Window_HandleFromAddress=function(id) return id end,
 JS_Window_GetLong=function(id) return nodes[id].id end,
 JS_Window_GetClassName=function(id) return nodes[id].class end,
 JS_Window_GetTitle=function(id) return nodes[id].title end,
 JS_Window_GetParent=function(id) return nodes[id].parent end,
 JS_Window_IsVisible=function(id) return nodes[id] and nodes[id].visible end,
 JS_Window_GetRect=function(id) return true,table.unpack(nodes[id].rect) end,
 JS_WindowMessage_Send=function(hwnd,msg,key,high,flag) messages[#messages+1]={hwnd,msg,key,flag} end,
 TrackFX_GetChainVisible=function() return 0 end,
 TrackFX_GetParamIdent=function() return true,ident end,
 TrackFX_GetParamName=function() return true,name end,
 TrackFX_GetNamedConfigParm=function() return true,plugin end,
 TrackFX_GetFXGUID=function() return '{fx-guid}' end
}
local ui=dofile(MODULE)
ui.areas={{track='track',fx=0,id=77,hwnd=1,kind='chain',focused=true}}
local rect,id,note=ui.fx_outline('track',0,3,1)
assert(not rect and note=='Selecting EQ band 2')
assert(#messages==2 and messages[1][3]==36 and messages[2][3]==39 and messages[2][4]==1)
rect,id,note=ui.fx_outline('track',0,3,1.2)
assert(rect[1]==120 and rect[2]==100 and rect[3]==180 and id==77 and note=='')
name='Gain-Band 2';rect=ui.fx_outline('track',0,4,1.3)
assert(rect[2]==150 and #messages==2,'Same band should not be reselected for every parameter')
name='BW-Band 2';rect=ui.fx_outline('track',0,5,1.4);assert(rect[2]==200)
name='Global Gain';rect=ui.fx_outline('track',0,15,2);assert(rect[1]==400)
ident='16:bypass';rect=ui.fx_outline('track',0,16,2);assert(rect[1]==450)
ident='17:wet';rect=ui.fx_outline('track',0,17,2);assert(rect[1]==400 and rect[2]==4)
ident='18:delta';name='Delta';rect,id,note=ui.fx_outline('track',0,18,2)
assert(not rect and note=='No visible control mapping for this parameter')
-- Native viewport, not the plug-in's larger desired size, limits the outline.
ident='3:_Freq';name='Freq-Band 2';nodes[1].rect={0,0,200,400}
rect,id,note=ui.fx_outline('track',0,3,3)
assert(rect[1]==120 and rect[3]==76 and note:find('partly clipped'))
nodes[1].rect={0,0,100,400};rect,id,note=ui.fx_outline('track',0,3,3)
assert(not rect and note:find('outside tile'))
nodes[1].rect={0,0,500,400};nodes[4].visible=false
rect,id,note=ui.fx_outline('track',0,3,3);assert(not rect and note:find('Show tabs'))
nodes[4].visible=true;nodes[5].visible=false
rect,id,note=ui.fx_outline('track',0,3,3);assert(not rect and note=='Control is hidden')
nodes[5].visible=true
-- Duplicate identities and other plug-ins never reuse a stale stock rectangle.
add(11,1023,'REAPERhfader','',2,{120,240,300,270})
rect=ui.fx_outline('track',0,3,3);assert(not rect)
plugin='/opt/Other.vst.so<123';rect=ui.fx_outline('track',0,3,3);assert(not rect)
ui.areas={};rect,id,note=ui.fx_outline('track',0,3,3);assert(not rect and note:find('Open'))
print('Passed: exact FX widgets, deferred band reveal, stable same-band selection, host controls, clipping, hidden/ambiguous/unmapped/foreign-plugin guards.')
'''.replace('MODULE',json.dumps(str(PROJECT/'setup/development/reaper-ui.lua')))
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
