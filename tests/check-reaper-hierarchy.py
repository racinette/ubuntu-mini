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
choose('effects','effects:list')
assert(ui.fx_move(30,'down',spatial)==1 and fx==1)
assert(not state.editing and not ui.fx_cancel(30))
for _,direction in ipairs({'left','right','up','down'}) do ui.fx_step(30,direction);assert(fx==1,'Right stick must not switch effects') end
assert(ui.fx_move(30,'up',spatial)==0 and fx==0)
ui.fx_move(30,'up',spatial);assert(fx==0 and ui.fx_current(30).kind=='effects')
ui.fx_move(30,'down',spatial);ui.fx_move(30,'down',spatial)
assert(ui.fx_current(30).kind=='command','Down past the last effect reaches the buttons')
ui.fx_move(30,'up',spatial);assert(ui.fx_current(30).kind=='effects')
ui.fx_activate(30);assert(state.region=='plugin' and not state.editing,'A enters the selected effect controls')
-- Removed, disabled and foreign controls cannot retain a stale activation target.
nodes[12].style=0x08000000;ui.fx_regions(area,0,0,2)
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.key~='eq:add') end end
nodes[12].style=0;nodes[12].rect={1000,500,1080,525};ui.fx_regions(area,0,0,2)
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.key~='eq:add') end end
plugin='/opt/unknown.vst.so<9';state.region='plugin';ui.fx_regions(area,0,0,2)
assert(state.region=='plugin' and ui.fx_current(30).kind~='param')
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(not n.key:match('^eq:') and n.param~=0,'Unknown FX must not reuse the EQ parameter map') end end

