-- Compact REAPER-native controller display and action menu. ReaLearn performs
-- input mapping, context switching and parameter control; this script supplies
-- visible feedback and a few stock operations that need object-aware handling.
reaper.set_action_options(2) -- Ignore duplicate launches from the startup timer.
local runtime = os.getenv('XDG_RUNTIME_DIR')
if not runtime then return end
local directory = runtime .. '/minion-gamepad/'
local choose_control = dofile(reaper.GetResourcePath() .. '/Scripts/Device/reaper-control-navigation.lua')
local ui = dofile(reaper.GetResourcePath() .. '/Scripts/Device/reaper-ui.lua')
local transport = dofile(reaper.GetResourcePath() .. '/Scripts/Device/reaper-transport.lua')
local transport_choices, previous_transport_knob, previous_transport_sample = nil,nil,nil
local REQUEST_COUNT, PAGE_COUNT = 29, 5
local choosing_area, area_choice, area_held = false, 'Timeline', false
local last_main_area, main_page, active_window = 0, 0, nil
local visible, previous_mode, previous_page, menu, menu_index = false, '', -1, false, 0
local pages = {'Arrange', 'Mixer', 'FX','Toolbar','Transport'}
local old_track, old_fx = '', -1
local last_update = 0
local message, message_until = '', 0
local process = assert(io.open('/proc/self/stat'))
local pid = process:read('*l'):match('^(%d+)'); process:close()
local outline_path = directory .. 'reaper-outline-' .. pid
local outline_started, old_control = false, 0
local controls = {
  {name='Volume', widget='volume'}, {name='Pan', widget='pan'},
  {name='Mute', widget='mute', key='B_MUTE'}, {name='Solo', widget='solo', key='I_SOLO'},
  {name='Arm', widget='recarm', key='I_RECARM'},
  {name='Monitoring', widget='recmon', key='I_RECMON'}, {name='FX', widget='fx'}
}

local function status(text)
  message, message_until = text, reaper.time_precise() + 2
end

local function read(path)
  local f = io.open(path)
  if not f then return '' end
  local value = f:read('*a'); f:close()
  return value:gsub('%s+$', '')
end
local function write(path, text)
  local f = io.open(path .. '.tmp', 'w')
  if f then f:write(text); f:close(); os.rename(path .. '.tmp', path) end
end
local function find_controller()
  local master = reaper.GetMasterTrack(0)
  for index = 0, reaper.TrackFX_GetRecCount(master) - 1 do
    local fx = index + 0x1000000
    local _, name = reaper.TrackFX_GetNamedConfigParm(master, fx, 'renamed_name')
    if name == 'Device gamepad' then return master, fx end
  end
end
local function parameter(master, fx, index, count)
  return math.floor(reaper.TrackFX_GetParamNormalized(master, fx, index) * (count - 1) + .5)
end
local function set(master, fx, index, count, value)
  local normalized = value / (count - 1)
  if math.abs(reaper.TrackFX_GetParamNormalized(master, fx, index) - normalized) > .000001 then
    reaper.TrackFX_SetParamNormalized(master, fx, index, normalized)
  end
end
local function selected_track()
  return reaper.GetSelectedTrack(0, 0)
end
local function track_rectangle(track, widget)
  if not track then return end
  local ok, text = reaper.GetSetMediaTrackInfo_String(track, 'P_UI_RECT:tcp.' .. widget, '', false)
  if not ok then return end
  local x,y,w,h = text:match('^(-?%d+) (-?%d+) (%d+) (%d+)$')
  if x and tonumber(w) > 0 and tonumber(h) > 0 then
    return string.format('%d %d %d %d', x,y,w,h)
  end
end
local function control_rectangle(track, index)
  return track_rectangle(track, controls[index + 1].widget)
end
local function show_outline(rectangle, area, track_number, window_id)
  write(outline_path, rectangle and (rectangle .. (window_id and ' window '..window_id or area and ' area ' .. area .. ' ' .. track_number or '')) or '')
  if (rectangle or ui.available()) and not outline_started then
    local helper = reaper.GetResourcePath() .. '/Scripts/Device/reaper-control-outline.py'
    local function quote(value) return "'" .. value:gsub("'", "'\\''") .. "'" end
    reaper.ExecProcess('/usr/bin/python3 ' .. quote(helper) .. ' --pid ' .. pid .. ' --state ' .. quote(outline_path), -1)
    outline_started = true
  end
