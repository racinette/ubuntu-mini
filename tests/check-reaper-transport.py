#!/usr/bin/python3
"""Exercise painted transport controls through Lua with isolated native API stubs."""
import ctypes as C
import ctypes.util
import json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
code=r'''
local state={auto=-1,bpm=120,n=4,d=4,rate=1,base=1,flags=0,cursor=0}
local answer={false,''}
local saved
reaper={
 GetGlobalAutomationOverride=function() return state.auto end,
 SetGlobalAutomationOverride=function(value) state.auto=value end,
 TimeMap_GetTimeSigAtTime=function() return state.n,state.d,state.bpm end,
 GetCursorPosition=function() return state.cursor end,
 SetCurrentBPM=function(_,value) state.bpm=value end,
 Master_GetPlayRate=function() return state.rate end,
 CSurf_OnPlayRateChange=function(value) state.rate=value end,
 GetSetProjectInfo=function(_,key) return key=='PROJECT_TIMEBASE' and state.base or state.flags end,
 Main_OnCommand=function(id)
   if id==43461 then state.base,state.flags=0,0
   elseif id==43462 then state.base,state.flags=1,0
   elseif id==43463 then state.base,state.flags=2,0
   elseif id==43640 then state.base,state.flags=1,2 else error('Unexpected command '..id) end
 end,
 FindTempoTimeSigMarker=function() return state.marker and 2 or -1 end,
 GetTempoTimeSigMarker=function() return true,state.marker,-1,-1,state.bpm,state.n,state.d,true end,
 SetTempoTimeSigMarker=function(_,index,time,measure,beat,bpm,n,d,ramp)
   saved={index=index,time=time,n=n,d=d,ramp=ramp};state.n,state.d=n,d;return true
 end,
 Undo_BeginBlock=function() end,Undo_EndBlock=function() end,
 GetUserInputs=function() return table.unpack(answer) end
}
local t=dofile(MODULE)
assert(t.is_field(60001) and t.is_field(60005) and not t.is_field(40023))
local choices=t.edit(60001);assert(#choices==8)
for index,mode in ipairs({-1,0,1,2,4,3,5,6}) do choices[index][2]();assert(state.auto==mode) end
state.auto=-1;t.step(60001,'right');assert(state.auto==0);t.step(60001,'left');assert(state.auto==-1)
t.step(60001,'left');assert(state.auto==-1)
t.step(60002,'right');assert(state.bpm==121)
t.step(60002,'down',true);assert(math.abs(state.bpm-120.9)<.00001)
state.bpm=1;t.step(60002,'left');assert(state.bpm==1)
state.bpm=960;t.step(60002,'right');assert(state.bpm==960)
state.bpm=120
t.step(60003,'up');assert(saved.index==-1 and saved.n==5 and saved.d==4 and saved.time==0)
t.step(60003,'right');assert(state.d==8)
state.marker,state.cursor=10,10;t.step(60003,'down');assert(saved.index==2 and saved.ramp)
state.cursor=12;t.step(60003,'up');assert(saved.index==-1 and saved.time==12)
state.marker=nil
t.absolute(60004,0);assert(state.rate==.25)
t.absolute(60004,.5);assert(state.rate==1)
t.absolute(60004,1);assert(state.rate==4)
choices=t.edit(60005);assert(#choices==4)
for i=1,4 do choices[i][2]();assert(t.describe(60005)==choices[i][1]) end
t.step(60005,'left');assert(state.base==2)
t.step(60005,'right');assert(state.base==1 and state.flags==2)
answer={true,'132.5'};t.edit(60002);assert(state.bpm==132.5)
for _,text in ipairs({'0','961','nan','inf','hello'}) do
 answer={true,text};local _,err=t.edit(60002);assert(err and state.bpm==132.5)
end
answer={false,'150'};t.edit(60002);assert(state.bpm==132.5)
answer={true,'7,8'};t.edit(60003);assert(state.n==7 and state.d==8)
for _,text in ipairs({'0,4','33,4','4,3','4,0','4.5,4','four,four'}) do
 answer={true,text};local _,err=t.edit(60003);assert(err and state.n==7 and state.d==8)
end
answer={true,'0.75'};t.edit(60004);assert(state.rate==.75)
answer={true,'0'};local _,err=t.edit(60004);assert(err and state.rate==.75)
assert(t.describe(60002):find('132.50') and t.describe(60003):find('7/8'))
print('Passed: native transport adjustments, choices, logarithmic rate angle, cursor-local signature updates, bounds and editor cancellation/validation.')
'''.replace('MODULE',json.dumps(str(PROJECT/'setup/development/reaper-transport.lua')))
lua=C.CDLL(ctypes.util.find_library('lua5.4') or 'liblua5.4.so.0')
lua.luaL_newstate.restype=C.c_void_p
lua.luaL_openlibs.argtypes=[C.c_void_p]
lua.luaL_loadstring.argtypes=[C.c_void_p,C.c_char_p]
lua.lua_pcallk.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ssize_t,C.c_void_p]
lua.lua_tolstring.argtypes=[C.c_void_p,C.c_int,C.c_void_p];lua.lua_tolstring.restype=C.c_char_p
lua.lua_close.argtypes=[C.c_void_p]
state=lua.luaL_newstate()
try:
    lua.luaL_openlibs(state)
    result=lua.luaL_loadstring(state,code.encode()) or lua.lua_pcallk(state,0,0,0,0,None)
    if result: raise AssertionError(lua.lua_tolstring(state,-1,None).decode())
finally:lua.lua_close(state)
