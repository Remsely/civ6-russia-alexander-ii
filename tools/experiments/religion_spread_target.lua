-- Experimental, not imported by the mod. Mirrors the target selection in the
-- audited Gathering Storm GameCore build; caller must establish event timing.
local M = {}

-- `noForeignSpread` must be a real boolean from UnitReligion, never a guess.
-- The map and city APIs are supplied by the caller to allow isolated testing.
function M.find(x, y, unitOwner, noForeignSpread, getAdjacent, getCity)
    if type(x) ~= "number" or type(y) ~= "number" or type(unitOwner) ~= "number"
        or type(noForeignSpread) ~= "boolean" then return nil end

    local city = getCity(x, y)
    if city ~= nil and city:GetOwner() == unitOwner then return city end

    for direction = 0, 5 do
        local plot = getAdjacent(x, y, direction)
        if plot ~= nil then
            city = getCity(plot:GetX(), plot:GetY())
            if city ~= nil and (not noForeignSpread or city:GetOwner() == unitOwner) then
                return city
            end
        end
    end
    return nil
end

return M