end
local function select_at_cursor()
  local track, cursor = selected_track(), reaper.GetCursorPosition()
  if track then
    for i = 0, reaper.CountTrackMediaItems(track) - 1 do
      local item = reaper.GetTrackMediaItem(track, i)
      local position = reaper.GetMediaItemInfo_Value(item, 'D_POSITION')
      if cursor >= position and cursor < position + reaper.GetMediaItemInfo_Value(item, 'D_LENGTH') then
        reaper.SelectAllMediaItems(0, false)
        reaper.SetMediaItemSelected(item, true)
        reaper.UpdateArrange()
        status('Selected item at cursor')
        return
      end
    end
  end
  status('No item at cursor on selected track')
end
local function split_items()
  local cursor = reaper.GetCursorPosition()
  for i = 0, reaper.CountSelectedMediaItems(0) - 1 do
    local item = reaper.GetSelectedMediaItem(0, i)
    local start = reaper.GetMediaItemInfo_Value(item, 'D_POSITION')
    if cursor > start and cursor < start + reaper.GetMediaItemInfo_Value(item, 'D_LENGTH') then
      reaper.Main_OnCommand(40757, 0)
      status('Split selected items')
      return
    end
  end
  status('Split: select an item and move the cursor inside it (R2 + D-pad)')
end
local function action(command)
  return function() reaper.Main_OnCommand(command, 0) end
end
local function toggle_track(key)
  local track = selected_track()
  if track then
    reaper.Undo_BeginBlock()
    reaper.SetMediaTrackInfo_Value(track, key, reaper.GetMediaTrackInfo_Value(track, key) == 0 and 1 or 0)
    reaper.TrackList_AdjustWindows(false)
    reaper.Undo_EndBlock('Gamepad: toggle ' .. key, -1)
  end
end
local function stock_fx(name)
  local track = selected_track()
  if track then
    reaper.Undo_BeginBlock()
    reaper.TrackFX_AddByName(track, name, false, -1)
    reaper.Undo_EndBlock('Gamepad: insert ' .. name, -1)
  end
end
local menus = {
  {{'Record / stop', action(1013)}, {'Insert track', action(40001)},
   {'Copy', action(40057)}, {'Paste', action(40058)}, {'Cut', action(40059)},
   {'Undo', action(40029)}, {'Redo', action(40030)},
   {'Split selected items', split_items}, {'Trim to time selection', action(40508)},
   {'Insert marker', action(40157)}, {'Toggle metronome', action(40364)},
   {'Remove selected items', action(40006)}},
  {{'Arm / disarm track', function() toggle_track('I_RECARM') end},
   {'Input monitoring on / off', function() toggle_track('I_RECMON') end},
   {'Mute / unmute', function() toggle_track('B_MUTE') end},
   {'Solo / unsolo', function() toggle_track('I_SOLO') end},
   {'Insert track', action(40001)}, {'Record / stop', action(1013)},
   {'Reset level to 0 dB', function() local t=selected_track();if t then reaper.SetMediaTrackInfo_Value(t,'D_VOL',1) end end},
   {'Center pan', function() local t=selected_track();if t then reaper.SetMediaTrackInfo_Value(t,'D_PAN',0) end end}},
  {{'Insert ReaEQ', function() stock_fx('ReaEQ (Cockos)') end},
   {'Insert ReaComp', function() stock_fx('ReaComp (Cockos)') end},
   {'Insert ReaGate', function() stock_fx('ReaGate (Cockos)') end},
   {'Insert ReaDelay', function() stock_fx('ReaDelay (Cockos)') end},
   {'Insert ReaVerbate', function() stock_fx('ReaVerbate (Cockos)') end}}, {}, {}
}

