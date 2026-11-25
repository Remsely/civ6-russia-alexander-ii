"""Compare the experimental Lua target selector to the installed GS DLL.

Run with ``--dll PATH`` and pefile, unicorn, and lupa installed. The native
function's surrounding map and city APIs are controlled stubs: this verifies
selection order and owner restrictions, not Civ's real map or event timing.
The Lua neighbor list is supplied from the same DLL direction constants; this
is not an independent test of Map.GetAdjacentPlot or wrapping/map boundaries.
The script reads game bytes locally and refuses any unrecognised DLL build.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import struct
from pathlib import Path

import pefile
from lupa import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_64
from unicorn.x86_const import UC_X86_REG_R8, UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_RSP

SHA256 = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
START, END = 0x673560, 0x6736E5
STACK, DATA, STUB, RET = 0x10000000, 0x11000000, 0x12000000, 0x12000F00
UNIT, PLOT, ATTR, CITY, MAP, VTABLE = (DATA + n for n in (0x1000, 0x3000, 0x4000, 0x5000, 0x7000, 0x8000))
PLOT_ATTR, MAP_PLOT = STUB + 0x10, STUB + 0x20


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.dll.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Unrecognised DLL: target algorithm has not been verified for this build")
    pe = pefile.PE(str(args.dll))
    directions_x = struct.unpack("<6i", pe.get_data(0xB61670, 24))
    directions_y = struct.unpack("<6i", pe.get_data(0xB61688, 24))
    lua = LuaRuntime(unpack_returned_tuples=True)
    selector = lua.execute(Path("tools/experiments/religion_spread_target.lua").read_text(encoding="utf-8"))["find"]
    make_functions = lua.eval('''function(cities, neighbors)
      local function city(x,y) return cities[tostring(x)..","..tostring(y)] end
      local function adjacent(x,y,d) return neighbors[d+1] end
      return adjacent, city
    end''')
    make_city = lua.eval('function(owner) return {GetOwner=function() return owner end} end')
    make_plot = lua.eval('function(x,y) return {GetX=function() return x end, GetY=function() return y end} end')

    rng = random.Random(271828)
    for case in range(512):
        x, y = rng.randrange(1, 80), rng.randrange(1, 60)
        owner, restricted = rng.randrange(4), bool(case & 1)
        neighbors = [(x - y // 2 + directions_x[d] + (y + directions_y[d]) // 2,
                      y + directions_y[d]) for d in range(6)]
        positions = [(x, y), *neighbors]
        cities = {pos: rng.randrange(4) for pos in positions if rng.randrange(3) == 0}
        cpu = Uc(UC_ARCH_X86, UC_MODE_64)
        for address, size in ((0x670000, 0x4000), (0x40000, 0x50000), (0xB61000, 0x1000),
                              (STACK, 0x10000), (DATA, 0x10000), (STUB, 0x1000)):
            cpu.mem_map(address, size)
        cpu.mem_write(START, pe.get_data(START, END - START))
        cpu.mem_write(0xB61670, pe.get_data(0xB61670, 48))
        for address in (0x5E770, 0x42F20, 0x44D40, PLOT_ATTR, MAP_PLOT):
            cpu.mem_write(address, b"\xc3")

        def put32(addr, value): cpu.mem_write(addr, struct.pack("<i", value))
        def put64(addr, value): cpu.mem_write(addr, struct.pack("<Q", value))

        put32(UNIT + 0x128, owner)
        cpu.mem_write(UNIT + 0xA25, bytes([restricted]))
        put64(MAP, VTABLE + 0x100)
        put64(VTABLE + 0x100 + 0x58, MAP_PLOT)
        plots = {}
        for idx, (px, py) in enumerate(positions):
            plot, attr = PLOT + idx * 0x100, ATTR + idx * 0x100
            plots[(px, py)] = plot
            put64(plot, VTABLE)
            put64(VTABLE + 0x30, PLOT_ATTR)
            cpu.mem_write(plot + 0x28, struct.pack("<hh", px, py))
            cpu.mem_write(attr + 0x1C, struct.pack("b", cities.get((px, py), -1)))
            put64(plot + 0x80, attr)
        for idx, (pos, city_owner) in enumerate(cities.items()):
            put32(CITY + idx * 0x100 + 0xD8, city_owner)
        native_city = {pos: CITY + idx * 0x100 for idx, pos in enumerate(cities)}

        def on_code(machine, address, size, user):
            rcx = machine.reg_read(UC_X86_REG_RCX)
            if address == PLOT_ATTR:
                machine.reg_write(UC_X86_REG_RAX, struct.unpack("<Q", machine.mem_read(rcx + 0x80, 8))[0])
            elif address == 0x5E770:
                machine.reg_write(UC_X86_REG_RAX, int(struct.unpack("b", machine.mem_read(rcx + 0x1C, 1))[0] >= 0))
            elif address == 0x42F20:
                coord = struct.unpack("<ii", machine.mem_read(rcx, 8))
                machine.reg_write(UC_X86_REG_RAX, native_city.get(coord, 0))
            elif address == 0x44D40:
                machine.reg_write(UC_X86_REG_RAX, MAP)
            elif address == MAP_PLOT:
                pos = (machine.reg_read(UC_X86_REG_RDX) & 0xFFFFFFFF, machine.reg_read(UC_X86_REG_R8) & 0xFFFFFFFF)
                machine.reg_write(UC_X86_REG_RAX, plots.get(pos, 0))

        cpu.hook_add(UC_HOOK_CODE, on_code)
        # Windows x64 entry: RSP is 8 modulo 16 after the caller's call.
        put64(STACK + 0x8008, RET)
        cpu.reg_write(UC_X86_REG_RSP, STACK + 0x8008)
        cpu.reg_write(UC_X86_REG_RDX, UNIT)
        cpu.reg_write(UC_X86_REG_R8, plots[(x, y)])
        cpu.emu_start(START, RET)
        result = cpu.reg_read(UC_X86_REG_RAX)
        native_pos = next((pos for pos, pointer in native_city.items() if pointer == result), None)

        lua_cities = lua.table()
        for pos, city_owner in cities.items():
            item = make_city(city_owner)
            # Include coordinates in the object so the result can be identified.
            item["x"], item["y"] = pos
            lua_cities[f"{pos[0]},{pos[1]}"] = item
        lua_neighbors = lua.table_from([make_plot(*pos) for pos in neighbors])
        get_adjacent, get_city = make_functions(lua_cities, lua_neighbors)
        picked = selector(x, y, owner, restricted, get_adjacent, get_city)
        lua_pos = (picked["x"], picked["y"]) if picked is not None else None
        assert lua_pos == native_pos, (case, owner, restricted, cities, native_pos, lua_pos)
    print("PASS: 512 deterministic native-vs-Lua cases, 0 mismatches")
    print("Controlled map/owner stubs only; Map.GetAdjacentPlot, boundaries, event order, stale positions and other game versions remain untested.")


if __name__ == "__main__":
    main()
