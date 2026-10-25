-- Value controls painted inside REAPER's transport; native APIs and actions only.
local transport = {}
local automation = {
  {-1,'No override'}, {0,'Trim/read'}, {1,'Read'}, {2,'Touch'},
  {4,'Latch'}, {3,'Write'}, {5,'Bypass'}, {6,'Latch preview'}
}
local timebases = {{43461,'Time'},{43462,'Beats: position, length, rate'},
                  {43463,'Beats: position only'},{43640,'Beats: auto-stretch'}}
local denominators = {1,2,4,8,16,32}
local function clamp(value,low,high) return math.max(low,math.min(high,value)) end
local function signature() return reaper.TimeMap_GetTimeSigAtTime(0,reaper.GetCursorPosition()) end
local function timebase_index()
  local mode=reaper.GetSetProjectInfo(0,'PROJECT_TIMEBASE',0,false)
  local flags=reaper.GetSetProjectInfo(0,'PROJECT_TIMEBASE_FLAGS',0,false)
  return mode==0 and 1 or mode==2 and 3 or (math.floor(flags)&2)~=0 and 4 or 2
end
local function index_of(values,value,column)
  for i,entry in ipairs(values) do if (column and entry[column] or entry)==value then return i end end
  return 1
end
local function set_signature(numerator,denominator)
  local position=reaper.GetCursorPosition()
  local _,_,bpm=signature()
  local index=reaper.FindTempoTimeSigMarker(0,position)
  local linear=false
  if index>=0 then
    local ok,time,_,_,_,_,_,ramp=reaper.GetTempoTimeSigMarker(0,index)
    if ok and math.abs(time-position)<.000001 then linear=ramp else index=-1 end
  end
  reaper.Undo_BeginBlock()
  reaper.SetTempoTimeSigMarker(0,index,position,-1,-1,bpm,numerator,denominator,linear)
  reaper.Undo_EndBlock('Gamepad: time signature',-1)
end
function transport.is_field(command) return command and command>=60001 and command<=60005 end
function transport.describe(command)
  if command==60001 then
    return automation[index_of(automation,reaper.GetGlobalAutomationOverride(),1)][2]
  elseif command==60002 then
    local _,_,bpm=signature();return string.format('%.2f BPM',bpm)
  elseif command==60003 then
    local n,d=signature();return n..'/'..d..' at edit cursor'
  elseif command==60004 then return string.format('%.3fx',reaper.Master_GetPlayRate(0))
  elseif command==60005 then return timebases[timebase_index()][2] end
end
function transport.choices(command)
  local choices={}
  if command==60001 then
    for _,entry in ipairs(automation) do
      local mode,label=entry[1],entry[2]
      choices[#choices+1]={label,function() reaper.SetGlobalAutomationOverride(mode) end}
    end
  elseif command==60005 then
    for _,entry in ipairs(timebases) do
      local id,label=entry[1],entry[2]
      choices[#choices+1]={label,function() reaper.Main_OnCommand(id,0) end}
    end
  else return end
  return choices
end
function transport.step(command,direction,fine)
  local delta=(direction=='right' or direction=='up') and 1 or -1
  if command==60001 then
    local index=index_of(automation,reaper.GetGlobalAutomationOverride(),1)
    reaper.SetGlobalAutomationOverride(automation[clamp(index+delta,1,#automation)][1])
  elseif command==60002 then
    local _,_,bpm=signature();reaper.SetCurrentBPM(0,clamp(bpm+delta*(fine and .1 or 1),1,960),true)
  elseif command==60003 then
    local n,d=signature()
    if direction=='up' or direction=='down' then n=clamp(n+delta,1,32)
    else d=denominators[clamp(index_of(denominators,d)+delta,1,#denominators)] end
    set_signature(n,d)
  elseif command==60005 then
    reaper.Main_OnCommand(timebases[clamp(timebase_index()+delta,1,#timebases)][1],0)
  end
end
function transport.absolute(command,value)
  if command==60004 then reaper.CSurf_OnPlayRateChange(2^(clamp(value,0,1)*4-2)) end
end
function transport.edit(command)
  local choices=transport.choices(command)
  if choices then return choices end
  local title,captions,defaults,count
  if command==60002 then
    local _,_,bpm=signature();title,captions,defaults,count='Tempo','BPM',tostring(bpm),1
  elseif command==60003 then
    local n,d=signature();title,captions,defaults,count='Time signature at edit cursor','Numerator,Denominator',n..','..d,2
  elseif command==60004 then
    title,captions,defaults,count='Playback rate','Rate (0.1 to 4)',tostring(reaper.Master_GetPlayRate(0)),1
  else return end
  local accepted,text=reaper.GetUserInputs(title,count,captions,defaults)
  if not accepted then return end
  if command==60003 then
    local a,b=text:match('^%s*(%d+)%s*,%s*(%d+)%s*$');a,b=tonumber(a),tonumber(b)
    if not a or a<1 or a>32 or not b or not table.concat(denominators,','):find('%f[%d]'..b..'%f[^%d]') then
      return nil,'Use a numerator from 1–32 and denominator 1, 2, 4, 8, 16 or 32'
    end
    set_signature(a,b)
  else
    local value=tonumber(text)
    local low,high=command==60002 and 1 or .1,command==60002 and 960 or 4
    if not value or value~=value or value<low or value>high then return nil,'Value must be between '..low..' and '..high end
    if command==60002 then reaper.SetCurrentBPM(0,value,true) else reaper.CSurf_OnPlayRateChange(value) end
  end
end
return transport
