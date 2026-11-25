-- EXPERIMENT ONLY: do not register as gameplay script.
-- Maps documented-by-disassembly GameEffects return types to the pure
-- religion_modifier_attach.ensure interface.  Native runtime availability,
-- load/save behavior and performance are not confirmed by Lua stubs.
local M = {}

function M.new(effects,players)
    assert(type(effects)=="table" and type(players)=="table")
    assert(type(effects.GetModifiers)=="function" and type(effects.GetModifierDefinition)=="function")
    assert(type(effects.GetModifierOwner)=="function" and type(effects.GetObjectsPlayerId)=="function")
    return {
        instances=function()
            -- GameCore::Lua::IGameEffects::lGetModifiers creates a Lua array
            -- of integer instance handles; never alter its returned table.
            return effects.GetModifiers()
        end,
        describe=function(instance,wanted)
            -- lGetModifierDefinition returns table.Id = definition string,
            -- not instance handle; nil means snapshot became invalid.
            local definition=effects.GetModifierDefinition(instance)
            assert(type(definition)=="table" and type(definition.Id)=="string", "definition unavailable")
            -- Most game effects have unrelated owners or no owner at all.
            -- Do not inspect them just to establish that their IDs differ.
            if type(wanted)=="table" and not wanted[definition.Id] then return definition.Id,-1 end
            -- Owner is an object handle, not a player ID. Ownerless and
            -- non-player objects have no player ID and cannot match leader.
            local object=effects.GetModifierOwner(instance)
            local owner=-1
            if object~=nil then
                assert(type(object)=="number", "invalid owner handle")
                local result=effects.GetObjectsPlayerId(object)
                if result~=nil then owner=result end
            end
            return definition.Id,owner
        end,
        attach=function(leader,name)
            local player=players[leader]
            assert(player~=nil and type(player.AttachModifierByID)=="function", "player unavailable")
            return player:AttachModifierByID(name)
        end,
    }
end
return M
