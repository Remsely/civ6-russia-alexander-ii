"""Exercise the actual deal-view wildcard extension using vanilla-like stubs."""
from pathlib import Path

from lupa import LuaRuntime


HOOK = Path('mod/UI/DiplomacyDealView_REMSELY_Voice.lua')


def make_view():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
        lines = {}; calls = {}; shown = false; other = "LEADER_REMSELY_ALEXANDER_II";
        ms_OtherPlayerID = 2; finalKey = "LOC_DIPLO_DEAL_UNFAIR";
        PlayerConfigurations = {[2] = {GetLeaderTypeName = function() return other end}};
        isHuman = false; Players = {[2] = {IsHuman = function() return isHuman end}};
        ContextPtr = {IsHidden = function() return not shown end};
        dealUpdatedHandlers = {};
        LuaEvents = {
          REMSELY_DealLine = function(id, key) table.insert(calls, {id, key}) end,
          REMSELY_DealClosed = function(id) table.insert(calls, {id, "CLOSED"}) end,
          DiploPopup_DealUpdated = {
            Add = function(f) table.insert(dealUpdatedHandlers, f) end,
            Remove = function(f)
              for i = #dealUpdatedHandlers, 1, -1 do
                if dealUpdatedHandlers[i] == f then table.remove(dealUpdatedHandlers, i) end
              end
            end,
          },
        };
        function SetLeaderDialog(key, effect) table.insert(lines, {key, effect}) end
        function UpdateDealStatus() SetLeaderDialog(finalKey, "EFFECT") end
        -- Vanilla registers this callback before the wildcard include. Its
        -- body looks up SetLeaderDialog and UpdateDealStatus at execution time.
        hasIncomingDeal = true;
        function OnDealUpdated(id, action, text)
          if not ContextPtr:IsHidden() then
            if text ~= nil and text ~= "" then SetLeaderDialog(text, "") end
            if hasIncomingDeal then UpdateDealStatus() end
          end
        end
        LuaEvents.DiploPopup_DealUpdated.Add(OnDealUpdated);
        function FireDealUpdated(id, action, text)
          for _, fn in ipairs(dealUpdatedHandlers) do fn(id, action, text) end
        end
        function OnShow()
          shown = true;
          SetLeaderDialog("LOC_DIPLO_DEAL_INTRO", "");
          UpdateDealStatus();
        end
        function OnHide() shown = false end
        function OnShutdown() end
    ''')
    lua.execute(HOOK.read_text(encoding='utf-8'))
    return lua


def test_batches_opening_and_deduplicates_repeated_status_refresh():
    lua = make_view()
    lua.execute('OnShow(); UpdateDealStatus(); UpdateDealStatus()')
    assert lua.eval('#calls') == 1
    assert lua.eval('calls[1][2]') == 'LOC_DIPLO_DEAL_UNFAIR'
    assert lua.eval('lines[1][1]') == 'LOC_DIPLO_DEAL_INTRO_REMSELY_ALEXANDER_II'
    assert lua.eval('lines[2][1]') == 'LOC_DIPLO_DEAL_UNFAIR_REMSELY_ALEXANDER_II'
    assert lua.eval('lines[2][2]') == 'EFFECT'


def test_changed_or_unvoiced_line_and_reopening():
    lua = make_view()
    lua.execute('''
        OnShow(); finalKey = "LOC_DIPLO_DEAL_LEADER_GIFT"; UpdateDealStatus();
        finalKey = "LOC_DIPLO_SOMETHING_ELSE"; UpdateDealStatus();
        OnHide(); finalKey = "LOC_DIPLO_DEAL_UNFAIR"; OnShow();
    ''')
    assert [lua.eval(f'calls[{i}][2]') for i in range(1, 6)] == [
        'LOC_DIPLO_DEAL_UNFAIR', 'LOC_DIPLO_DEAL_LEADER_GIFT', '', 'CLOSED',
        'LOC_DIPLO_DEAL_UNFAIR',
    ]


def test_other_leaders_and_hidden_view_never_dispatch_or_relocalize():
    lua = make_view()
    lua.execute('''
        other = "LEADER_OTHER"; OnShow(); UpdateDealStatus(); OnHide();
        other = "LEADER_REMSELY_ALEXANDER_II"; UpdateDealStatus();
    ''')
    assert lua.eval('#calls') == 0
    assert lua.eval('lines[1][1]') == 'LOC_DIPLO_DEAL_INTRO'
    assert lua.eval('lines[2][1]') == 'LOC_DIPLO_DEAL_UNFAIR'


def test_other_human_controlling_alexander_is_not_given_ai_speech():
    lua = make_view()
    lua.execute('isHuman = true; OnShow(); UpdateDealStatus(); OnHide()')
    assert lua.eval('#calls') == 0
    assert lua.eval('lines[1][1]') == 'LOC_DIPLO_DEAL_INTRO'


def test_all_eleven_deal_strings_reach_the_matching_leader_specific_key():
    keys = [
        'LOC_DIPLOMACY_DEAL_INVALID', 'LOC_DIPLO_DEAL_INTRO',
        'LOC_DIPLO_DEAL_INTRO_AI', 'LOC_DIPLO_DEAL_LEADER_DEMAND',
        'LOC_DIPLO_DEAL_LEADER_EQUALIZE_FAILED',
        'LOC_DIPLO_DEAL_LEADER_EQUALIZE_SUCCEEDED', 'LOC_DIPLO_DEAL_LEADER_GIFT',
        'LOC_DIPLO_DEAL_LEADER_GIFT_EQUALIZE_FAILED',
        'LOC_DIPLO_DEAL_UNACCEPTABLE_DEAL', 'LOC_DIPLO_DEAL_UNFAIR',
        'LOC_DIPLO_DEMAND_INTRO',
    ]
    lua = make_view()
    lua.execute('shown = true')
    for i, key in enumerate(keys, 1):
        lua.globals().finalKey = key
        lua.execute('UpdateDealStatus()')
        assert lua.eval(f'lines[{i}][1]') == key + '_REMSELY_ALEXANDER_II'
        assert lua.eval(f'calls[{i}][2]') == key


def test_deal_updated_intermediate_resolved_text_does_not_play_before_final_key():
    lua = make_view()
    lua.execute('''
        OnShow(); finalKey = "LOC_DIPLO_DEAL_LEADER_EQUALIZE_SUCCEEDED";
        FireDealUpdated(2, 0, "Already localized intermediate text")
    ''')
    assert lua.eval('#calls') == 2
    assert lua.eval('calls[2][2]') == 'LOC_DIPLO_DEAL_LEADER_EQUALIZE_SUCCEEDED'
    assert lua.eval('lines[3][1]') == 'Already localized intermediate text'
    assert lua.eval('lines[4][1]') == (
        'LOC_DIPLO_DEAL_LEADER_EQUALIZE_SUCCEEDED_REMSELY_ALEXANDER_II')


def test_deal_updated_without_incoming_deal_stops_stale_speech():
    lua = make_view()
    lua.execute('''
        OnShow(); hasIncomingDeal = false;
        FireDealUpdated(2, 0, "Already localized new text");
    ''')
    assert lua.eval('#calls') == 2
    assert lua.eval('calls[2][2]') == ''
    lua.execute('OnShutdown()')
    assert lua.eval('#dealUpdatedHandlers') == 1