-- Unmapped native plug-ins use ownership rather than globally unique IDs.
add(30,0,'unknown','',1,150,30,750,520)
for _,id in ipairs({2,6,16,17}) do nodes[id].parent=30 end
add(31,1192,'Button','UI',30,680,40,40,25)
add(32,1422,'Button','Param',30,600,40,60,25)
add(33,1192,'Button','UI',2,600,100,40,25)
add(34,1076,'SysListView32','',2,300,150,200,100)
add(35,1075,'Button','Add',2,300,260,60,25)
add(36,1058,'Button','Remove',2,370,260,80,25)
add(37,2000,'Button','Frame',2,150,90,740,450);nodes[37].style=0x20000000
add(38,2001,'Static','Wet:',2,160,110,60,15)
add(39,2002,'REAPERhfader','',2,230,105,150,25)
add(40,2003,'Edit','0.5',2,390,105,50,25)
add(41,2004,'Edit','read only',2,450,105,60,25);nodes[41].style=0x800
add(42,2005,'Button','Enabled',2,600,140,100,25);nodes[42].style=3
names[1]='Wet'
local selection,count,visible=-1,3,-1
reaper.JS_ListView_EnumSelItems=function() return selection end
reaper.JS_ListView_GetItemCount=function() return count end
reaper.JS_ListView_SetItemState=function(_,index,value,mask) assert(mask==3);selection=value==0 and -1 or index end
reaper.JS_ListView_EnsureVisible=function(_,index) visible=index end
reaper.JS_Window_IsWindow=function(hwnd) return nodes[hwnd]~=nil end
reaper.JS_Window_SetTitle=function(hwnd,text) nodes[hwnd].title=text end
local accept=false
reaper.GetUserInputs=function() return accept,'0.75' end
ui.fx_regions(area,0,0,3)
assert(choose('effects','effects:list').hwnd==3)
assert(choose('header','header:1192').hwnd==31)
assert(choose('plugin','native:39').param==0,'Plugin Wet must not bind host Wet')
assert(choose('plugin','native:40').label=='Wet')
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.hwnd~=37 and n.hwnd~=41) end end
choose('plugin','native:35');ui.fx_activate(30)
assert(commands[#commands].owner==2 and commands[#commands].pointer==35,'Internal Add must not invoke host Add FX')
choose('plugin','native:34');ui.fx_activate(30);assert(state.editing and selection==0 and visible==0)
ui.fx_cancel(30);assert(selection==-1)
selection=1;ui.fx_activate(30);selection=2;ui.fx_cancel(30);assert(selection==1)
count=0;assert(ui.fx_activate(30):find('empty') and not state.editing);count=3
choose('plugin','native:40');ui.fx_activate(30);assert(nodes[40].title=='0.5')
accept=true;ui.fx_activate(30);assert(nodes[40].title=='0.75' and commands[#commands].notification==0x300)
choose('plugin','native:42');ui.fx_activate(30);assert(nodes[42].check==0)
choose('plugin','native:34');ui.fx_activate(30);nodes[34]=nil
ui.fx_regions(area,0,0,4);assert(not state.editing,'Removed native controls must leave selector mode')
-- Duplicate parameter names must disable inferred rotary binding.
names[2]='Wet';ui.fx_regions(area,0,0,5)
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.hwnd~=39 or (n.kind=='edit' and n.editor==40 and n.param==nil),'Ambiguous slider names must use their value field, not an arbitrary parameter') end end

-- Numbered parameter groups resolve only when the unprefixed label is unique.
nodes[38].title='Shift (full range):';names[1]='1: Shift (full range)';names[2]='Dry'
ui.fx_regions(area,0,0,6);assert(choose('plugin','native:39').param==0)
names[2]='2: Shift (full range)';ui.fx_regions(area,0,0,7)
local fallback=choose('plugin','native:39');assert(fallback.kind=='edit' and fallback.editor==40 and fallback.param==nil)
assert(fallback.slider==39 and choose('plugin','native:40').slider==39)
local focus,events=6,{}
reaper.JS_Window_GetFocus=function() return focus end
reaper.JS_Window_SetFocus=function(hwnd) focus=hwnd end
reaper.JS_Window_GetClientRect=function(hwnd) local r=nodes[hwnd].rect;return true,0,0,r[3]-r[1],r[4]-r[2] end
local send=reaper.JS_WindowMessage_Send
reaper.JS_WindowMessage_Send=function(hwnd,msg,low,high,x,y)
 if msg=='WM_LBUTTONDOWN' or msg=='WM_MOUSEMOVE' or msg=='WM_LBUTTONUP' then
  assert(hwnd==39 and x>=0 and x<=150 and y>=0 and y<=25)
  events[#events+1]=msg;focus=39
 end
 return send(hwnd,msg,low,high,x,y)
end
assert(ui.fx_native_absolute(30,.8) and #events==3 and focus==6)
assert(events[1]=='WM_LBUTTONDOWN' and events[3]=='WM_LBUTTONUP')
nodes[39].style=0x08000000
assert(not ui.fx_native_absolute(30,.2) and #events==3,'Disabled slider must not receive input')
nodes[39].style=0;nodes[39].parent=nil
assert(not ui.fx_native_absolute(30,.2) and #events==3,'Foreign slider must not receive input')
nodes[39].parent=2
choose('plugin','native:39')
nodes[40].title='0';ui.fx_activate(30)
assert(nodes[40].title=='0.75' and commands[#commands].pointer==40,'Slider editor must notify the paired value field')
add(43,2006,'Edit','0',2,390,105,50,25);ui.fx_regions(area,0,0,8)
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.hwnd~=39,'Ambiguous adjacent editors must not be guessed') end end
nodes[43]=nil;nodes[40].style=0x800;ui.fx_regions(area,0,0,9)
for _,r in ipairs(state.regions) do for _,n in ipairs(r.nodes) do assert(n.hwnd~=39,'Read-only value fields cannot make a slider editable') end end

-- ReaPitch's displayed labels differ from automation labels and repeat per tab.
nodes={}
add(1,0,'unknown','',nil,0,0,960,540)
add(2,0,'unknown','',1,150,45,800,490)
add(3,0,'unknown','',2,150,90,700,440)
add(4,1192,'Button','UI',2,700,50,40,25)
add(5,1422,'Button','Param',2,600,50,70,25)
add(6,1100,'Button','ReaPitch',3,150,90,690,430);nodes[6].style=0x20000000
add(7,1026,'SysTabControl32','',3,240,90,590,400)
add(8,0,'unknown','',3,240,115,590,370)
local ids={1075,1076,1077,1078,1083,1079,1080,1081,1082}
for i,id in ipairs(ids) do add(10+i,id,'REAPERhfader','',8,400,120+(i-1)*34,200,25) end
names={'Wet','Dry'}
for group=1,2 do
 for _,name in ipairs({'Enabled','Shift (full range)','Shift (cents)','Shift (semitones)','Shift (oct)','Formant adjust (full range)','Formant adjust (cents)','Formant adjust (semitones)','Volume','Pan'}) do names[#names+1]=group..': '..name end
end
names[23],names[24],names[25]='Bypass','Wet','Delta'
local notify_stamp,released=0,false
reaper.JS_WindowMessage_Intercept=function() return 1 end
reaper.JS_WindowMessage_Peek=function() return true,true,notify_stamp end
reaper.JS_WindowMessage_Release=function(_,message) assert(message=='WM_NOTIFY');released=true end
plugin='/opt/reapitch.vst.so<1'
reaper.TrackFX_GetFXGUID=function() return '{pitch-guid}' end
reaper.TrackFX_GetParamIdent=function(_,_,p) return p>=22 and ({'22:bypass','23:wet','24:delta'})[p-21] or tostring(p) end
ui.fx_regions(area,0,0,10);ui.fx_prepare(30,10)
local slider=choose('plugin','pitch:1083');assert(slider.param==7 and slider.ready==false)
assert(ui.fx_activate(30):find('Selecting shifter'))
ui.fx_regions(area,0,0,10.2);ui.fx_prepare(30,10.2);assert(choose('plugin','pitch:1083').ready)
local tabs=choose('plugin','pitch:shifter');assert(tabs.rect[4]==24)
ui.fx_activate(30);ui.fx_step(30,'right');assert(state.shifter==1)
ui.fx_regions(area,0,0,11);ui.fx_prepare(30,11);assert(choose('plugin','pitch:1083').ready==false)
ui.fx_regions(area,0,0,11.2);ui.fx_prepare(30,11.2)
for i,id in ipairs(ids) do local n=choose('plugin','pitch:'..id);assert(n.param==i+12 and n.ready) end
choose('plugin','pitch:shifter');ui.fx_cancel(30);assert(state.shifter==0)
ui.fx_regions(area,0,0,12);ui.fx_prepare(30,12);ui.fx_regions(area,0,0,12.2);ui.fx_prepare(30,12.2)
for i,id in ipairs(ids) do assert(choose('plugin','pitch:'..id).param==i+2) end
-- A native tab change replaces the panel: reselect the controller's shifter and
-- block rotary input until that panel has settled.
add(40,0,'unknown','',3,240,115,590,370)
for i=1,9 do nodes[10+i].parent=40 end
ui.fx_regions(area,0,0,13);ui.fx_prepare(30,13);assert(choose('plugin','pitch:1083').ready==false)
ui.fx_regions(area,0,0,13.2);ui.fx_prepare(30,13.2);assert(choose('plugin','pitch:1083').ready)
notify_stamp=1;ui.fx_regions(area,0,0,14);ui.fx_prepare(30,14)
assert(choose('plugin','pitch:1083').ready==false,'Tab notifications must gate unchanged native handles too')
ui.fx_regions(area,0,0,14.2);ui.fx_prepare(30,14.2);assert(choose('plugin','pitch:1083').ready)
ui.close();assert(released,'Owned message monitoring must be released on exit')
nodes[6]=nil;ui.fx_regions(area,0,0,15);ui.fx_prepare(30,15);assert(not state.pitch,'Generic UI must stop preparing a closed custom tab')
-- Opaque plugin editors have a generic list, including parameters above 255.
local opaque_root=nodes[1];nodes={[1]=opaque_root}
add(2,0,'__swell_xbridgewndclass','',1,150,80,700,450)
plugin='/opt/opaque.vst3';names={}
for i=1,301 do names[i]='Blank' end
names[1]='Gain';names[5]='Tone';names[300]='Gain';names[301]='MIDI CC 0|1'
reaper.TrackFX_GetParamIdent=function(_,_,p) return true,tostring(p) end
ui.fx_memory[30]=nil;regions=ui.fx_regions(area,0,0,16);state=ui.fx_memory[30]
assert(#regions==1 and regions[1].key=='parameters' and #regions[1].nodes==3)
local current=ui.fx_current(30);assert(current.list_only and current.param==0 and current.label=='Gain')
ui.fx_move(30,'down',spatial);assert(ui.fx_current(30).param==4)
ui.fx_move(30,'right',spatial);assert(ui.fx_current(30).param==299,'Keep original indices after filtering')
ui.fx_move(30,'right',spatial);assert(ui.fx_current(30).param==299)
ui.fx_move(30,'left',spatial);assert(ui.fx_current(30).param==4)
local before_commands=#commands;ui.fx_activate(30);assert(#commands==before_commands,'Virtual entries must never send native commands')
names[5]='Blank';ui.fx_regions(area,0,0,17);assert(ui.fx_current(30).param==0,'Removed parameters cannot remain selected')
names[1]='Blank';names[300]='Blank';ui.fx_regions(area,0,0,18);assert(not ui.fx_current(30))
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
