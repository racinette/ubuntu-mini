-- Native panel discovery plus exact theme-image button bounds from the outline
-- process. No clicks or pointer movement; activation uses REAPER action IDs.
local ui = {panels={},buttons={Toolbar={},Transport={}},selection={Toolbar=1,Transport=1}}
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
function ui.scan(now,path)
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
    local parts={theme}
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
