-- Native panel discovery plus exact theme-image button bounds from the outline
-- process. No clicks or pointer movement; activation uses REAPER action IDs.
local ui = {panels={},buttons={Toolbar={},Transport={}},selection={Toolbar=1,Transport=1},areas={}}
local last_scan,signature,generation = -1,'',0
local function quote(s)
  return '"' .. s:gsub('\\','\\\\'):gsub('"','\\"'):gsub('\n','\\n'):gsub('\r','\\r') .. '"'
end
local function write(path,text)
  local f=io.open(path..'.tmp','w')
  if f then f:write(text);f:close();os.rename(path..'.tmp',path) end
end
function ui.available()
  return reaper.APIExists('JS_Window_ListAllChild')
end
-- Compositor IDs come from the existing outline process, not title-only focus.
-- Bind each FX entry back to a track in this project before offering controls.
local function window_rect(hwnd)
  if not hwnd or not reaper.JS_Window_IsVisible(hwnd) then return end
  local ok,l,t,r,b=reaper.JS_Window_GetRect(hwnd)
  if ok then return table.concat({l,t,r-l,b-t},',') end
end
function ui.scan_windows(path)
  local f=io.open(path..'.windows')
  if not f then ui.areas={};return end
  local stamp=tonumber(f:read('*l')) or 0
  local windows={}
  for row in f:lines() do
    local id,focused,x,y,w,h,title=row:match('^(%d+)\t([01])\t(-?%d+)\t(-?%d+)\t(%d+)\t(%d+)\t(.*)$')
    if id then windows[#windows+1]={id=tonumber(id),focused=focused=='1',title=title,rect={tonumber(x),tonumber(y),tonumber(w),tonumber(h)}} end
  end
  f:close()
  ui.native_windows=windows
  if math.abs(os.time()-stamp)>2 then ui.areas={};return end
  local main_rect=window_rect(reaper.GetMainHwnd())
  local candidates={}
  for index=0,reaper.CountTracks(0)-1 do
    local track=reaper.GetTrack(0,index)
    local _,name=reaper.GetTrackName(track)
    local title='FX: Track '..(index+1)..' "'..name..'"'
    local fx=reaper.TrackFX_GetChainVisible(track)
    if fx>=0 or fx==-2 then
      local rect=window_rect(reaper.JS_Window_Find(title,true))
      if rect then candidates[#candidates+1]={track=track,fx=math.max(0,fx),title=title,rect=rect,hwnd=reaper.JS_Window_Find(title,true),kind='chain'} end
    end
    for effect=0,reaper.TrackFX_GetCount(track)-1 do
      local hwnd=reaper.TrackFX_GetFloatingWindow(track,effect)
      local rect=window_rect(hwnd)
      if rect then candidates[#candidates+1]={track=track,fx=effect,title=reaper.JS_Window_GetTitle(hwnd),rect=rect,hwnd=hwnd,kind='floating'} end
    end
  end
  local areas={}
  for _,window in ipairs(windows) do
    local rect=table.concat(window.rect,',')
    if rect==main_rect and window.title:find('REAPER v',1,true) and not window.title:find('About REAPER',1,true) then
      for i,name in ipairs({'Timeline','Tracks','Toolbar','Transport'}) do
        areas[#areas+1]={key=name,label=name,page=({0,1,3,4})[i],main=i-1,id=window.id,rect=ui.panels[name],focused=window.focused}
      end
    else
      local match
      for _,candidate in ipairs(candidates) do
        if candidate.title==window.title and candidate.rect==rect then
          if match then match=nil;break end -- Ambiguous ownership: offer no editing target.
          match=candidate
        end
      end
      if match then areas[#areas+1]={key='fx:'..window.id,label=window.title,page=2,id=window.id,rect=window.rect,track=match.track,fx=match.fx,hwnd=match.hwnd,kind=match.kind,focused=window.focused} end
    end
  end
  -- The outline helper supplies Sway's tree order: tab/split order, not the
  -- creation IDs or focus history. Keep each window's regions together here;
  -- ui.windows() deduplicates them without changing that visible order.
  ui.areas=areas
end
-- Native widget IDs/classes for the bundled Linux ReaEQ/ReaComp interfaces.
-- Never infer a third-party plug-in's layout or draw on another parameter.
local comp_widgets={
 ['Threshold']={1045,'REAPERvfader'},['Ratio']={1078,'REAPERhfader'},
 ['Attack']={1072,'REAPERhfader'},['Release']={1074,'REAPERhfader'},
 ['Pre-comp']={1075,'REAPERhfader'},['Lowpass']={1076,'REAPERhfader'},
 ['Hipass']={1077,'REAPERhfader'},['SignIn']={1015,'combobox'},
 ['Dry']={1046,'REAPERvfader'},['Wet']={1047,'REAPERvfader'},
 ['Filter Preview']={1014,'Button'},['RMS size']={1079,'REAPERhfader'},
 ['Knee']={1080,'REAPERhfader'},['Auto Make Up Gain']={1018,'Button'},
 ['Auto Release']={1019,'Button'}
}
local pitch_widgets={
 {1075,'Shift (full range)','Shift (full range)'},
 {1076,'Shift (cents)','Shift (cents)'},
 {1077,'Shift (semitones)','Shift (semitones)'},
 {1078,'Shift (octaves)','Shift (oct)'},
 {1083,'Formant shift (full)','Formant adjust (full range)'},
 {1079,'Formant shift (cents)','Formant adjust (cents)'},
 {1080,'Formant shift (semitones)','Formant adjust (semitones)'},
 {1081,'Volume','Volume'}, {1082,'Pan','Pan'}
}
local function native_children(root)
 local result={}
 local _,list=reaper.JS_Window_ListAllChild(root)
 for address in list:gmatch('[^,]+') do
  local hwnd=reaper.JS_Window_HandleFromAddress(tonumber(address))
  result[#result+1]={hwnd=hwnd,id=reaper.JS_Window_GetLong(hwnd,'ID'),
   class=reaper.JS_Window_GetClassName(hwnd),title=reaper.JS_Window_GetTitle(hwnd)}
 end
 return result
end
local function widget(children,id,class,title)
 local match
 for _,child in ipairs(children) do
  if child.id==id and child.class==class and (not title or child.title==title) then
   if match then return end -- A changed layout must not highlight an arbitrary duplicate.
   match=child.hwnd
  end
 end
 return match
end
local function direct_children(children,parent)
 local result={}
 for _,child in ipairs(children) do
  if reaper.JS_Window_GetParent(child.hwnd)==parent then result[#result+1]=child end
 end
 return result
end
local function clean_label(text)
 return (text or ''):gsub('&',''):gsub(':$',''):gsub('^%s+',''):gsub('%s+$','')
end
local function label_key(text) return clean_label(text):lower():gsub('[%s%-%_]+','') end
-- Labels describe targets; native ownership/class determines how to activate
-- them. Never infer a parameter from control IDs or a coincidental value.
local function nearby_label(child,children)
 local ok,l,t,r,b=reaper.JS_Window_GetRect(child.hwnd)
 if not ok then return '' end
 local parent=reaper.JS_Window_GetParent(child.hwnd)
 local best,score,ambiguous='',math.huge,false
 for _,other in ipairs(children) do
  if other.class=='Static' and other.title~='' and reaper.JS_Window_GetParent(other.hwnd)==parent and reaper.JS_Window_IsVisible(other.hwnd) then
   local valid,x,y,right,bottom=reaper.JS_Window_GetRect(other.hwnd)
   if valid then
    local cost
    if right<=l+4 and math.abs((y+bottom-t-b)/2)<16 and l-right<150 then cost=l-right+math.abs((y+bottom-t-b)/2)*3
    elseif bottom<=t+4 and t-bottom<40 and x<r and right>l then cost=40+t-bottom+math.abs((x+right-l-r)/2) end
    if cost and cost<score then best,score,ambiguous=clean_label(other.title),cost,false
    elseif cost and cost==score then ambiguous=true end
   end
  end
 end
 return not ambiguous and best or ''
end
-- A native slider can still be edited when its automation name is different or
-- repeated across tabs. Bind only a unique adjacent value field in its parent.
local function slider_editor(child,children)
 local ok,l,t,r,b=reaper.JS_Window_GetRect(child.hwnd)
 if not ok then return end
 local parent=reaper.JS_Window_GetParent(child.hwnd)
 local best,distance,ambiguous=nil,math.huge,false
 for _,other in ipairs(children) do
  if other.class=='Edit' and reaper.JS_Window_GetParent(other.hwnd)==parent and reaper.JS_Window_IsVisible(other.hwnd) and (reaper.JS_Window_GetLong(other.hwnd,'STYLE') & 0x08000800)==0 then
   local valid,x,y,right,bottom=reaper.JS_Window_GetRect(other.hwnd)
   local cost
   if valid and x>=r and x-r<32 and math.abs((y+bottom-t-b)/2)<10 then cost=x-r
   elseif valid and y>=b and y-b<32 and math.abs((x+right-l-r)/2)<10 then cost=y-b end
   if cost and cost<distance then best,distance,ambiguous=other.hwnd,cost,false
   elseif cost and cost==distance then ambiguous=true end
  end
 end
 if not ambiguous then return best end
end
local function native_key(hwnd,key)
 reaper.JS_WindowMessage_Send(hwnd,'WM_KEYDOWN',key,0,1,0)
 reaper.JS_WindowMessage_Send(hwnd,'WM_KEYUP',key,0,1,0)
end
local function invalidate_shifter(state)
 state.pitch_tab,state.pitch_pending,state.pitch_ready=nil,nil,false
end
ui.pitch_watches={}
local function shifter_notification(tab)
 if not reaper.JS_WindowMessage_Intercept then return false end
 local parent=reaper.JS_Window_GetParent(tab)
 local watch=ui.pitch_watches[parent]
 if not watch then
  local owned=reaper.JS_WindowMessage_Intercept(parent,'WM_NOTIFY',true)==1
  local ok,passed,stamp=reaper.JS_WindowMessage_Peek(parent,'WM_NOTIFY')
  if not ok or not passed then return false end
  watch={owned=owned,stamp=stamp};ui.pitch_watches[parent]=watch
 end
 local ok,passed,stamp=reaper.JS_WindowMessage_Peek(parent,'WM_NOTIFY')
 if not ok then
  ui.pitch_watches[parent]=nil
  return shifter_notification(tab)
 end
 local changed=ok and passed and stamp~=watch.stamp
 if ok then watch.stamp=stamp end
 return changed
end
function ui.close()
 for hwnd,watch in pairs(ui.pitch_watches) do
  if watch.owned then reaper.JS_WindowMessage_Release(hwnd,'WM_NOTIFY') end
 end
 ui.pitch_watches={}
end
local function prepare_shifter(state,tab,panel,now)
 if not tab or not panel then state.pitch_ready=false;return false end
 if shifter_notification(tab) then invalidate_shifter(state) end
 if state.pitch_pending then
  if now<state.pitch_pending then return false end
  state.pitch_pending,state.pitch_panel,state.pitch_ready=nil,panel,true
  return true
 end
 if state.pitch_tab~=tab or state.pitch_panel~=panel then
  -- The controller owns the selected shifter, as it owns ReaEQ's selected band.
  -- Gate rotary input until the native panel is ready. Watch pass-through tab
  -- notifications because ReaPitch can also reuse the same panel on tab changes.
  native_key(tab,36)
  for _=1,state.shifter do native_key(tab,39) end
  shifter_notification(tab) -- Acknowledge notifications from our own tab reveal.
  state.pitch_tab,state.pitch_pending,state.pitch_ready=tab,now+.12,false
  return false
 end
 return state.pitch_ready
end
local function native_index(node)
 return reaper.JS_ListView_EnumSelItems(node.hwnd,-1)
end
local function select_native(node,index)
 reaper.JS_ListView_SetItemState(node.hwnd,-1,0,3)
 if index and index>=0 and index<reaper.JS_ListView_GetItemCount(node.hwnd) then
  reaper.JS_ListView_SetItemState(node.hwnd,index,3,3)
  reaper.JS_ListView_EnsureVisible(node.hwnd,index,false)
 end
end
local function clipped_widget(hwnd,root)
 if not hwnd or not reaper.JS_Window_IsVisible(hwnd) then return nil,'Control is hidden' end
 local ok,l,t,r,b=reaper.JS_Window_GetRect(hwnd)
 if not ok or r<=l or b<=t then return nil,'Control is hidden' end
 local original={l,t,r,b}
 local parent=reaper.JS_Window_GetParent(hwnd)
 for _=1,32 do
  if not parent then return nil,'Control window closed' end
  local valid,x,y,right,bottom=reaper.JS_Window_GetRect(parent)
  if not valid or not reaper.JS_Window_IsVisible(parent) then return nil,'Control is hidden' end
  local inset=parent==root and 4 or 0
  l,t,r,b=math.max(l,x+inset),math.max(t,y+inset),math.min(r,right-inset),math.min(b,bottom-inset)
  if parent==root then
   if r-l<12 or b-t<8 then return nil,'Control outside tile: enlarge the FX window' end
   local partial=l~=original[1] or t~=original[2] or r~=original[3] or b~=original[4]
   return {l,t,r-l,b-t},partial and 'Control partly clipped: enlarge the FX window' or ''
  end
  parent=reaper.JS_Window_GetParent(parent)
 end
 return nil,'Unrecognized control hierarchy'
end
function ui.fx_outline(track,fx,param,now)
 local area
 for _,entry in ipairs(ui.areas) do
  if entry.track==track and entry.fx==fx then
   if not area or entry.focused then area=entry end
  end
 end
 if not area or not area.hwnd then return nil,nil,'Open the selected effect to show its control' end
 if area.kind=='chain' and reaper.TrackFX_GetChainVisible(track)~=fx then return nil,nil,'Updating effect view' end
 local root=area.hwnd
 local all=native_children(root)
 local _,ident=reaper.TrackFX_GetParamIdent(track,fx,param)
 local target
 if ident and ident:match(':bypass$') then target=widget(all,1426,'Button')
 elseif ident and ident:match(':wet$') then target=widget(all,1449,'REAPERknob')
 else
  local _,plugin=reaper.TrackFX_GetNamedConfigParm(track,fx,'fx_ident')
  local _,name=reaper.TrackFX_GetParamName(track,fx,param,'')
  local marker
  if plugin and plugin:find('/reaeq.vst.so<',1,true) then marker=widget(all,1034,'Static','ReaEQ')
  elseif plugin and plugin:find('/reacomp.vst.so<',1,true) then marker=widget(all,1112,'Button','ReaComp') end
  if marker then
   local body=reaper.JS_Window_GetParent(marker)
   local children=native_children(body)
   if plugin:find('/reaeq.vst.so<',1,true) then
    local kind=name:match('^(%a+)%-')
    local id=({Freq=1023,Gain=1024,BW=1025})[kind]
    if id then
     local tab=widget(children,1026,'SysTabControl32')
     if not tab or not reaper.JS_Window_IsVisible(tab) then return nil,nil,'Enable ReaEQ Show tabs to highlight band controls' end
     local band=math.floor(param/3)
     local key=tostring(root)..':'..reaper.TrackFX_GetFXGUID(track,fx)..':'..band
     if ui.fx_band~=key then
      -- Linux SWELL uses FVIRTKEY=1 in lParam, and updates the band panel
      -- asynchronously. Reveal tabs with native keyboard messages, not clicks.
      reaper.JS_WindowMessage_Send(tab,'WM_KEYDOWN',36,0,1,0) -- Home
      for _=1,band do reaper.JS_WindowMessage_Send(tab,'WM_KEYDOWN',39,0,1,0) end -- Right
      ui.fx_band,ui.fx_band_ready=key,now+.12
     end
     if now<ui.fx_band_ready then return nil,nil,'Selecting EQ band '..(band+1) end
     target=widget(children,id,'REAPERhfader')
    elseif name=='Global Gain' then target=widget(children,1047,'REAPERvfader') end
   else
    local control=comp_widgets[name]
    if control then target=widget(children,control[1],control[2]) end
   end
  end
 end
 if not target then return nil,nil,'No visible control mapping for this parameter' end
 local rect,note=clipped_widget(target,root)
 return rect,area.id,note
end
-- Window-local FX regions and spatial controls. Native commands are dispatched
-- only from explicitly identified controls in the currently bound FX window.
ui.fx_memory={}
function ui.windows()
 local result,seen={},{}
 for _,area in ipairs(ui.areas) do
  if not seen[area.id] then result[#result+1]=area;seen[area.id]=true end
 end
 return result
end
function ui.focused_window()
 for _,window in ipairs(ui.windows()) do if window.focused then return window end end
end
function ui.window_neighbor(current,direction)
 local windows=ui.windows()
 for i,window in ipairs(windows) do
  if window.id==current then return windows[(i-1+direction)%#windows+1] end
 end
 return windows[direction<0 and #windows or 1]
end
local function command_widget(hwnd)
 local parent=reaper.JS_Window_GetParent(hwnd)
 local id=reaper.JS_Window_GetLong(hwnd,'ID')
 reaper.JS_WindowMessage_Send(parent,'WM_COMMAND',id,0,reaper.JS_Window_AddressFromHandle(hwnd),0)
end
local function combo_index(hwnd,value)
 local count=reaper.JS_WindowMessage_Send(hwnd,'CB_GETCOUNT',0,0,0,0)
 if count<=0 then return end
 local current=reaper.JS_WindowMessage_Send(hwnd,'CB_GETCURSEL',0,0,0,0)
 if value==nil then return current,count end
 value=math.max(0,math.min(count-1,value))
 if value~=current then
  reaper.JS_WindowMessage_Send(hwnd,'CB_SETCURSEL',value,0,0,0)
  reaper.JS_WindowMessage_Send(reaper.JS_Window_GetParent(hwnd),'WM_COMMAND',reaper.JS_Window_GetLong(hwnd,'ID'),1,reaper.JS_Window_AddressFromHandle(hwnd),0)
 end
 return value,count
end
function ui.fx_regions(area,fx,param,now)
 if not area or not area.hwnd or not reaper.JS_Window_IsVisible(area.hwnd) then
  if area and ui.fx_memory[area.id] then ui.fx_memory[area.id].regions={};ui.fx_memory[area.id].editing=nil end
  return {}
 end
 local root,track=area.hwnd,area.track
 local state=ui.fx_memory[area.id]
 if not state then state={region='plugin',selection={},band=0};ui.fx_memory[area.id]=state end
 local count=reaper.TrackFX_GetCount(track)
 local guid=count>0 and reaper.TrackFX_GetFXGUID(track,fx) or ''
 if state.guid~=guid then
  state.guid,state.band=guid,0
  state.shifter,state.pitch=0,false;invalidate_shifter(state)
  if not state.editing or state.editing.kind~='effects' then state.editing=nil end
 end
 local all=native_children(root)
 local regions={}
 local function region(key,label,anchor)
  local value={key=key,label=label,nodes={},id=area.id,page=2,track=track,fx=fx,hwnd=root,kind=area.kind,region=key}
  if anchor then value.rect=clipped_widget(anchor,root) end
  regions[#regions+1]=value
  return value
 end
 local function add(region,key,label,hwnd,kind,param)
  if kind=='param' and (param==nil or param<0 or param>=65536 or fx>=128) then return end
  local style=hwnd and reaper.JS_Window_GetLong(hwnd,'STYLE') or 0
  if (style & 0x08000000)~=0 then return end -- Disabled native controls are not activation targets.
  local rect=hwnd and clipped_widget(hwnd,root)
  if not rect then return end
  local node={key=key,label=label,hwnd=hwnd,rect=rect,kind=kind or 'command',param=param}
  region.nodes[#region.nodes+1]=node
  return node
 end
 local chain_controls=direct_children(all,root)
 local list=widget(chain_controls,1076,'SysListView32')
 if area.kind=='chain' and list then
  local effects=region('effects','Effects list',list)
  add(effects,'effects:list','Choose effect',list,'effects')
  add(effects,'effects:add','Add FX',widget(chain_controls,1075,'Button','Add'))
  add(effects,'effects:remove','Remove selected FX',widget(chain_controls,1058,'Button','Remove'))
 end
 local host=root
 for _,child in ipairs(chain_controls) do
  if child.class=='unknown' then
   local siblings=direct_children(all,child.hwnd)
   if widget(siblings,1192,'Button','UI') and widget(siblings,1422,'Button','Param') then host=child.hwnd;break end
  end
 end
 local host_controls=direct_children(all,host)
 local header=region('header','Presets and routing')
 add(header,'header:preset','Preset',widget(host_controls,1000,'combobox'),'combo')
 for _,item in ipairs({{1257,'+','Preset actions'},{1422,'Param','Parameter actions'},{1190,nil,'Audio routing'},{1192,'UI','Custom / generic interface'}}) do
  add(header,'header:'..item[1],item[3],widget(host_controls,item[1],'Button',item[2]))
 end
 local function host_param(suffix)
  for index=0,reaper.TrackFX_GetNumParams(track,fx)-1 do
   local _,ident=reaper.TrackFX_GetParamIdent(track,fx,index)
   if ident and ident:match(':'..suffix..'$') then return index end
  end
 end
 if count>0 then
  add(header,'header:wet','Wet',widget(host_controls,1449,'REAPERknob'),'param',host_param('wet'))
  add(header,'header:bypass','Effect enabled',widget(host_controls,1426,'Button'),'toggle')
 end
 local plugin=''
 if count>0 then local ok;ok,plugin=reaper.TrackFX_GetNamedConfigParm(track,fx,'fx_ident');plugin=plugin or '' end
 state.pitch=false -- The same FX can switch to the host's generic parameter UI.
 local marker,eq,pitch
 if plugin:find('/reaeq.vst.so<',1,true) then marker,eq=widget(all,1034,'Static','ReaEQ'),true
 elseif plugin:find('/reacomp.vst.so<',1,true) then marker=widget(all,1112,'Button','ReaComp') end
 if plugin:find('/reapitch.vst.so<',1,true) then marker,pitch=widget(all,1100,'Button','ReaPitch'),true end
 if marker then
  local body=reaper.JS_Window_GetParent(marker)
  local controls=native_children(body)
  local editor=region('plugin',eq and 'ReaEQ controls' or pitch and 'ReaPitch controls' or 'ReaComp controls',body)
  local parameters={}
  for index=0,reaper.TrackFX_GetNumParams(track,fx)-1 do
   local _,name=reaper.TrackFX_GetParamName(track,fx,index,'')
   parameters[name]=parameters[name] or index
  end
  if eq then
   local bands=0
   for name in pairs(parameters) do if name:match('^Freq%-') then bands=bands+1 end end
   state.bands=bands;state.band=math.max(0,math.min(state.band,bands-1))
   local tabs=add(editor,'eq:band','Band '..(state.band+1),widget(controls,1026,'SysTabControl32'),'band')
   if tabs then tabs.rect[4]=math.min(24,tabs.rect[4]) end -- Highlight the tab strip, not its child panel.
   local prefix=state.band*3
   for i,item in ipairs({{'eq:freq','Frequency',1023},{'eq:gain','Gain',1024},{'eq:bandwidth','Bandwidth',1025}}) do
    local node=add(editor,item[1],'Band '..(state.band+1)..' '..item[2],widget(controls,item[3],'REAPERhfader'),'param',prefix+i-1)
    if node then node.band=state.band end
   end
   add(editor,'eq:global','Global Gain',widget(controls,1047,'REAPERvfader'),'param',parameters['Global Gain'])
   add(editor,'eq:type','Band type',widget(controls,1015,'combobox'),'combo')
   add(editor,'eq:enabled','Band enabled',widget(controls,1022,'Button','Enabled'),'toggle')
   add(editor,'eq:log','Log-scale frequencies',widget(controls,1029,'Button','Log-scale automated frequencies'),'toggle')
   for _,item in ipairs({{1018,'Add band','eq:add'},{1019,'Remove band','eq:remove'},{1020,'Reset defaults','eq:reset'}}) do
    add(editor,item[3],item[2],widget(controls,item[1],'Button',item[2]))
   end
   for _,item in ipairs({{1029,'Show tabs'},{1022,'Show grid'},{1024,'Show phase'}}) do
    add(editor,'eq:'..item[2],item[2],widget(controls,item[1],'Button',item[2]),'toggle')
   end
   add(editor,'eq:meter','Metering',widget(controls,1038,'combobox'),'combo')
  elseif pitch then
   state.pitch=true
   local groups=0
   for name in pairs(parameters) do groups=math.max(groups,tonumber(name:match('^(%d+): Enabled$')) or 0) end
   state.shifters=groups
   local selected=math.max(0,math.min(state.shifter or 0,groups-1))
   if selected~=state.shifter then state.shifter=selected;invalidate_shifter(state) end
   local slider=widget(controls,1075,'REAPERhfader')
   local panel=slider and reaper.JS_Window_GetParent(slider)
   local tab=widget(controls,1026,'SysTabControl32')
   local ready=state.pitch_ready or false
   state.pitch_current_panel,state.pitch_current_tab=panel,tab
   local tabs=add(editor,'pitch:shifter','Shifter '..(state.shifter+1),tab,'shifter')
   if tabs then tabs.rect[4]=math.min(24,tabs.rect[4]) end
   local prefix=(state.shifter+1)..': '
   for _,item in ipairs(pitch_widgets) do
    local node=add(editor,'pitch:'..item[1],item[2],widget(controls,item[1],'REAPERhfader'),'param',parameters[prefix..item[3]])
    if node then node.ready,node.shifter_control=ready,true end
   end
   add(editor,'pitch:wet','Wet',widget(controls,1047,'REAPERvfader'),'param',parameters['Wet'])
   add(editor,'pitch:dry','Dry',widget(controls,1046,'REAPERvfader'),'param',parameters['Dry'])
   for _,item in ipairs({{1018,'Add shifter','pitch:add'},{1019,'Delete shifter','pitch:delete'},{1020,'Reset all','pitch:reset'}}) do
    local node=add(editor,item[3],item[2],widget(controls,item[1],'Button',item[2]))
    if node then node.shifter_control=true end
   end
  else
   for name,param in pairs(parameters) do
    local map=comp_widgets[name]
    -- Host Wet has its own header control; comp's Wet remains parameter 11.
    if map and (name~='Wet' or param==11) then
     local kind=map[2]=='Button' and 'toggle' or map[2]=='combobox' and 'combo' or 'param'
     add(editor,'comp:'..name,name,widget(controls,map[1],map[2]),kind,param)
    end
   end
   add(editor,'comp:limit','Limit output',widget(controls,1023,'Button','Limit output'),'toggle')
  end
 end
 -- Standard SWELL widgets are discoverable even when a plug-in has no custom
 -- adapter. Keep the exact EQ/Comp parameter maps, then fill their native gaps.
 local bodies={}
 for _,child in ipairs(host_controls) do
  if child.class=='unknown' and reaper.JS_Window_IsVisible(child.hwnd) then bodies[#bodies+1]=child.hwnd end
 end
 local editor
 for _,entry in ipairs(regions) do if entry.key=='plugin' then editor=entry end end
 local mapped={}
 if editor then for _,node in ipairs(editor.nodes) do mapped[node.hwnd]=true end end
 local parameters,grouped_parameters={},{}
 if count>0 then
  for index=0,reaper.TrackFX_GetNumParams(track,fx)-1 do
   local _,ident=reaper.TrackFX_GetParamIdent(track,fx,index)
   if not ((ident or ''):match(':wet$') or (ident or ''):match(':bypass$') or (ident or ''):match(':delta$')) then
    local _,name=reaper.TrackFX_GetParamName(track,fx,index,'')
    local key=label_key(name)
    parameters[key]=parameters[key]==nil and index or false
    local ungrouped=name:match('^%d+:%s*(.+)$')
    if ungrouped then
     local alias=label_key(ungrouped)
     grouped_parameters[alias]=grouped_parameters[alias]==nil and index or false
    end
   end
  end
 end
 if count>0 then for _,body in ipairs(bodies) do
  local controls=native_children(body)
  for _,child in ipairs(controls) do
   if not mapped[child.hwnd] then
    local class,hwnd=child.class,child.hwnd
    local style=reaper.JS_Window_GetLong(hwnd,'STYLE')
    local label,kind,param,editor_hwnd=clean_label(child.title),nil,nil,nil
    if class=='Button' then
     local subtype=style & 0xf
     -- Group boxes/static frames are not buttons (SWELL can mark them disabled).
     if (style & 0x20000000)~=0 then -- SWELL BS_GROUPBOX differs from Win32.
     elseif subtype==0 or subtype==1 then kind='command'
     elseif subtype==2 or subtype==3 then kind='toggle'
     elseif subtype==4 or subtype==5 or subtype==6 or subtype==9 then kind='native_button' end
    elseif class=='combobox' then kind='combo';label=nearby_label(child,controls)
    elseif class=='SysListView32' then kind='list';label=nearby_label(child,controls)
    elseif class=='Edit' and (style & 0x800)==0 then
     kind='edit';label=nearby_label(child,controls)
     if label=='' then
      local _,l,t,r,b=reaper.JS_Window_GetRect(hwnd)
      local best,distance='',math.huge
      for _,other in ipairs(controls) do
       if (other.class=='REAPERhfader' or other.class=='REAPERvfader') and reaper.JS_Window_GetParent(other.hwnd)==reaper.JS_Window_GetParent(hwnd) then
        local valid,x,y,right,bottom=reaper.JS_Window_GetRect(other.hwnd)
        local cost
        if valid and right<=l and l-right<30 and math.abs((y+bottom-t-b)/2)<10 then cost=l-right
        elseif valid and bottom<=t and t-bottom<30 and math.abs((x+right-l-r)/2)<10 then cost=t-bottom end
        if cost and cost<distance then best,distance=nearby_label(other,controls),cost end
       end
      end
      label=best
     end
    elseif class=='REAPERhfader' or class=='REAPERvfader' or class=='REAPERknob' then
     label=nearby_label(child,controls)
     local candidate=parameters[label_key(label)]
     if candidate==nil then candidate=grouped_parameters[label_key(label)] end
     if type(candidate)=='number' then kind,param='param',candidate end
     if not kind then
      editor_hwnd=slider_editor(child,controls)
      if editor_hwnd then kind='edit' end
     end
    end
    if kind then
     if label=='' then label=({combo='Choices',list='List',edit='Value',command='Button',toggle='Switch'})[kind] or kind end
     if not editor then editor=region('plugin','Plugin controls',body) end
     local node=add(editor,'native:'..tostring(hwnd),label,hwnd,kind,param)
     if node then
      node.editor=editor_hwnd
      if pitch and reaper.JS_Window_GetParent(hwnd)==state.pitch_current_panel then node.ready,node.shifter_control=state.pitch_ready,true end
     end
    end
   end
  end
 end end
 -- Host automation is the portable fallback for opaque/custom-painted editors.
 -- These are list entries, never pretend screen coordinates for native knobs.
 local parameter_region
 if count>0 and fx<128 and (not editor or #editor.nodes==0) then
  for index=0,math.min(65536,reaper.TrackFX_GetNumParams(track,fx))-1 do
   local _,ident=reaper.TrackFX_GetParamIdent(track,fx,index)
   local _,name=reaper.TrackFX_GetParamName(track,fx,index,'')
   name=clean_label(name)
   local placeholder=name=='' or name:lower()=='blank' or name:lower()=='unused'
   local host=(ident or ''):match(':wet$') or (ident or ''):match(':bypass$') or (ident or ''):match(':delta$')
   -- REAPER exposes synthetic VST3 MIDI CC slots alongside real parameters.
   local midi=name:match('^MIDI CC %d+|%d+$')
   if not placeholder and not host and not midi then
    if not parameter_region then
     parameter_region=region('parameters','Plugin parameters')
     local _,l,t,r,b=reaper.JS_Window_GetRect(root)
     parameter_region.rect={l+4,t+80,math.max(12,r-l-8),math.max(8,b-t-84)}
    end
    parameter_region.nodes[#parameter_region.nodes+1]={key=string.format('parameter:%05d',index),
     label=name,param=index,kind='param',list_only=true,rect=parameter_region.rect}
   end
  end
 end
 local available={}
 for _,region in ipairs(regions) do
  table.sort(region.nodes,function(a,b)return a.key<b.key end)
  if #region.nodes>0 then
   do
    local anchor=region.rect
    local l,t,r,b=anchor and anchor[1] or math.huge,anchor and anchor[2] or math.huge,anchor and (anchor[1]+anchor[3]) or -math.huge,anchor and (anchor[2]+anchor[4]) or -math.huge
    for _,node in ipairs(region.nodes) do local v=node.rect;l,t,r,b=math.min(l,v[1]),math.min(t,v[2]),math.max(r,v[1]+v[3]),math.max(b,v[2]+v[4]) end
    region.rect={l,t,r-l,b-t}
   end
   local selected=state.selection[region.key]
   local found=false
   for _,node in ipairs(region.nodes) do if node.key==selected then found=true end end
   if not found then
    if state.editing and state.editing.key==selected then state.editing=nil end
    state.selection[region.key]=region.key=='plugin' and eq and 'eq:freq' or region.nodes[1].key
    local has=false
    for _,node in ipairs(region.nodes) do if node.key==state.selection[region.key] then has=true end end
    if not has then state.selection[region.key]=region.nodes[1].key end
   end
   available[#available+1]=region
  end
 end
 state.regions,state.track,state.fx,state.window=available,track,fx,area.id
 local valid=false
 for _,region in ipairs(available) do if region.key==state.region then valid=true end end
 if not valid and available[1] then state.region=parameter_region and parameter_region.key or available[1].key end
 return available
end
function ui.fx_current(window)
 local state=ui.fx_memory[window]
 if not state then return end
 for _,region in ipairs(state.regions or {}) do
  if region.key==state.region then
   for _,node in ipairs(region.nodes) do if node.key==state.selection[region.key] then return node,state,region end end
  end
 end
end
function ui.fx_prepare(window,now)
 local state=ui.fx_memory[window]
 if not state or not state.pitch then return end
 local ready=prepare_shifter(state,state.pitch_current_tab,state.pitch_current_panel,now)
 for _,region in ipairs(state.regions or {}) do
  for _,node in ipairs(region.nodes) do if node.shifter_control then node.ready=ready end end
 end
end
local function show_band(state)
 ui.fx_band=nil
 ui.fx_outline(state.track,state.fx,state.band*3,reaper.time_precise())
end
function ui.fx_step(window,direction)
 local node,state=ui.fx_current(window)
 if not node or node.ready==false then return end
 local delta=(direction=='left' or direction=='up') and -1 or 1
 if node.kind=='band' then
  state.band=math.max(0,math.min(state.bands-1,state.band+delta));show_band(state)
 elseif node.kind=='shifter' then
  state.shifter=math.max(0,math.min(state.shifters-1,state.shifter+delta));invalidate_shifter(state)
 elseif node.kind=='combo' then
  local index=combo_index(node.hwnd)
  if index then combo_index(node.hwnd,index+delta) end
 elseif node.kind=='effects' then
  local count=reaper.TrackFX_GetCount(state.track)
  local index=math.max(0,math.min(count-1,state.fx+delta))
  if count>0 then reaper.TrackFX_Show(state.track,index,1);return index end
 elseif node.kind=='toggle' then
  reaper.JS_WindowMessage_Send(node.hwnd,'BM_SETCHECK',delta>0 and 1 or 0,0,0,0);command_widget(node.hwnd)
 elseif node.kind=='list' then
  native_key(node.hwnd,delta<0 and 38 or 40)
 end
end
function ui.fx_move(window,direction,choose)
 local node,state,region=ui.fx_current(window)
 if not node then return end
 if state.editing then return ui.fx_step(window,direction) end
 if node.list_only then
  for i,item in ipairs(region.nodes) do
   if item.key==node.key then
    local delta=(direction=='left' or direction=='up') and -1 or 1
    state.selection[region.key]=region.nodes[math.max(1,math.min(#region.nodes,i+delta))].key
    return
   end
  end
 end
 local rectangles,current={},0
 for i,item in ipairs(region.nodes) do rectangles[i]=item.rect;if item.key==node.key then current=i-1 end end
 local next=region.nodes[choose(rectangles,current,direction)+1]
 if next then state.selection[region.key]=next.key end
end
local function expect_popup(state,prefix)
 if not ui.path then return end
 local ids={}
 for _,window in ipairs(ui.native_windows or {}) do ids[#ids+1]=window.id end
 write(ui.path..'.popup',os.time()..'\t'..state.window..'\t'..table.concat(ids,',')..'\t'..(prefix or ''))
end
function ui.fx_activate(window)
 local node,state=ui.fx_current(window)
 if not node then return end
 if node.ready==false then return 'Selecting shifter '..(state.shifter+1) end
 if state.editing then state.editing=nil;return end
 if node.kind=='param' then return 'Turn the right stick to adjust '..node.label
 elseif node.kind=='toggle' then
  local checked=reaper.JS_WindowMessage_Send(node.hwnd,'BM_GETCHECK',0,0,0,0)
  reaper.JS_WindowMessage_Send(node.hwnd,'BM_SETCHECK',checked==0 and 1 or 0,0,0,0);command_widget(node.hwnd)
 elseif node.kind=='list' then
  if reaper.JS_ListView_GetItemCount(node.hwnd)==0 then return 'This list is empty; choose Add' end
  local original=native_index(node)
  state.editing={key=node.key,kind=node.kind,original=original}
  if original<0 then select_native(node,0) end
 elseif node.kind=='shifter' then
  state.editing={key=node.key,kind=node.kind,original=state.shifter}
 elseif node.kind=='band' or node.kind=='combo' or node.kind=='effects' then
  state.editing={key=node.key,kind=node.kind,original=node.kind=='band' and state.band or node.kind=='effects' and state.fx or combo_index(node.hwnd)}
 elseif node.kind=='edit' then
  local hwnd=node.editor or node.hwnd
  local original=reaper.JS_Window_GetTitle(hwnd)
  expect_popup(state)
  local accepted,value=reaper.GetUserInputs(node.label,1,'Value:,separator=\n',original)
  if accepted and reaper.JS_Window_IsWindow(hwnd) and reaper.TrackFX_GetFXGUID(state.track,state.fx)==state.guid then
   reaper.JS_Window_SetTitle(hwnd,value)
   reaper.JS_WindowMessage_Send(reaper.JS_Window_GetParent(hwnd),'WM_COMMAND',reaper.JS_Window_GetLong(hwnd,'ID'),0x300,reaper.JS_Window_AddressFromHandle(hwnd),0)
  end
 elseif node.kind=='native_button' then native_key(node.hwnd,32)
 else
  if node.key=='eq:add' then state.band=state.bands
  elseif node.key=='eq:remove' then state.band=math.max(0,math.min(state.band,state.bands-2))
  elseif node.key=='eq:reset' then state.band=0 end
  if node.key=='pitch:add' then state.shifter=state.shifters;invalidate_shifter(state)
  elseif node.key=='pitch:delete' then state.shifter=math.max(0,state.shifter-1);invalidate_shifter(state)
  elseif node.key=='pitch:reset' then state.shifter=0;invalidate_shifter(state) end
  ui.fx_band=nil
  expect_popup(state,node.key=='effects:add' and 'Add FX ' or '')
  command_widget(node.hwnd)
 end
end
function ui.fx_cancel(window)
 local node,state=ui.fx_current(window)
 if not state or not state.editing then return false end
 local editing=state.editing;state.editing=nil
 if node and node.key==editing.key then
  if editing.kind=='band' then state.band=editing.original;show_band(state)
  elseif editing.kind=='shifter' then state.shifter=editing.original;invalidate_shifter(state)
  elseif editing.kind=='combo' then combo_index(node.hwnd,editing.original)
  elseif editing.kind=='list' then select_native(node,editing.original)
  elseif editing.kind=='effects' and reaper.TrackFX_GetCount(state.track)>editing.original then reaper.TrackFX_Show(state.track,editing.original,1) end
 end
 return true
end
local focus_sequence=0
function ui.focus(path,area,now)
  focus_sequence=focus_sequence+1
  write(path..'.focus',focus_sequence..' '..area.id)
  ui.pending={sequence=focus_sequence,area=area,deadline=now+1}
end
function ui.focus_result(path,now)
  local pending=ui.pending
  if not pending then return end
  local f=io.open(path..'.focused')
  local sequence,success
  if f then sequence,success=f:read('*a'):match('^(%d+) ([01])');f:close() end
  if tonumber(sequence)==pending.sequence or now>pending.deadline then
    ui.pending=nil
    return pending.area,tonumber(sequence)==pending.sequence and success=='1'
  end
end
function ui.cancel_focus(path)
  ui.pending=nil
  os.remove(path..'.focus')
end
function ui.scan(now,path)
  ui.path=path
  if not ui.available() then return end
  if now-last_scan>.25 then
    last_scan=now
    local panels={}
    local _,list=reaper.JS_Window_ListAllChild(reaper.GetMainHwnd())
    for address in list:gmatch('[^,]+') do
      local hwnd=reaper.JS_Window_HandleFromAddress(tonumber(address))
      if reaper.JS_Window_IsVisible(hwnd) then
        local title,class=reaper.JS_Window_GetTitle(hwnd),reaper.JS_Window_GetClassName(hwnd)
        local name=title=='Main toolbar' and 'Toolbar' or title=='Transport' and 'Transport' or class=='REAPERTCPDisplay' and 'Tracks' or class=='REAPERTrackListWindow' and 'Timeline'
        if name then
          local ok,l,t,r,b=reaper.JS_Window_GetRect(hwnd)
          if ok and r>l and b>t then panels[name]={l,t,r-l,b-t} end
        end
      end
    end
    local theme=reaper.GetLastColorThemeFile()
    local _,flags=reaper.get_config_var_string('transflags')
    local _,layout=reaper.ThemeLayout_GetLayout('trans',-1)
    local parts={theme,flags or '',layout or '',tostring(reaper.GetToggleCommandStateEx(0,40680)),tostring(reaper.GetToggleCommandStateEx(0,40531))}
    for index=0,255 do
      local cfg,desc,value=reaper.ThemeLayout_GetParameter(index)
      if not cfg or cfg=='' then break end
      if desc and desc:lower():find('transport',1,true) then parts[#parts+1]=cfg..':'..tostring(value) end
    end
    for _,name in ipairs({'Toolbar','Tracks','Timeline','Transport'}) do
      parts[#parts+1]=name..':'..table.concat(panels[name] or {},',')
    end
    local next_signature=table.concat(parts,'|')
    if next_signature~=signature then
      signature,generation=next_signature,generation+1
      ui.panels,ui.buttons=panels,{Toolbar={},Transport={}}
      local json={}
      for _,name in ipairs({'Toolbar','Transport'}) do
        if panels[name] then json[#json+1]=quote(name)..':['..table.concat(panels[name],',')..']' end
      end
      write(path..'.request','{"generation":'..generation..',"resource":'..quote(reaper.GetResourcePath())..',"theme":'..quote(theme)..',"panels":{'..table.concat(json,',')..'}}')
    end
    ui.scan_windows(path)
  end
  local f=io.open(path..'.buttons')
  if f then
    local version=tonumber(f:read('*l'))
    if version==generation then
      local result={Toolbar={},Transport={}}
      for line in f:lines() do
        local name,command,label,x,y,w,h=line:match('^([^\t]+)\t(%d+)\t([^\t]+)\t(-?%d+)\t(-?%d+)\t(%d+)\t(%d+)$')
        if result[name] then result[name][#result[name]+1]={command=tonumber(command),label=label,rect={tonumber(x),tonumber(y),tonumber(w),tonumber(h)}} end
      end
      for name,buttons in pairs(result) do
        table.sort(buttons,function(a,b) if a.rect[2]~=b.rect[2] then return a.rect[2]<b.rect[2] else return a.rect[1]<b.rect[1] end end)
        local old=ui.current(name)
        if old then for i,button in ipairs(buttons) do if button.command==old.command then ui.selection[name]=i end end end
        ui.selection[name]=math.min(math.max(1,ui.selection[name]),#buttons)
      end
      ui.buttons=result
    end
    f:close()
  end
end
function ui.current(name)
  return ui.buttons[name] and ui.buttons[name][ui.selection[name]]
end
function ui.move(name,direction,choose)
  local rectangles={}
  for i,button in ipairs(ui.buttons[name] or {}) do rectangles[i]=button.rect end
  if #rectangles>0 then ui.selection[name]=choose(rectangles,math.max(0,ui.selection[name]-1),direction)+1 end
end
return ui