local function line(text, y, highlight)
  gfx.set(highlight and .55 or .88, highlight and .85 or .88, highlight and 1 or .88, 1)
  gfx.x, gfx.y = 12, y
  if gfx.measurestr(text) > gfx.w - 24 then
    while #text > 0 and gfx.measurestr(text .. '…') > gfx.w - 24 do
      local last = utf8.offset(text, -1)
      text = text:sub(1, last - 1)
    end
    text = text .. '…'
  end
  gfx.drawstr(text)
end
local function loop()
  local now = reaper.time_precise()
  if now - last_update < .05 then reaper.defer(loop); return end
  last_update = now
  local master, controller = find_controller()
  if not master then gfx.quit(); return end
  local page = math.min(PAGE_COUNT-1, parameter(master, controller, 0, PAGE_COUNT))
  local mode = read(directory .. 'mode')
  if mode ~= 'reaper' then
    choosing_area, menu, area_held, transport_choices = false, false, false, nil
    ui.cancel_focus(outline_path)
    ui.fx_band=nil
    set(master, controller, 9, 2, 0)
    set(master,controller,15,2,0)
    set(master, controller, 12, 3, 0)
    write(directory .. 'reaper-area', '')
    write(directory .. 'reaper-rotary-target', '')
    write(directory .. 'reaper-transport-field','')
    if outline_started then show_outline(nil) end
    if visible then gfx.quit(); visible = false end
    previous_mode = mode
    reaper.defer(loop); return
  end
  if not visible and previous_mode ~= mode then
    gfx.init('REAPER gamepad controls', 900, 190, 1)
    gfx.setfont(1, 'sans-serif', 24)
    visible = true
  end
  previous_mode = mode
  ui.scan(now,outline_path)
  if page~=2 then ui.fx_band=nil;main_page=page end
  local function adopt_window(area)
    if area.track then
      page=2
      reaper.SetOnlyTrackSelected(area.track)
      set(master,controller,1,128,area.fx)
      set(master,controller,2,65536,0)
      old_track,old_fx=reaper.GetTrackGUID(area.track),area.fx
      if area.region and ui.fx_memory[area.id] then ui.fx_memory[area.id].region=area.region end
    else
      page=area.window_switch and main_page or area.page
      main_page=page
      last_main_area=area.main or last_main_area
      if page<=1 then reaper.SetCursorContext(page==1 and 0 or 1,nil) end
    end
    active_window=area.id
    set(master,controller,0,PAGE_COUNT,page)
  end
  local focused_window=ui.focused_window()
  if focused_window and active_window~=focused_window.id and not ui.pending then
    ui.fx_cancel(active_window)
    choosing_area,menu,transport_choices=false,false,nil
    local target={}
    for key,value in pairs(focused_window) do target[key]=value end
    target.window_switch=true
    adopt_window(target)
    set(master,controller,9,2,0)
    reaper.defer(loop);return
  end
  for i,name in ipairs({'Toolbar','Transport'}) do
    menus[i+3]={}
    for _,button in ipairs(ui.buttons[name]) do
      local command=button.command
      menus[i+3][#menus[i+3]+1]={button.label,transport.is_field(command) and function() transport.edit(command) end or action(command)}
    end
    if name=='Transport' and transport_choices then menus[i+3]=transport_choices end
  end
  local track = selected_track()
  for _,entry in ipairs(ui.windows()) do
    if entry.id==active_window and entry.track and reaper.ValidatePtr2(0,entry.track,'MediaTrack*') and entry.track~=track then
      reaper.SetOnlyTrackSelected(entry.track);track=entry.track
    end
  end
  local guid = track and reaper.GetTrackGUID(track) or ''
  local track_changed = guid ~= old_track
  local fx_index = parameter(master, controller, 1, 128)
  local param_index = parameter(master, controller, 2, 65536)
  if guid ~= old_track then fx_index, param_index = 0, 0 end
  for _,entry in ipairs(ui.windows()) do
    if entry.id==active_window and entry.track==track and entry.kind=='chain' then
      local selected=reaper.TrackFX_GetChainVisible(track)
      if selected>=0 then fx_index=selected end
    end
  end
  local fx_count = track and reaper.TrackFX_GetCount(track) or 0
  fx_index = math.max(0, math.min(fx_index, fx_count - 1))
  if fx_index ~= old_fx then
    param_index = 0
    -- Navigation explicitly selects the effect. Observe the native selection
    -- here; showing it again can overwrite a selection still being applied.
  end
  local param_count = track and fx_count > 0 and reaper.TrackFX_GetNumParams(track, fx_index) or 0
  param_index = math.max(0, math.min(param_index, param_count - 1))
  set(master, controller, 1, 128, fx_index)
  set(master, controller, 2, 65536, param_index)
  old_track, old_fx = guid, fx_index
  local send = parameter(master, controller, 7, 128)
  local send_count = track and reaper.GetTrackNumSends(track, 0) or 0
  send = math.max(0, math.min(send, send_count - 1))
  set(master, controller, 7, 128, send)
  local control = parameter(master, controller, 8, #controls)
  if page == 1 then
    if track_changed or page ~= previous_page then reaper.Main_OnCommand(40913, 0) end -- Scroll selected track into view.
    if not control_rectangle(track, control) then
      local direction = control < old_control and -1 or 1
      for i=1,#controls do
        local candidate = (control + direction * i) % #controls
        if control_rectangle(track, candidate) then control = candidate; break end
      end
      set(master, controller, 8, #controls, control)
    end
  end
  old_control = control
  local window
  for _,entry in ipairs(ui.windows()) do if entry.id==active_window then window=entry end end
  local regions={}
  if window and window.track then
    regions=ui.fx_regions(window,fx_index,param_index,now)
    ui.fx_prepare(active_window,now)
  else
    for _,entry in ipairs(ui.areas) do if entry.id==active_window and entry.page~=2 and entry.rect then regions[#regions+1]=entry end end
  end
  local function chosen_area()
    for _,area in ipairs(regions) do if area.key==area_choice then return area end end
  end
  local function begin_area()
    if page==2 then ui.fx_cancel(active_window) end
    choosing_area,menu,transport_choices=true,false,nil
    if window and window.track then
      local state=ui.fx_memory[active_window]
      area_choice=state and state.region or 'plugin'
    else area_choice=page==0 and 'Timeline' or page==3 and 'Toolbar' or page==4 and 'Transport' or 'Tracks' end
    if not chosen_area() and regions[1] then area_choice=regions[1].key end
  end
  local function enter_area()
    if ui.pending then return end
    local area=chosen_area()
    if not area then choosing_area=false;status('Region closed or unavailable');return end
    ui.focus(outline_path,area,now)
  end
  local area,focused=ui.focus_result(outline_path,now)
  if area then
    choosing_area,menu=false,false
    if focused and (not area.track or reaper.ValidatePtr2(0,area.track,'MediaTrack*')) then
      adopt_window(area)
      reaper.defer(loop);return
    else status('Could not focus region; select it again') end
  end
  local function edit_transport_field(command)
    local choices,err=transport.edit(command)
    previous_transport_knob=parameter(master,controller,13,16384)
    previous_transport_sample=parameter(master,controller,14,65536)
    if err then status(err) end
    transport_choices,menu,menu_index=choices,choices~=nil,0
    if choices then menus[5]=choices end
    set(master,controller,4,32,0)
    set(master,controller,6,2,menu and 1 or 0)
  end
  local hold_state = parameter(master,controller,12,3)
  if hold_state == 2 and not area_held then
    begin_area()
  elseif hold_state == 1 then
    choosing_area = false
    ui.cancel_focus(outline_path)
    set(master,controller,12,3,0) -- Acknowledge cancellation without committing.
  end
  local request = parameter(master, controller, 3, REQUEST_COUNT)
  if request ~= 0 then
    set(master, controller, 3, REQUEST_COUNT, 0)
    if request==27 or request==28 then
      ui.fx_cancel(active_window)
      ui.scan_windows(outline_path)
      local next_window=ui.window_neighbor(active_window,request==27 and -1 or 1)
      if next_window then
        local target={}
        for key,value in pairs(next_window) do target[key]=value end
        target.window_switch=true
        choosing_area,menu=true,false
        ui.focus(outline_path,target,now)
      end
    elseif page==2 and window and window.track and not choosing_area and not menu and request==8 then
      local note=ui.fx_activate(active_window)
      if note then status(note) end
      reaper.defer(loop);return
    elseif page==2 and not choosing_area and not menu and request>=11 and request<=14 then
      local next_fx=ui.fx_move(active_window,({'left','right','up','down'})[request-10],choose_control)
      if next_fx then set(master,controller,1,128,next_fx);old_fx=-1;reaper.defer(loop);return end
    elseif page==2 and not choosing_area and not menu and request>=23 and request<=26 then
      local next_fx=ui.fx_step(active_window,({'left','right','up','down'})[request-22])
      if next_fx then set(master,controller,1,128,next_fx);old_fx=-1;reaper.defer(loop);return end
    elseif request == 15 then
      if page==2 and ui.fx_cancel(active_window) then
      elseif menu then menu = false
      elseif choosing_area then enter_area()
      else
        begin_area()
      end
    elseif choosing_area and request == 16 then enter_area()
    elseif choosing_area and request == 17 then choosing_area = false;ui.cancel_focus(outline_path)
    elseif choosing_area and request >= 18 and request <= 21 then
      if not ui.pending then
        local rectangles,index={},nil
        for i,entry in ipairs(regions) do rectangles[i]=entry.rect or false;if entry.key==area_choice then index=i-1 end end
        if index then area_choice=regions[choose_control(rectangles,index,({'left','right','up','down'})[request-17])+1].key end
      end
    elseif request == 1 then choosing_area = false; menu = not menu; menu_index = 0; set(master,controller,4,32,0)
    elseif request == 2 and menu then
      local entry = menus[page + 1][menu_index + 1]
      local choices=transport_choices
      menu,transport_choices = false,nil
      set(master,controller,6,2,0)
      local field=page==4 and ui.buttons.Transport[menu_index+1]
      if not choices and field and transport.is_field(field.command) then
        edit_transport_field(field.command)
      elseif page >= 3 and not choices then reaper.defer(loop);return -- Native action already invoked.
      elseif entry then entry[2]() end
      -- Reacquire selection pointers after an action changes project contents.
      reaper.defer(loop);return
    elseif request == 5 then menu,transport_choices = false,nil
    elseif page==4 and request==22 then
      local button=ui.current('Transport')
      if button then
        edit_transport_field(button.command)
        reaper.defer(loop);return
      end
    elseif page==4 and request>=23 and request<=26 then
      local button=ui.current('Transport')
      if button then transport.step(button.command,({'left','right','up','down'})[request-22],parameter(master,controller,5,2)==1) end
    elseif request == 3 then
      if page == 0 then split_items()
      elseif page == 1 then toggle_track('B_MUTE')
      elseif track and fx_count > 0 then reaper.TrackFX_SetEnabled(track, fx_index, not reaper.TrackFX_GetEnabled(track, fx_index)) end
    elseif request == 4 then
      if page == 0 then reaper.Main_OnCommand(1068, 0)
      elseif page == 1 then toggle_track('I_SOLO')
      elseif track and fx_count > 0 then
        reaper.TrackFX_Show(track, fx_index, reaper.TrackFX_GetFloatingWindow(track, fx_index) and 2 or 3)
      end
    elseif request == 6 then select_at_cursor()
    elseif request == 7 then
      reaper.Undo_BeginBlock()
      for i = 0, reaper.CountSelectedTracks(0) - 1 do
        local t = reaper.GetSelectedTrack(0, i)
        reaper.SetMediaTrackInfo_Value(t, 'I_RECMON', reaper.GetMediaTrackInfo_Value(t, 'I_RECMON') == 0 and 1 or 0)
      end
      reaper.Undo_EndBlock('Gamepad: input monitoring', -1)
    elseif page >= 3 and request >= 11 and request <= 14 then
      ui.move(pages[page+1],({'left','right','up','down'})[request-10],choose_control)
    elseif page == 1 and request >= 11 and request <= 14 then
      local rectangles = {}
      for i=0,#controls-1 do
        local text = control_rectangle(track, i)
        local rect = false
        if text then
          local x,y,w,h = text:match('^(-?%d+) (-?%d+) (%d+) (%d+)$')
          rect = {tonumber(x),tonumber(y),tonumber(w),tonumber(h)}
        end
        rectangles[i + 1] = rect
      end
      control = choose_control(rectangles, control, ({'left','right','up','down'})[request - 10])
      old_control = control
      set(master, controller, 8, #controls, control)
    elseif page == 1 and request >= 8 and request <= 10 then
      local entry = controls[control + 1]
      if track and entry.key then
        local current = reaper.GetMediaTrackInfo_Value(track, entry.key)
        local value = request == 8 and (current == 0 and 1 or 0) or (request == 10 and 1 or 0)
        if current ~= value then
          reaper.Undo_BeginBlock()
          reaper.SetMediaTrackInfo_Value(track, entry.key, value)
          reaper.TrackList_AdjustWindows(false)
          reaper.Undo_EndBlock('Gamepad: ' .. entry.name, -1)
        end
      elseif track and control == 6 and request == 8 then
        set(master, controller, 0, PAGE_COUNT, 2)
        reaper.TrackFX_Show(track,fx_index,1) -- Empty chains still expose Add FX.
      end
    end
  end
  -- Process the last spatial move before a release commits the selection.
  if hold_state == 0 and area_held and choosing_area then enter_area() end
  area_held = hold_state == 2
  if page ~= previous_page then menu,transport_choices = false,nil; previous_page = page end
  set(master, controller, 6, 2, menu and 1 or 0)
  set(master, controller, 9, 2, choosing_area and 1 or 0)
  set(master, controller, 10, 4, last_main_area) -- Legacy main-area display metadata.
  menu_index = math.max(0,math.min(#menus[page + 1] - 1, parameter(master, controller, 4, 32)))
  set(master, controller, 4, 32, menu_index)
  local native_button = page >= 3 and not transport_choices and (menu and ui.buttons[pages[page+1]][menu_index+1] or ui.current(pages[page+1]))
  local knob=parameter(master,controller,13,16384)
  local sample=parameter(master,controller,14,65536)
  if page==4 and not choosing_area and not menu and native_button and native_button.command==60004 then
    if previous_transport_knob~=nil and (knob~=previous_transport_knob or sample~=previous_transport_sample) then transport.absolute(60004,knob/16383) end
  end
  previous_transport_knob,previous_transport_sample=knob,sample
  set(master,controller,11,65536,native_button and native_button.command or 0)
  local fx_node,fx_state,fx_region
  if window and window.track then fx_node,fx_state,fx_region=ui.fx_current(active_window) end
  local fx_ready,fx_note=not fx_node or fx_node.ready~=false,''
  if not fx_ready then fx_note='Selecting shifter '..((fx_state.shifter or 0)+1) end
  if page==2 and not choosing_area and not menu and fx_node and fx_node.band~=nil then
    local rectangle,_,note=ui.fx_outline(track,fx_index,fx_node.param,now)
    fx_ready=rectangle~=nil;fx_note=note or ''
  end
  local fx_knob=page==2 and not choosing_area and not menu and fx_ready and fx_node and fx_node.kind=='param' and fx_node.param~=nil
  set(master,controller,15,2,fx_knob and 1 or 0)
  if fx_knob then param_index=fx_node.param;set(master,controller,2,65536,param_index) end
  if choosing_area then
    local area=chosen_area()
    local rect=area and area.rect
    show_outline(rect and table.concat(rect,' '),nil,nil,area and area.id)
  elseif page==2 and not menu then
    show_outline(fx_node and not fx_node.list_only and fx_ready and table.concat(fx_node.rect,' '),nil,nil,active_window)
  elseif page >= 3 and not menu then
    local button=ui.current(pages[page+1])
    show_outline(button and table.concat(button.rect,' '))
  else
    show_outline(mode == 'reaper' and page == 1 and not menu and control_rectangle(track, control) or nil)
  end
  local _, name = track and reaper.GetTrackName(track) or false, ''
  if track then _, name = reaper.GetTrackName(track) end
  local summary = track and string.format('%d: %s%s', reaper.GetMediaTrackInfo_Value(track, 'IP_TRACKNUMBER'), name,
    reaper.GetMediaTrackInfo_Value(track, 'I_RECARM') == 1 and ' [ARMED]' or '') or 'No selected track — B + Up: Insert track'
  local detail = ''
  if page >= 3 then
    local button=ui.current(pages[page+1])
    local value=button and transport.describe(button.command)
    detail=button and ('< '..button.label..' >  '..(value and (value..'  R: adjust  A: edit') or 'A: activate')) or 'Locating visible native buttons'
  elseif page == 1 and track then
    local volume = reaper.GetMediaTrackInfo_Value(track, 'D_VOL')
    local entry = controls[control + 1]
    local value = control == 0 and string.format('%.1f dB',20 * math.log(math.max(volume,1e-10),10)) or control == 1 and string.format('%.0f%%',reaper.GetMediaTrackInfo_Value(track,'D_PAN') * 100) or entry.key and (reaper.GetMediaTrackInfo_Value(track,entry.key) == 0 and 'OFF' or 'ON') or 'A: open effects'
    detail = '< ' .. entry.name .. ' >  ' .. value
  elseif page==2 then
    if fx_node then
      local value=''
      if fx_node.param~=nil and track and fx_count>0 then
        local _,text=reaper.TrackFX_GetFormattedParamValue(track,fx_index,fx_node.param,'');value=text
      elseif fx_node.kind=='effects' then
        if fx_count>0 then local ok;ok,value=reaper.TrackFX_GetFXName(track,fx_index,'') else value='Empty' end
      elseif fx_node.kind=='combo' then value=reaper.JS_Window_GetTitle(fx_node.hwnd)
      elseif fx_node.kind=='edit' then value=reaper.JS_Window_GetTitle(fx_node.editor or fx_node.hwnd)
      elseif fx_node.kind=='list' then
        local selected=reaper.JS_ListView_EnumSelItems(fx_node.hwnd,-1)
        value=selected>=0 and reaper.JS_ListView_GetItemText(fx_node.hwnd,selected,0) or 'No selection'
      elseif fx_node.kind=='toggle' then value=reaper.JS_WindowMessage_Send(fx_node.hwnd,'BM_GETCHECK',0,0,0,0)==0 and 'OFF' or 'ON' end
      detail=fx_region.label..' > '..fx_node.label..(value~='' and ': '..value or '')
      if not fx_ready then detail=detail..' | '..fx_note end
      if fx_state.editing then detail=detail..' | Choose with L / D-pad; A accept; B cancel'
      elseif fx_node.kind=='effects' then detail=detail..' | Up/down: effect; A: controls'
      elseif fx_node.kind=='param' then detail=detail..(fx_node.list_only and ' | L: choose; R: adjust' or ' | R: adjust')
      elseif fx_node.kind=='edit' then detail=detail..' | A: edit value'
      else detail=detail..' | A: activate / choose' end
    else detail='No mapped controls in this window; L2: choose a region' end
  elseif page == 0 then
    local count = reaper.CountSelectedMediaItems(0)
    local item = reaper.GetSelectedMediaItem(0, 0)
    local take = item and reaper.GetActiveTake(item)
    detail = item and string.format('%d selected | %s @ %.2fs', count, take and reaper.GetTakeName(take) or 'Empty item',
      reaper.GetMediaItemInfo_Value(item, 'D_POSITION')) or 'No item selected — D-pad left/right: choose item; A: select at cursor'
    if now < message_until then detail = message end
  end
  if now < message_until then detail=message end
  write(directory .. 'reaper-page', pages[page + 1])
  local rotary_target = ''
  if not menu and not choosing_area then
    if page==4 and native_button and native_button.command==60004 then
      rotary_target=pid..':transport:playrate'
    elseif page == 1 and track and control <= 1 then
      rotary_target = pid .. ':' .. guid .. ':control:' .. control
    elseif fx_knob and track and fx_count>0 then
      rotary_target = pid .. ':' .. tostring(active_window) .. ':' .. guid .. ':' .. reaper.TrackFX_GetFXGUID(track,fx_index) .. ':' .. param_index .. ':' .. fx_node.label
    end
  end
  write(directory .. 'reaper-rotary-target', rotary_target)
  write(directory .. 'reaper-transport-field',page==4 and not menu and not choosing_area and native_button and transport.is_field(native_button.command) and tostring(native_button.command) or '')
  write(directory .. 'reaper-area', choosing_area and (chosen_area() and chosen_area().label or 'Area closed') or '')
  write(directory .. 'reaper-context', (choosing_area and 'areas' or menu and 'menu' or 'page') .. '\n' .. summary .. '\n' .. (choosing_area and ('Choose area: ' .. (chosen_area() and chosen_area().label or 'Area closed')) or detail))
  if visible then
    local key = gfx.getchar()
    if key == -1 then gfx.quit();visible = false
    else
      gfx.set(.09,.10,.12,1);gfx.rect(0,0,gfx.w,gfx.h,1)
      local row = math.max(12, math.min(30, (gfx.h - 8) / 4))
      gfx.setfont(1, 'sans-serif', math.max(10, math.min(18, row * .78)))
      line(choosing_area and ('Choose area: ' .. (chosen_area() and chosen_area().label or 'Area closed')) or ('[' .. pages[page + 1] .. ']  ' .. summary), 4, true)
      if choosing_area then
        line('Stick / D-pad: regions in this window',4+row)
        line('Release L2 / A: enter     B: cancel     Right stick: inactive',4+2*row)
        line('L1/R1 switch REAPER windows outside the picker',4+3*row)
        if key == 13 then set(master,controller,3,REQUEST_COUNT,16)
        elseif key == 27 then set(master,controller,3,REQUEST_COUNT,17) end
      elseif menu then
        line('A: run   B/L3: back   D-pad: choose', 4 + row)
        for offset=0,1 do local item=menus[page + 1][menu_index+offset+1];if item then line((offset==0 and '> ' or '  ') .. item[1],4+(offset+2)*row,offset==0) end end
        if key == 13 then set(master,controller,3,REQUEST_COUNT,2) elseif key==27 then menu=false end
      elseif page==2 and fx_node and fx_node.list_only then
        local position=1
        for i,node in ipairs(fx_region.nodes) do if node.key==fx_node.key then position=i end end
        line(position..'/'..#fx_region.nodes..'  '..detail,4+row,true)
        local previous,next=fx_region.nodes[position-1],fx_region.nodes[position+1]
        line((previous and previous.label or 'Start')..'  < >  '..(next and next.label or 'End'),4+2*row)
        line('L / D: parameter   R: value   L2: regions   L1/R1: window',4+3*row)
      else
        local controls = {'D: item/track   R2+D: cursor   L: scroll   R: zoom',
                          'L: outline in 2D  D up/down: track  R angle: knob  A: activate',
                          'L / D: move between controls   R: adjust   A: activate',
                          'L / D-pad: choose button   A: activate   B: choose area',
                          'L / D-pad: choose button   A: activate   B: choose area'}
        local buttons = {'X: split  R3: loop', 'X: mute  R3: solo', 'X: bypass  R3: FX window','',''}
        line(detail ~= '' and detail or controls[page + 1], 4 + row)
        line(detail ~= '' and controls[page + 1] or 'Y: play/stop   Start: save   R center: retain knob value', 4 + 2*row)
        line(buttons[page + 1] .. ' | L2: areas  L3: actions  L1/R1: window', 4 + 3*row)
      end
      gfx.update()
    end
  end
  reaper.defer(loop)
end
reaper.atexit(function() ui.close(); gfx.quit(); write(directory .. 'reaper-page', ''); os.remove(directory .. 'reaper-area'); os.remove(directory .. 'reaper-rotary-target'); os.remove(directory .. 'reaper-transport-field'); ui.cancel_focus(outline_path);os.remove(outline_path) end)
reaper.defer(loop)
