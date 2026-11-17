"""Run the gameplay Lua against a tiny deterministic railway map."""
from pathlib import Path
import random
import subprocess
from lupa import LuaRuntime


def test_generated_maps_match_original_algorithm():
    # Pin the actual pre-optimization implementation; HEAD changes after commit.
    old = subprocess.check_output(['git', 'show', 'cb77bcc:mod/Lua/RemselysAlexanderII_Railways.lua'], text=True, encoding='utf-8')
    new = Path('mod/Lua/RemselysAlexanderII_Railways.lua').read_text(encoding='utf-8')
    rnd = random.Random(841)
    for scenario in range(35):
        city_indices = sorted(rnd.sample(range(64), 14))
        own = set(rnd.sample(city_indices, 6))
        rails = set(rnd.sample(range(64), rnd.randrange(10, 55)))
        populations = {i: rnd.randrange(1, 20) for i in own}
        setup = '''
          function event() local e={}; e.Add=function(f) e.handler=f end; return e end
          Events={RouteChanged=event(),RouteAddedToMap=event(),RouteRemovedFromMap=event(),TurnBegin=event()}
          GameInfo={Routes={ROUTE_RAILROAD={Index=1}}}; DirectionTypes={NUM_DIRECTION_TYPES=2}
          plots={}; cities={}
          for i=0,63 do
            local p={i=i,rail=0,owner=-1,props={}}
            function p:GetIndex() return self.i end; function p:GetX() return self.i end
            function p:GetY() return 0 end; function p:GetRouteType() return self.rail end
            function p:IsCity() return self.owner>=0 end; function p:GetOwner() return self.owner end
            function p:GetProperty(k) return self.props[k] end; function p:SetProperty(k,v) self.props[k]=v end
            plots[i]=p
          end
          Map={GetPlotCount=function() return 64 end, GetPlotByIndex=function(i) return plots[i] end,
            GetPlot=function(x,y) return plots[x] end,
            GetAdjacentPlot=function(x,y,d) return plots[x+(d==0 and -1 or 1)] end}
          Players={[0]={IsAlive=function() return true end,GetCities=function() return {Members=function() return ipairs(cities) end} end}}
          PlayerConfigurations={[0]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end},
            [1]={GetLeaderTypeName=function() return 'OTHER' end}}
          PlayerManager={GetWasEverAliveCount=function() return 1 end}
          function addCity(i,owner,pop)
            plots[i].owner=owner
            if owner==0 then table.insert(cities,{GetLocation=function() return i end,GetPopulation=function() return pop end}) end
          end
        '''
        runtimes = []
        for source in [old, new]:
            lua = LuaRuntime(unpack_returned_tuples=True)
            lua.execute(setup)
            for i in rails: lua.globals().plots[i].rail = 1
            for i in city_indices: lua.globals().addCity(i, 0 if i in own else 1, populations.get(i, 5))
            lua.execute(source)
            runtimes.append(lua)
        def compare():
            left, right = [x.globals().plots for x in runtimes]
            for i in own:
                for kind in ['OWN', 'FOREIGN']:
                    expected = left[i].props[f'REMSELY_RAIL_{kind}_N'] or 0
                    actual = sum(bit * (right[i].props[f'REMSELY_RAIL_{kind}_BIT_{bit}'] or 0) for bit in [1,2,4,8,16,32,64,128])
                    assert expected == actual, (scenario, i, kind, expected, actual)
        compare()
        for i in rnd.sample(range(64), 8):
            for lua in runtimes:
                plot = lua.globals().plots[i]
                plot.rail = 0 if plot.rail == 1 else 1
                lua.globals().Events.RouteChanged.handler(i, 0)
            compare()


