"""Check fallback subtitle lifecycle, geometry and non-interactive markup."""

from pathlib import Path
import xml.etree.ElementTree as ET

from lupa import LuaRuntime


SCRIPT = Path('mod/UI/RemselysAlexanderII_DealSubtitle.lua')
MARKUP = Path('mod/UI/RemselysAlexanderII_DealSubtitle.xml')


def make_overlay():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      handlers = {}; hidden = true; screenWidth = 1920; screenHeight = 1080;
      leader = 'LEADER_REMSELY_ALEXANDER_II'; removed = false;
      LuaEvents = { REMSELY_DealSubtitle = {
        Add = function(f) table.insert(handlers, f) end,
        Remove = function(f) removed = f == handlers[1] end,
      }};
      PlayerConfigurations = {[1] = {GetLeaderTypeName=function() return leader end}};
      ContextPtr = {
        SetHide = function(self, v) hidden = v end,
        SetShutdown = function(self, f) shutdown = f end,
      };
      UIManager = {GetScreenSizeVal=function(self) return screenWidth, screenHeight end};
      label = {height=24}; box = {hidden=true};
      function label:SetText(s) self.text=s end
      function label:SetWrapWidth(w) self.wrap=w end
      function label:GetSizeY() return self.height end
      function box:SetHide(v) self.hidden=v end
      function box:SetSizeVal(w,h) self.width=w; self.height=h end
      function box:SetOffsetVal(x,y) self.x=x; self.y=y end
      Controls = {SubtitleBox=box, SubtitleText=label};
      function emit(id, text, rightEdge, hiddenBubble)
        for _, f in ipairs(handlers) do f(id, text, rightEdge, hiddenBubble) end
      end
    ''')
    lua.execute(SCRIPT.read_text(encoding='utf-8'))
    return lua


def test_uses_resolved_text_and_stays_outside_trade_panel():
    lua = make_overlay()
    lua.execute("emit(1, 'Что вы желаете обсудить?', 1045, true)")
    assert not lua.eval('hidden')
    assert lua.eval('label.text') == 'Что вы желаете обсудить?'
    assert lua.eval('box.x') > 1045
    assert lua.eval('box.x + box.width') <= lua.eval('screenWidth')
    assert lua.eval('box.y + box.height') <= lua.eval('screenHeight')
    lua.execute("emit(1, 'Эти условия неприемлемы.', 1045, true)")
    assert lua.eval('label.text') == 'Эти условия неприемлемы.'


def test_hides_on_close_visible_vanilla_bubble_or_other_leader():
    lua = make_overlay()
    lua.execute("emit(1, 'text', 1045, true); emit(1, '', nil, false)")
    assert lua.eval('hidden and box.hidden')
    lua.execute("emit(1, 'text', 1045, false)")
    assert lua.eval('hidden and box.hidden')
    lua.execute("leader='LEADER_OTHER'; emit(1, 'text', 1045, true)")
    assert lua.eval('hidden and box.hidden')
    lua.execute('shutdown()')
    assert lua.eval('removed')


def test_insufficient_space_or_unknown_geometry_fails_closed():
    lua = make_overlay()
    for expression in [
        "emit(1, 'text', nil, true)",
        "emit(1, 'text', 0/0, true)",
        "emit(1, 'text', math.huge, true)",
        "emit(1, 'text', 1700, true)",
        "label.height=180; emit(1, 'text', 1045, true)",
        "label.height=0; emit(1, 'text', 1045, true)",
        "emit(nil, 'text', 1045, true)",
        "function label:GetSizeY() error('unavailable') end; emit(1, 'text', 1045, true)",
    ]:
        lua.execute(expression)
        assert lua.eval('hidden and box.hidden'), expression


def test_subtitle_markup_never_consumes_mouse():
    root = ET.parse(MARKUP).getroot()
    assert root.tag == 'Context'
    assert not root.findall('.//Button')
    for element in (root, root.find('./Grid'), root.find('./Grid/Label')):
        assert element is not None
        for attr in ('ConsumeAllMouse', 'ConsumeMouseButton', 'ConsumeMouseOver', 'ConsumeMouseWheel'):
            assert element.get(attr) == '0'
