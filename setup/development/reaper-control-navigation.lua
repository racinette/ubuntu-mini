-- Choose a visible control in screen space; indices are the controller's
-- zero-based IDs. Missing/hidden rectangles are false entries in the list.
return function(rectangles, current, direction)
  local origin = rectangles[current + 1]
  if not origin then return current end
  local vertical = direction == 'up' or direction == 'down'
  local sign = (direction == 'up' or direction == 'left') and -1 or 1
  local axis, cross = vertical and 2 or 1, vertical and 1 or 2
  local best, best_beam, best_cost = current, math.huge, math.huge
  for index, rect in ipairs(rectangles) do
    if rect and index ~= current + 1 then
      local forward = sign * (rect[axis] + rect[axis + 2] / 2 - origin[axis] - origin[axis + 2] / 2)
      -- Knobs and buttons on one row can differ by a few pixels. Don't treat
      -- that cosmetic difference as a separate row/column.
      local tolerance = math.max(2, math.min(rect[axis + 2], origin[axis + 2]) * .35)
      if forward > tolerance then
        local across = rect[cross] + rect[cross + 2] / 2 - origin[cross] - origin[cross + 2] / 2
        local overlap = math.min(rect[cross] + rect[cross + 2], origin[cross] + origin[cross + 2]) - math.max(rect[cross], origin[cross])
        local beam = overlap > 0 and 0 or 1
        local cost = forward * forward + 4 * across * across
        if beam < best_beam or (beam == best_beam and cost < best_cost) then
          best, best_beam, best_cost = index - 1, beam, cost
        end
      end
    end
  end
  return best -- At an edge, keep the current control and track.
end
