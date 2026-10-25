-- Run with Lua, or load this file in an isolated REAPER ReaScript and pass the
-- path to reaper-control-navigation.lua as its argument.
local choose = assert(loadfile((...) or 'setup/development/reaper-control-navigation.lua'))()
local checks = 0
local function expect(rects, current, direction, expected)
  local actual = choose(rects, current, direction)
  assert(actual == expected, string.format('%d %s: expected %d, got %d', current, direction, expected, actual))
  checks = checks + 1
end
local grid = {{0,0,20,20},{30,0,20,20},{60,0,20,20},{0,30,20,20},{30,30,20,20},{60,30,20,20},false}
for _, transform in ipairs({{0,0,1},{456,123,2},{-200,-300,.5}}) do
  local layout = {}
  for i, rect in ipairs(grid) do
    layout[i] = rect and {rect[1]*transform[3]+transform[1],rect[2]*transform[3]+transform[2],rect[3]*transform[3],rect[4]*transform[3]} or false
  end
  expect(layout,0,'left',0); expect(layout,0,'right',1)
  expect(layout,0,'up',0); expect(layout,0,'down',3)
  expect(layout,1,'down',4); expect(layout,4,'up',1)
  expect(layout,4,'left',3); expect(layout,4,'right',5)
  expect(layout,5,'down',5); expect(layout,5,'right',5)
  expect(layout,2,'left',1); expect(layout,3,'up',0)
end
grid[2] = false
expect(grid,0,'right',2) -- Hidden controls cannot become targets.
expect(grid,4,'up',0) -- Nearest off-axis fallback, deterministic on ties.
expect(grid,6,'down',6) -- Missing origin is handled by the caller's fallback.
local knobs = {{0,0,20,20},{30,0,20,20},{60,-4,20,22},{60,20,20,22}}
expect(knobs,0,'up',0) -- Same-row cosmetic offsets are not another row.
expect(knobs,2,'down',3); expect(knobs,3,'up',2)
expect({{0,0,20,20},false},0,'right',0)
return checks
