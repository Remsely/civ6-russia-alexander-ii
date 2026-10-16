# Motions to try the leader in (render_leader.py --motion): the body moved by keyframes, and the loose pieces
# (bones with a 'dangle' = (stiffness, damping) property, art/3d/build_dangles.py) swinging after it - a damped spring
# pulls each one's tail towards where its parent would hold it, so it lags, overshoots and settles. The game has no
# physics: an idle animation for it is made the same way and baked (the dangle bones get keyframes here too).
#   idle - what the leader screen plays: breathing, the weight shifting, the head looking round a little (144 frames,
#          looping: the springs run the loop twice and the second pass is keyed, so its end meets its start)
#   test - the same pieces pushed hard: torso turn, the left arm up, a big weight shift, a nod (100 frames)
import math
from mathutils import Quaternion, Vector

FPS = 24
SUBSTEPS = 4
MAX_SWING = math.radians(40)   # no loose piece swings further than this from where it hangs

# bone -> [(frame, (rx, ry, rz) degrees about the bone's own axes, (tx, ty, tz) metres in the bone's space)]
MOTIONS = {
    'idle': dict(frames=144, keys={
        'spine_02': [(1, (0, 0, 0)), (36, (1.5, 2.5, 0)), (72, (0, 0, 0)), (108, (1.5, -2.0, 0)), (144, (0, 0, 0))],
        'spine_03': [(1, (0, 0, 0)), (36, (2.0, 0, 0)), (72, (0, 0, 0)), (108, (2.0, 0, 0)), (144, (0, 0, 0))],
        'pelvis': [(1, (0, 0, 0), (0, 0, 0)), (60, (0, 2.0, 0), (0.02, 0, 0)), (84, (0, 2.0, 0), (0.02, 0, 0)),
                   (144, (0, 0, 0), (0, 0, 0))],
        'head': [(1, (0, 0, 0)), (40, (0, 0, 0)), (60, (2, 8, -2)), (90, (2, 8, -2)), (115, (0, 0, 0)), (144, (0, 0, 0))],
    }),
    'test': dict(frames=100, keys={
        'spine_02': [(1, (0, 0, 0)), (20, (0, 12, 0)), (40, (0, -8, 0)), (60, (0, 0, 0)), (100, (0, 0, 0))],
        'pelvis': [(1, (0, 0, 0), (0, 0, 0)), (55, (0, 0, 0), (0, 0, 0)), (70, (0, 5, 0), (0.05, 0, 0)),
                   (85, (0, -3, 0), (-0.03, 0, 0)), (100, (0, 0, 0), (0, 0, 0))],
        'upperarm_l': [(1, (0, 0, 0)), (25, (0, 0, 0)), (40, (0, 0, -35)), (55, (0, 0, 0)), (100, (0, 0, 0))],
        'head': [(1, (0, 0, 0)), (75, (0, 0, 0)), (85, (15, 0, 0)), (92, (-5, 0, 0)), (100, (0, 0, 0))],
    }),
}


def _key(pb, frame, rot, loc=(0, 0, 0)):
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = Matrix.LocRotScale(None, None, None).to_quaternion() if False else \
        (Quaternion((1, 0, 0), math.radians(rot[0])) @ Quaternion((0, 1, 0), math.radians(rot[1]))
         @ Quaternion((0, 0, 1), math.radians(rot[2])))
    pb.location = loc
    pb.keyframe_insert('rotation_quaternion', frame=frame)
    pb.keyframe_insert('location', frame=frame)


def apply(sc, rig, name):
    """Keys the motion on rig and simulates its dangle bones over it; returns the last frame."""
    m = MOTIONS[name]
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    rig.animation_data_clear()
    for bone, keys in m['keys'].items():
        pb = rig.pose.bones.get(bone)
        if pb is None:
            continue
        for k in keys:
            _key(pb, k[0], k[1], k[2] if len(k) > 2 else (0, 0, 0))
    sc.frame_start, sc.frame_end = 1, m['frames']
    dangles = [pb for pb in rig.pose.bones if 'dangle' in pb]
    # parents first: a chain's lower bone hangs from the simulated upper one
    dangles.sort(key=lambda pb: len(pb.parent_recursive))
    state, swing = {}, {}
    dt = 1.0 / FPS / SUBSTEPS
    mw = rig.matrix_world
    n = m['frames']
    for step in range(1, 2 * n + 1):  # the first pass only winds the springs up (the motion loops)
        f = (step - 1) % n + 1
        sc.frame_set(f)
        for pb in dangles:  # after the frame's keys: the simulation sets them
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = (1, 0, 0, 0)
        for pb in dangles:
            k, c = pb['dangle']
            bpy_update(sc)
            head, rest_tail = mw @ pb.head, mw @ pb.tail
            L = (rest_tail - head).length
            p, v = state.get(pb.name, (rest_tail.copy(), Vector()))
            for _ in range(SUBSTEPS):
                a = (rest_tail - p) * k - v * c
                v = v + a * dt
                p = p + v * dt
                d = p - head  # the bone keeps its length
                p = head + d.normalized() * L
            d0, d1 = (rest_tail - head).normalized(), (p - head).normalized()
            ang = d0.angle(d1, 0.0)
            if ang > MAX_SWING:
                d1 = d0.slerp(d1, MAX_SWING / ang)
                p = head + d1 * L
            state[pb.name] = (p, v)
            if step <= n:
                continue
            swing[pb.name] = max(swing.get(pb.name, 0.0), math.degrees(d0.angle(d1, 0.0)))
            q = d0.rotation_difference(d1)
            # world rotation about the head -> the bone's own (basis) rotation
            bm = mw @ pb.matrix
            rot = bm.to_quaternion()
            pb.rotation_quaternion = rot.inverted() @ q @ rot
            pb.keyframe_insert('rotation_quaternion', frame=f)
    print('swing (max degrees): ' + ', '.join('%s %.1f' % kv for kv in sorted(swing.items())))
    return m['frames']


def bpy_update(sc):
    import bpy
    bpy.context.view_layer.update()
