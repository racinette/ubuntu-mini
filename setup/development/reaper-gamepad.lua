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
local REQUEST_COUNT, PAGE_COUNT = 27, 5
local choosing_area, area_choice, area_held, opened_area_fx = false, 0, false, nil
local area_names = {'Timeline','Tracks','Toolbar','Transport'}
local area_pages = {0,1,3,4}
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
local function show_outline(rectangle, area, track_number)
  write(outline_path, rectangle and (rectangle .. (area and ' area ' .. area .. ' ' .. track_number or '')) or '')
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
    set(master, controller, 9, 2, 0)
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
  for i,name in ipairs({'Toolbar','Transport'}) do
    menus[i+3]={}
    for _,button in ipairs(ui.buttons[name]) do
      local command=button.command
      menus[i+3][#menus[i+3]+1]={button.label,transport.is_field(command) and function() transport.edit(command) end or action(command)}
    end
    if name=='Transport' and transport_choices then menus[i+3]=transport_choices end
  end
  local track = selected_track()
  local guid = track and reaper.GetTrackGUID(track) or ''
  local track_changed = guid ~= old_track
  local fx_index = parameter(master, controller, 1, 128)
  local param_index = parameter(master, controller, 2, 256)
  if guid ~= old_track then fx_index, param_index = 0, 0 end
  local fx_count = track and reaper.TrackFX_GetCount(track) or 0
  fx_index = math.max(0, math.min(fx_index, fx_count - 1))
  if fx_index ~= old_fx then param_index = 0 end
  local param_count = track and fx_count > 0 and reaper.TrackFX_GetNumParams(track, fx_index) or 0
  param_index = math.max(0, math.min(param_index, param_count - 1))
  set(master, controller, 1, 128, fx_index)
  set(master, controller, 2, 256, param_index)
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
  local function enter_area()
    choosing_area, menu, page = false, false, area_pages[area_choice+1]
    set(master, controller, 0, PAGE_COUNT, page)
    if page == 2 and track and fx_count > 0 then
      reaper.TrackFX_Show(track, fx_index, 1)
      opened_area_fx = track
    else
      if opened_area_fx and reaper.ValidatePtr2(0,opened_area_fx,'MediaTrack*') then
        reaper.TrackFX_Show(opened_area_fx, 0, 0)
      end
      opened_area_fx = nil
      if page <= 1 then reaper.SetCursorContext(page == 1 and 0 or 1, nil) end
    end
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
    choosing_area, menu, transport_choices = true, false, nil
    area_choice = page == 0 and 0 or page == 3 and 2 or page == 4 and 3 or 1
  elseif hold_state == 1 then
    choosing_area = false
    set(master,controller,12,3,0) -- Acknowledge cancellation without committing.
  end
  local request = parameter(master, controller, 3, REQUEST_COUNT)
  if request ~= 0 then
    set(master, controller, 3, REQUEST_COUNT, 0)
    if request == 15 then
      if menu then menu = false
      elseif choosing_area then enter_area()
      else
        choosing_area = true
        area_choice = page == 0 and 0 or page == 3 and 2 or page == 4 and 3 or 1
      end
    elseif choosing_area and request == 16 then enter_area()
    elseif choosing_area and request == 17 then choosing_area = false
    elseif choosing_area and request >= 18 and request <= 21 then
      local rectangles={}
      for i,name in ipairs(area_names) do rectangles[i]=ui.panels[name] or false end
      area_choice = choose_control(rectangles,area_choice,({'left','right','up','down'})[request-17])
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
        if fx_count > 0 then reaper.TrackFX_Show(track, fx_index, 1);opened_area_fx=track end
      end
    end
  end
  -- Process the last spatial move before a release commits the selection.
  if hold_state == 0 and area_held and choosing_area then enter_area() end
  area_held = hold_state == 2
  if page ~= previous_page then menu,transport_choices = false,nil; previous_page = page end
  set(master, controller, 6, 2, menu and 1 or 0)
  set(master, controller, 9, 2, choosing_area and 1 or 0)
  set(master, controller, 10, #area_names, area_choice)
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
  if choosing_area then
    local rect=ui.panels[area_names[area_choice+1]]
    show_outline(rect and table.concat(rect,' '))
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
  elseif page == 2 and track and fx_count > 0 then
    local _, fx_name = reaper.TrackFX_GetFXName(track, fx_index, '')
    local _, param_name = reaper.TrackFX_GetParamName(track, fx_index, param_index, '')
    local _, value = reaper.TrackFX_GetFormattedParamValue(track, fx_index, param_index, '')
    detail = string.format('%s%s | %s: %s', reaper.TrackFX_GetEnabled(track,fx_index) and '' or '[Bypassed] ',fx_name,param_name,value)
  elseif page == 2 then detail = 'No effects — L3: actions → Insert ReaEQ / ReaComp'
  elseif page == 0 then
    local count = reaper.CountSelectedMediaItems(0)
    local item = reaper.GetSelectedMediaItem(0, 0)
    local take = item and reaper.GetActiveTake(item)
    detail = item and string.format('%d selected | %s @ %.2fs', count, take and reaper.GetTakeName(take) or 'Empty item',
      reaper.GetMediaItemInfo_Value(item, 'D_POSITION')) or 'No item selected — D-pad left/right: choose item; A: select at cursor'
    if now < message_until then detail = message end
  end
  write(directory .. 'reaper-page', pages[page + 1])
  local rotary_target = ''
  if not menu and not choosing_area then
    if page==4 and native_button and native_button.command==60004 then
      rotary_target=pid..':transport:playrate'
    elseif page == 1 and track and control <= 1 then
      rotary_target = pid .. ':' .. guid .. ':control:' .. control
    elseif page == 2 and track and fx_count > 0 then
      rotary_target = pid .. ':' .. guid .. ':' .. reaper.TrackFX_GetFXGUID(track,fx_index) .. ':' .. param_index
    end
  end
  write(directory .. 'reaper-rotary-target', rotary_target)
  write(directory .. 'reaper-transport-field',page==4 and not menu and not choosing_area and native_button and transport.is_field(native_button.command) and tostring(native_button.command) or '')
  write(directory .. 'reaper-area', choosing_area and area_names[area_choice + 1] or '')
  write(directory .. 'reaper-context', (choosing_area and 'areas' or menu and 'menu' or 'page') .. '\n' .. summary .. '\n' .. (choosing_area and ('Choose area: ' .. area_names[area_choice + 1]) or detail))
  if visible then
    local key = gfx.getchar()
    if key == -1 then gfx.quit();visible = false
    else
      gfx.set(.09,.10,.12,1);gfx.rect(0,0,gfx.w,gfx.h,1)
      local row = math.max(12, math.min(30, (gfx.h - 8) / 4))
      gfx.setfont(1, 'sans-serif', math.max(10, math.min(18, row * .78)))
      line(choosing_area and ('Choose area: ' .. area_names[area_choice + 1]) or ('[' .. pages[page + 1] .. ']  ' .. summary), 4, true)
      if choosing_area then
        line('Stick / D-pad: move between visible regions',4+row)
        line('Release L2 / A: enter     B: cancel     Right stick: inactive',4+2*row)
        line('Toolbar / Tracks / Timeline / Transport',4+3*row)
        if key == 13 then set(master,controller,3,REQUEST_COUNT,16)
        elseif key == 27 then set(master,controller,3,REQUEST_COUNT,17) end
      elseif menu then
        line('A: run   B/L3: back   D-pad: choose', 4 + row)
        for offset=0,1 do local item=menus[page + 1][menu_index+offset+1];if item then line((offset==0 and '> ' or '  ') .. item[1],4+(offset+2)*row,offset==0) end end
        if key == 13 then set(master,controller,3,REQUEST_COUNT,2) elseif key==27 then menu=false end
      else
        local controls = {'D: item/track   R2+D: cursor   L: scroll   R: zoom',
                          'L: outline in 2D  D up/down: track  R angle: knob  A: activate',
                          'D: FX/parameter   L: track   R angle: knob position',
                          'L / D-pad: choose button   A: activate   B: choose area',
                          'L / D-pad: choose button   A: activate   B: choose area'}
        local buttons = {'X: split  R3: loop', 'X: mute  R3: solo', 'X: bypass  R3: FX window','',''}
        line(detail ~= '' and detail or controls[page + 1], 4 + row)
        line(detail ~= '' and controls[page + 1] or 'Y: play/stop   Start: save   R center: retain knob value', 4 + 2*row)
        line(buttons[page + 1] .. ' | L2: areas  L3: actions  L1/R1: track', 4 + 3*row)
      end
      gfx.update()
    end
  end
  reaper.defer(loop)
end
reaper.atexit(function() gfx.quit(); write(directory .. 'reaper-page', ''); os.remove(directory .. 'reaper-area'); os.remove(directory .. 'reaper-rotary-target'); os.remove(directory .. 'reaper-transport-field'); os.remove(outline_path) end)
reaper.defer(loop)
