"""The whole 3D leader from art/3d/alexander_assembly.blend: build_uniform.py, build_details.py, build_head.py (in the
rest pose, into alexander_rest.blend), build_pose.py (the portrait's stance, cloth settled: alexander_leader.blend),
build_regalia.py (epaulettes, sash, aiguillettes on the posed uniform, hanging as they would), build_orders.py
(orders, medals, the sabre), build_dangles.py (bones for what swings loose), build_bake.py (the uniform's ambient occlusion) in background Blender (env BLENDER or
the default 4.5 install), each one's last lines printed; stops on the first error.
    python art/3d/build_all.py [--from uniform|details|head|pose|regalia|orders|dangles|bake] [--to <step>]
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.environ.get('BLENDER', r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe')
STEPS = [('uniform', 'alexander_assembly.blend'), ('details', 'alexander_rest.blend'), ('head', 'alexander_rest.blend'),
         ('pose', 'alexander_rest.blend'), ('regalia', 'alexander_leader.blend'), ('orders', 'alexander_leader.blend'),
         ('dangles', 'alexander_leader.blend'), ('bake', 'alexander_leader.blend')]
start = sys.argv[sys.argv.index('--from') + 1] if '--from' in sys.argv else 'uniform'
stop = sys.argv[sys.argv.index('--to') + 1] if '--to' in sys.argv else 'bake'
order = [s for s, _ in STEPS]
for name, blend in STEPS[order.index(start):order.index(stop) + 1]:
    p = subprocess.run([BLENDER, '-b', os.path.join(HERE, blend), '--python-exit-code', '1', '--python',
                        os.path.join(HERE, 'build_%s.py' % name)], capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    out = [l for l in (p.stdout + p.stderr).splitlines() if l.strip() and 'MCP' not in l]
    print('== build_%s.py' % name)
    print('\n'.join(out[-40:] if p.returncode else [l for l in out if not l.startswith(('Blender', 'Read blend', 'Info'))][-12:]))
    if p.returncode:
        sys.exit('build_%s.py failed' % name)