def test_recomputation_writes_only_real_changes_and_ignores_foreign_growth():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      function event() local e = {}; e.Add = function(f) e.handler = f end; return e end
      Events = { RouteAddedToMap=event(), RouteChanged=event(), RouteRemovedFromMap=event(),
        CityAddedToMap=event(), CityRemovedFromMap=event(), CityPopulationChanged=event(), TurnBegin=event() }
      GameInfo={Routes={ROUTE_RAILROAD={Index=1}}}; DirectionTypes={NUM_DIRECTION_TYPES=2}
      writes=0; scans=0; plots={}; cities={}
      for i=0,2 do
        local p={i=i, owner=(i==2 and 1 or 0), props={}, rail=1}
        function p:GetIndex() return self.i end
        function p:GetX() return self.i end
        function p:GetY() return 0 end
        function p:GetRouteType() return self.rail end
        function p:IsCity() return true end
        function p:GetOwner() return self.owner end
        function p:GetProperty(k) return self.props[k] end
        function p:SetProperty(k,v) writes=writes+1; self.props[k]=v end
        plots[i]=p
        local c={i=i,pop=10}
        function c:GetLocation() return self.i end
        function c:GetPopulation() return self.pop end
        if i<2 then cities[#cities+1]=c end
      end
      Map={GetPlotCount=function() return 3 end,
        GetPlotByIndex=function(i) scans=scans+1; return plots[i] end,
        GetPlot=function(i) return plots[i] end,
        GetAdjacentPlot=function(x,y,d) return plots[x+(d==0 and -1 or 1)] end}
      Players={[0]={IsAlive=function() return true end,GetCities=function() return {
        Members=function() return ipairs(cities) end} end}}
      PlayerConfigurations={[0]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end},
        [1]={GetLeaderTypeName=function() return 'LEADER_OTHER' end}}
      PlayerManager={GetWasEverAliveCount=function() return 1 end}
    ''')

    source = Path('mod/Lua/RemselysAlexanderII_Railways.lua').read_text(encoding='utf-8')
    lua.execute(source)
    lua.execute('''
      assert(plots[0].props.REMSELY_RAIL_OWN_BIT_1 == 1 and plots[0].props.REMSELY_RAIL_FOREIGN_BIT_1 == 1)
      local before, reads=writes,scans
      Events.TurnBegin.handler()
      assert(writes==before, 'unchanged turn rewrote properties')
      reads=scans; Events.CityPopulationChanged.handler(1, 123)
      assert(scans==reads, 'foreign city growth scanned map')
      cities[1].pop=1; Events.CityPopulationChanged.handler(0, 123)
      assert(writes==before, 'unchanged capped values rewrote properties')
      plots[2].owner=0; cities[3]={i=2,pop=10,GetLocation=function(self) return self.i end,GetPopulation=function(self) return self.pop end}
      Events.CityAddedToMap.handler()
      assert(plots[0].props.REMSELY_RAIL_FOREIGN_BIT_1 == 0)
      assert(plots[1].props.REMSELY_RAIL_OWN_BIT_2 == 1)
      plots[1].owner=1; table.remove(cities,2); Events.CityRemovedFromMap.handler()
      assert(plots[1].props.REMSELY_RAIL_OWN_BIT_1 == 0 and plots[1].props.REMSELY_RAIL_FOREIGN_BIT_1 == 0)
      local beforeScan = scans
      Events.RouteChanged.handler(0,0)
      assert(scans==beforeScan, 'unchanged rail caused full scan')
      plots[0].rail=0; Events.RouteChanged.handler(0,0)
      assert(scans>beforeScan, 'removal of a rail must recalculate')
      beforeScan=scans; Events.RouteChanged.handler(0,0)
      assert(scans==beforeScan, 'ordinary road caused full scan')
      plots[0].rail=1; Events.RouteChanged.handler(0,0)
      assert(scans>beforeScan, 'adding rail must recalculate')
      beforeScan=scans; Events.RouteRemovedFromMap.handler(0,0)
      assert(scans>beforeScan, 'undocumented remove event must take conservative path')
      beforeScan=scans; Events.RouteAddedToMap.handler()
      assert(scans>beforeScan, 'undocumented add event must take conservative path')
    ''')


def test_bridge_disconnect_reconnect_and_migration():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      function event() return { Add=function(f) return f end } end
      function capture() local e={}; e.Add=function(f) e.handler=f end; return e end
      Events={RouteChanged=capture(),RouteAddedToMap=capture(),RouteRemovedFromMap=capture(),TurnBegin=capture()}
      GameInfo={Routes={ROUTE_RAILROAD={Index=1}}}; DirectionTypes={NUM_DIRECTION_TYPES=2}
      plots={}; cities={}; writes=0
      for i=0,6 do
        local p={i=i, rail=(i==1 or i==2 or i==4 or i==5) and 1 or 0,
          city=(i==0 or i==3 or i==6), owner=(i==6 and 1 or 0),props={}}
        function p:GetIndex() return self.i end; function p:GetX() return self.i end
        function p:GetY() return 0 end; function p:GetRouteType() return self.rail end
        function p:IsCity() return self.city end; function p:GetOwner() return self.owner end
        function p:GetProperty(k) return self.props[k] end
        function p:SetProperty(k,v) self.props[k]=v; writes=writes+1 end
        plots[i]=p
        if i==0 or i==3 then table.insert(cities,{GetLocation=function() return i end,GetPopulation=function() return 20 end}) end
      end
      plots[0].props.REMSELY_RAIL_OWN_N=19
      Map={GetPlotCount=function() return 7 end, GetPlotByIndex=function(i) return plots[i] end,
        GetPlot=function(x,y) return plots[x] end,
        GetAdjacentPlot=function(x,y,d) return plots[x+(d==0 and -1 or 1)] end}
      Players={[0]={IsAlive=function() return true end,GetCities=function() return {Members=function() return ipairs(cities) end} end}}
      PlayerConfigurations={[0]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end},
        [1]={GetLeaderTypeName=function() return 'LEADER_OTHER' end}}
      PlayerManager={GetWasEverAliveCount=function() return 1 end}
    ''')

    lua.execute(Path('mod/Lua/RemselysAlexanderII_Railways.lua').read_text(encoding='utf-8'))
    lua.execute('''
      assert(plots[0].props.REMSELY_RAIL_OWN_N==0)
      assert(plots[0].props.REMSELY_RAIL_OWN_BIT_1==1 and plots[0].props.REMSELY_RAIL_FOREIGN_BIT_1==1)
      local original=writes
      for i=1,500 do Events.RouteAddedToMap.handler() end
      assert(writes==original, 'unchanged route events must not change yields')
      plots[2].rail=0; Events.RouteChanged.handler(2,0)
      assert(plots[0].props.REMSELY_RAIL_OWN_BIT_1==0 and plots[0].props.REMSELY_RAIL_FOREIGN_BIT_1==0)
      plots[2].rail=1; Events.RouteAddedToMap.handler()
      assert(plots[0].props.REMSELY_RAIL_OWN_BIT_1==1 and plots[0].props.REMSELY_RAIL_FOREIGN_BIT_1==1)
      plots[4].rail=0; Events.RouteRemovedFromMap.handler()
      assert(plots[0].props.REMSELY_RAIL_FOREIGN_BIT_1==0)
    ''')


