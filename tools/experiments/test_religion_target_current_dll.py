"""Run the existing 512 native-vs-Lua cases against the current XP2 DLL.

The emulated map and external calls are controlled stubs. Event timing, real
map boundaries and the live game's complete behavior are not established.
"""
import test_religion_target_native as original


if __name__ == "__main__":
    # The independently audited target function moved by 0x40 in this build.
    # Its six direction tables and stubbed external call RVAs are unchanged.
    # The original main performs the SHA check before reading or executing it.
    original.SHA256 = "4de40abf7c739f53c1f3f825863ace84dc220e5a42d87620e56fceaf3fbd4dc8"
    original.START, original.END = 0x6735A0, 0x673725
    original.main()