def test_bulk_events_do_not_rebuild_the_graph_for_unchanged_roads():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      function capture() local e={}; e.Add=function(f) e.handler=f end; return e end
      Events={RouteAddedToMap=capture(),CityAddedToMap=capture(),RouteChanged=capture()}
      GameInfo={Routes={ROUTE_RAILROAD={Index=1}}}; DirectionTypes={NUM_DIRECTION_TYPES=2}
      plots={}; mapReads=0; neighbors=0; writes=0
      for i=0,4999 do
        local p={i=i,rail=(i<100 and i%2==1) and 1 or 0, city=(i==0),props={}}
        function p:GetIndex() return self.i end; function p:GetX() return self.i end
        function p:GetY() return 0 end; function p:GetRouteType() return self.rail end
        function p:IsCity() return self.city end; function p:GetOwner() return 0 end
        function p:GetProperty(k) return self.props[k] end
        function p:SetProperty(k,v) self.props[k]=v; writes=writes+1 end
        plots[i]=p
      end
      Map={GetPlotCount=function() return 5000 end,
        GetPlotByIndex=function(i) mapReads=mapReads+1; return plots[i] end,
        GetPlot=function(x,y) return plots[x] end,
        GetAdjacentPlot=function(x,y,d) neighbors=neighbors+1; return plots[x+(d==0 and -1 or 1)] end}
      Players={[0]={IsAlive=function() return true end,GetCities=function() return {
        Members=function() return ipairs({{GetLocation=function() return 0 end,GetPopulation=function() return 10 end}}) end} end}}
      PlayerConfigurations={[0]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end}}
      PlayerManager={GetWasEverAliveCount=function() return 1 end}
    ''')
    lua.execute(Path('mod/Lua/RemselysAlexanderII_Railways.lua').read_text(encoding='utf-8'))
    lua.execute('''
      local initialNeighbors, initialWrites = neighbors, writes
      for i=1,1000 do Events.RouteAddedToMap.handler() end
      for i=1,1000 do Events.CityAddedToMap.handler(0, 123, 0, 0) end
      assert(neighbors==initialNeighbors, 'unchanged events rebuilt graph')
      assert(writes==initialWrites, 'unchanged events rewrote properties')
      -- Undocumented route events still require a conservative map scan.
      assert(mapReads>=5000000)
    ''')


def test_no_living_alexander_skips_map_scans_and_revival_resyncs():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      function capture() local e={}; e.Add=function(f) e.handler=f end; return e end
      Events={RouteChanged=capture(),RouteAddedToMap=capture(),RouteRemovedFromMap=capture(),
        CityAddedToMap=capture(),CityRemovedFromMap=capture(),CityPopulationChanged=capture(),TurnBegin=capture()}
      GameInfo={Routes={ROUTE_RAILROAD={Index=1}}}; DirectionTypes={NUM_DIRECTION_TYPES=2}
      alive=false; mapReads=0; plots={}
      for i=0,2 do
        local p={i=i,rail=0, city=(i==0 or i==2), owner=(i==2 and 1 or 0),props={}}
        function p:GetIndex() return self.i end; function p:GetX() return self.i end
        function p:GetY() return 0 end; function p:GetRouteType() return self.rail end
        function p:IsCity() return self.city end; function p:GetOwner() return self.owner end
        function p:GetProperty(k) return self.props[k] end
        function p:SetProperty(k,v) self.props[k]=v end
        plots[i]=p
      end
      plots[0].props.REMSELY_RAIL_OWN_N=19
      Map={GetPlotCount=function() return 3 end,
        GetPlotByIndex=function(i) mapReads=mapReads+1; return plots[i] end,
        GetPlot=function(x,y) mapReads=mapReads+1; return plots[x] end,
        GetAdjacentPlot=function(x,y,d) return plots[x+(d==0 and -1 or 1)] end}
      Players={[0]={IsAlive=function() return alive end,GetCities=function() return {
        Members=function() return ipairs({{GetLocation=function() return 0 end,GetPopulation=function() return 5 end}}) end} end}}
      PlayerConfigurations={[0]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end},
        [1]={GetLeaderTypeName=function() return 'LEADER_OTHER' end}}
      PlayerManager={GetWasEverAliveCount=function() return 1 end}
    ''')
    lua.execute(Path('mod/Lua/RemselysAlexanderII_Railways.lua').read_text(encoding='utf-8'))
    lua.execute('''
      local initialReads=mapReads
      assert(initialReads==0, 'inactive leader must not scan map during initialization')
      for i=1,100 do
        Events.RouteAddedToMap.handler(); Events.RouteRemovedFromMap.handler()
        Events.RouteChanged.handler(1,0); Events.CityAddedToMap.handler(0,1,0,0)
        Events.CityRemovedFromMap.handler(); Events.CityPopulationChanged.handler(0,1)
        Events.TurnBegin.handler()
      end
      assert(mapReads==initialReads, 'inactive leader must not scan or look up map plots')
      -- Network changes while no Alexander is alive; a later resurrection must
      -- rebuild from current map state, not use the outdated startup snapshot.
      plots[1].rail=1; alive=true; Events.RouteChanged.handler(1,0)
      assert(plots[0].props.REMSELY_RAIL_FOREIGN_BIT_1==1, 'revival did not resync topology')
      assert(plots[0].props.REMSELY_RAIL_OWN_N==0, 'deferred migration did not clear legacy properties')
    ''')
