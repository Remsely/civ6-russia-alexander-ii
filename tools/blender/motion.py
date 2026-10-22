# Motions to try the leader in (render_leader.py --motion): the body moved by keyframes, and the loose pieces
# (bones with a 'dangle' = (stiffness, damping) property, art/3d/build_dangles.py) swinging after it - a damped spring
# pulls each one's tail towards where its parent would hold it, turned a share back to hang under gravity (HANG), so
# it lags, overshoots and settles; it keeps off the limbs (LIMBS) and what it lies on (HIT). The hands stay where they
# rest unless the motion moves that arm (plant: two-bone IK; the left one holds the sabre's hilt and goes with it).
# The game has no physics: an idle animation for it is made the same way and baked (the dangle bones and the planted
# arms get keyframes here too).
#   idle - what the leader screen plays (IDLE_* below): he looks into the camera, breathes, blinks and shifts his weight
#          from one leg onto the other and back (384 frames, 16 s, looping: the springs run the loop twice and the
#          second pass is keyed, so its end meets its start; frame 1 is the stance itself)
#   test - the same pieces pushed hard: torso turn, the left arm up, a big weight shift, a nod (100 frames)
#   stress_* - the stress tests (tools/blender/stress.py): one joint or a few taken out to the ends of their range and
#          back (STRESS below); the frames to look at are in their 'check'
import math
from mathutils import Matrix, Quaternion, Vector

FPS = 24
SUBSTEPS = 4
MAX_SWING = math.radians(40)   # no loose piece swings further than this from where its parent holds it ...
MAX_SWING_OF = {'dangle_sabre': math.radians(70),  # ... but the sabre, pushed by a leg, the aiguillettes' loops,
                'dangle_loop': math.radians(12),   # buttoned at both ends on the chest, and the sword knot, hanging
                'dangle_knot': math.radians(15)}   # along the scabbard (swinging on its own as the sabre swung, it went
                                                   # through the scabbard)
# Gravity: each loose piece comes to rest this share of the way from where its parent holds it (turned with the body)
# back to its own hang - as far from straight down as in the rest pose. The tassels on their cords hang nearly
# straight down whatever the body does; the aiguillettes' loops are held at both ends; the bullion fringe is stiff wire
# sewn to the rim; the skirt is stiff wool sewn to the waist; the sabre is held in his fist (left to hang as far as
# 0.6 of the way, it swung in over his shins as he stepped aside) and its sword knot goes with it more than the
# belt's (hanging 0.8 of the way, the knee pushed the scabbard on through it).
HANG = {'dangle_sabre': 0.35, 'dangle_knot': 0.45, 'dangle_beltknot': 0.8, 'dangle_pencil': 0.7, 'dangle_loop': 0.15,
        'dangle_fringe': 0.25, 'dangle_skirt': 0.4}
# ... and what each one bumps into instead of going through it: the surface of the uniform's layers and other meshes
# (_colliders; what lies on the chest) and the limbs as capsules round their bones (LIMBS; a thigh or an arm swinging
# through a hanging piece - a surface's side is lost once the thigh has gone through the skirt in front of it): the
# points of it nearest them (_contacts) kept no nearer than CLEAR or than at rest, if nearer then
COLLIDER, LAYERS = 'Uniform', ('tunic', 'trousers')
HIT = {'dangle_pencil': ('tunic', 'Sash'), 'dangle_loop': ('tunic',), 'dangle_beltknot': ('tunic',),
       'dangle_knot': (('tunic',), ('Sabre', 1.0)), 'dangle_sabre': ('tunic',)}
# (several walls: a tuple of them; a number in one, the share of the bone from its head it is looked for from - the
# sword knot is wound round the hilt at its top, and the scabbard it hangs by (curved away from the sabre's straight
# bone, its capsule let the knot through it) is a wall to its lower part)
LIMBS = {'dangle_sabre': ('thigh_l', 'calf_l'), 'dangle_knot': ('thigh_l', 'calf_l', 'dangle_sabre'),
         'dangle_beltknot': ('thigh_l', 'thigh_r', 'calf_l', 'calf_r', 'dangle_sabre'),
         'dangle_skirt': ('thigh_l', 'thigh_r', 'dangle_sabre'),  # (the scabbard pushed by the knee into its hem)
         'dangle_fringe_l': ('upperarm_l',), 'dangle_fringe_r': ('upperarm_r',),
         'dangle_loop': ('upperarm_r',)}  # (the aiguillettes' loops hang by his right armpit)
LIMB_R = 0.85                  # a limb's capsule: this quantile of how far its cloth (and boot) lies off its bone
LIMB_FROM = (COLLIDER, 'Boot', 'Sabre')  # ... of these (not what lies on the cloth: an epaulette's 12 cm off the arm)
CLEAR = 0.004
HOLDS = {'dangle_sabre': 'l'}  # a loose piece a hand holds (planted): the hand follows it
SLACK = 0.0005                 # ... going in less than this is let be (a piece lying on the chest pushed off it at every
                               # hair of difference, and walked off it by 22 degrees)

# bone -> [(frame, (rx, ry, rz) degrees about the bone's own axes, (tx, ty, tz) metres in the bone's space)]
MOTIONS = {
    'test': dict(frames=100, keys={
        'spine_02': [(1, (0, 0, 0)), (20, (0, 12, 0)), (40, (0, -8, 0)), (60, (0, 0, 0)), (100, (0, 0, 0))],
        'pelvis': [(1, (0, 0, 0), (0, 0, 0)), (55, (0, 0, 0), (0, 0, 0)), (70, (0, 5, 0), (0.05, 0, 0)),
                   (85, (0, -3, 0), (-0.03, 0, 0)), (100, (0, 0, 0), (0, 0, 0))],
        'upperarm_l': [(1, (0, 0, 0)), (25, (0, 0, 0)), (40, (0, 0, -35)), (55, (0, 0, 0)), (100, (0, 0, 0))],
        'head': [(1, (0, 0, 0)), (75, (0, 0, 0)), (85, (15, 0, 0)), (92, (-5, 0, 0)), (100, (0, 0, 0))],
    }),
}

# ---------------------------------------------------------------- stress tests
# A pose: bone -> [(axis, degrees), ...] (turned in that order) or ([...], (dx, dy, dz) metres). Axes are the body's as
# it stands at rest, carried by the parent bone: 'x' to his left, 'y' backwards, 'z' up (right hand: +x bends the spine
# forward and swings a hanging limb back, +y leans the top to his left, +z turns the front to his left); 'own' about the
# bone's own length (a twist); 'hinge' about its joint with its parent, + bending it further (elbow, knee, wrist,
# fingers); 'eyes' about the line between the eyes (+ the lids and the jaw down, the face nodding); 'face' about the
# face's forward line (+ the top to his right). Degrees 'blink' = that lid's blink (sc['head']['BLINK_L' / 'BLINK_R']).
# The hands stay where they rest - the left on the sabre's hilt, the right on the belt at his back - unless the test
# moves that arm: an animator holds them there (two-bone IK to the pelvis, which carries the sabre and the belt).
SPINE = ('spine_01', 'spine_02', 'spine_03')
FINGERS = tuple('%s_%02d_' % (f, i) for f in ('index', 'middle', 'ring', 'pinky', 'thumb') for i in (1, 2, 3))


def _all(bones, *rot):
    return {b: list(rot) for b in bones}


def _arm(s, out, fwd, back):
    """Tests of one arm: out to the side, forward, back, across, twisted; the elbow, wrist, forearm and fingers with the
    arm held out in front first (the hands rest on the hilt and on the belt at the back: turned there, they would go
    into the body as any hand pressed to it would; the right one, behind his back, out to the side as well)."""
    o = 1 if s == 'r' else -1  # 'y' sign that takes this arm out to its side
    ua, la, hd = 'upperarm_' + s, 'lowerarm_' + s, 'hand_' + s

    def held(**more):
        p = {ua: [('x', -45), ('y', o * 25)], la: [('hinge', -40)]}  # the forearm out of its bend (it lies across him)
        p.update(more)
        return p
    fingers = [f + s for f in FINGERS]
    return {
        'arm_%s_side' % s: dict(poses=[{ua: [('y', o * out * 0.5)]}, {ua: [('y', o * out)]}]),
        'arm_%s_fwd' % s: dict(poses=[{ua: [('x', -fwd * 0.5)]}, {ua: [('x', -fwd)]}]),
        'arm_%s_back' % s: dict(poses=[{ua: [('x', back)]}]),
        'arm_%s_across' % s: dict(poses=[{ua: [('x', -40), ('z', o * 35)]}]),
        'arm_%s_twist' % s: dict(poses=[{ua: [('own', 35)]}, {ua: [('own', -35)]}]),
        'elbow_%s' % s: dict(poses=[held(**{la: [('hinge', 20)]}), held(**{la: [('hinge', -60)]})], rest_between=False),
        'wrist_%s' % s: dict(poses=[held(), held(**{hd: [('hinge', 40)]}), held(**{hd: [('hinge', -40)]}),
                                    held(**{hd: [('z', 25)]}), held(**{hd: [('z', -25)]}), held()], rest_between=False),
        'forearm_%s' % s: dict(poses=[held(), held(**{la: [('hinge', -40), ('own', 60)]}),
                                      held(**{la: [('hinge', -40), ('own', -60)]}), held()], rest_between=False),
        # (forward 12, the cloth at the front of the armpit folded over the aiguillettes' cords on his right: a man
        # standing in a tight tunic takes his shoulders no further forward than this)
        'shrug_%s' % s: dict(poses=[{'clavicle_' + s: [('y', -o * 12)]}, {'clavicle_' + s: [('z', o * 6)]},
                                    {'clavicle_' + s: [('z', -o * 10)]}]),
        'fingers_%s' % s: dict(poses=[held(), held(**_all(fingers, ('hinge', 35))), held(**_all(fingers, ('hinge', -15))),
                                      held()], rest_between=False),
    }


def _leg(s):
    o = 1 if s == 'r' else -1
    return {
        'leg_%s_fwd' % s: [{'thigh_' + s: [('x', -30)]}, {'thigh_' + s: [('x', -60)], 'calf_' + s: [('hinge', 60)]}],
        'leg_%s_back' % s: [{'thigh_' + s: [('x', 25)]}],
        'leg_%s_side' % s: [{'thigh_' + s: [('y', o * 25)]}],  # (in, it went through the other leg: legs do)
        'leg_%s_twist' % s: [{'thigh_' + s: [('own', 25)]}, {'thigh_' + s: [('own', -25)]}],
        'knee_%s' % s: [{'calf_' + s: [('hinge', 45)]}, {'calf_' + s: [('hinge', 90)]}],
        'ankle_%s' % s: [{'foot_' + s: [('hinge', 25)]}, {'foot_' + s: [('hinge', -25)]}, {'foot_' + s: [('own', 15)]}],
    }


STRESS = {
    'blink': dict(poses=[{'lid_upper_l': [('eyes', 'blink')], 'lid_upper_r': [('eyes', 'blink')]}], ramp=3, hold=2,
                  settle=6),
    'gaze': dict(poses=[_all(('eye_l', 'eye_r'), ('z', a), ('x', b)) for a, b in ((18, 0), (-18, 0), (0, -12), (0, 12))]),
    'jaw': dict(poses=[{'jaw': [('eyes', 3)]}, {'jaw': [('eyes', 6)]}], ramp=6, hold=4),  # talking
    'breath': dict(poses=[{'spine_02': [('x', -1.5)], 'spine_03': [('x', -2.5)], 'clavicle_l': [('y', -2.5)],
                           'clavicle_r': [('y', 2.5)]}], ramp=30, hold=6),
    'head_turn': dict(poses=[{'neck_01': [('z', a * 0.4)], 'head': [('z', a * 0.6)]} for a in (35, -35)]),
    # (down 25, the beard went into the high collar's front: a man in one bends his head no further than this)
    'head_nod': dict(poses=[{'neck_01': [('eyes', a * 0.4)], 'head': [('eyes', a * 0.6)]} for a in (15, -20)]),
    'head_tilt': dict(poses=[{'neck_01': [('face', a * 0.4)], 'head': [('face', a * 0.6)]} for a in (15, -15)]),
    'torso_twist': dict(poses=[_all(SPINE, ('z', a)) for a in (8, -8)]),
    'torso_bend': dict(poses=[_all(SPINE, ('x', 8)), _all(SPINE, ('x', -5))]),
    'torso_side': dict(poses=[_all(SPINE, ('y', a)) for a in (6, -6)]),
    'hips': dict(poses=[{'pelvis': ([('y', -a * 80)], (a, 0, 0))} for a in (0.05, -0.05)] +
                 [{'pelvis': ([('z', a)], (0, 0, 0))} for a in (10, -10)]),
    'squat': dict(poses=[{'pelvis': ([], (0, 0, -0.10)), 'thigh_l': [('x', -35)], 'thigh_r': [('x', -35)],
                          'calf_l': [('hinge', 60)], 'calf_r': [('hinge', 60)], 'foot_l': [('hinge', -25)],
                          'foot_r': [('hinge', -25)]}], ramp=16, hold=8),
    'gesture': dict(poses=[{'upperarm_l': [('x', -55), ('y', -15)], 'lowerarm_l': [('hinge', 30)],
                            'spine_02': [('z', -6)], 'spine_03': [('z', -6)], 'head': [('z', -15)],
                            'hand_l': [('hinge', -20)]}], ramp=14, hold=10),
    'jolt': dict(poses=[_all(SPINE, ('z', 7)), _all(SPINE, ('z', -7))], ramp=3, hold=0, settle=30),
    'walk': dict(poses=[{'thigh_l': [('x', -25)], 'thigh_r': [('x', 20)], 'calf_r': [('hinge', 30)],
                         'spine_02': [('z', 4)], 'upperarm_r': [('x', -15)]},
                        {'thigh_r': [('x', -25)], 'thigh_l': [('x', 20)], 'calf_l': [('hinge', 30)],
                         'spine_02': [('z', -4)], 'upperarm_r': [('x', 15)]}], ramp=10, hold=2, rest_between=False),
}
for _s, (_out, _fwd, _back) in (('l', (80, 85, 30)), ('r', (80, 85, 25))):
    STRESS.update(_arm(_s, _out, _fwd, _back))
    STRESS.update({k: dict(poses=v) for k, v in _leg(_s).items()})


def _timeline(t):
    """A stress test as keys: rest, then each pose eased in, held and eased back to rest (or straight on to the next
    with rest_between=False), the springs left to settle at the end. -> (frames, {bone: [(frame, pose)]}, checks): the
    frames to look at - each pose as it is reached and at the end of its hold, and some frames after it is left (the
    loose pieces still swinging) - and the frames each pose is reached at."""
    ramp, hold, settle = t.get('ramp', 12), t.get('hold', 8), t.get('settle', 18)
    poses = t['poses']
    bones = sorted({b for p in poses for b in p})
    rest = ([], (0, 0, 0))
    keys = {b: [(1, rest)] for b in bones}
    checks, arrive, f = [], [], 1
    for i, p in enumerate(poses):
        f += ramp
        for b in bones:
            v = p.get(b, rest)
            keys[b].append((f, v if isinstance(v, tuple) else (v, (0, 0, 0))))
        checks.append(f)
        arrive.append(f)
        if hold:
            f += hold
            for b in bones:
                keys[b].append((f, keys[b][-1][1]))
            checks.append(f)
        if t.get('rest_between', True) or i == len(poses) - 1:
            f += ramp
            for b in bones:
                keys[b].append((f, rest))
            checks.append(f + min(6, settle))
    f += settle
    checks.append(f)
    return f, keys, sorted(set(checks)), arrive


for _n, _t in STRESS.items():
    _f, _k, _c, _a = _timeline(_t)
    _plant = tuple(s for s in 'lr' if not any(b in _k for b in ('upperarm_' + s, 'lowerarm_' + s, 'hand_' + s)))
    MOTIONS['stress_' + _n] = dict(frames=_f, body=True, keys=_k, check=_c, arrive=_a, plant=_plant)
MOTIONS['test']['plant'] = ('r',)

# ---------------------------------------------------------------- the idle loop
# He stands as in the stance - his weight on his left leg, the right one set out to the side - and in the loop brings the
# right foot in a little (a small step), takes his weight over onto it, back onto the left, and sets the right foot out
# where it was. Body axes and degrees as in STRESS. The feet stand where they are put and the hands where they rest
# (two-bone IK); the head is held steady over the body's sway (LOOK_HOLD of it taken out, the neck turning
# LOOK_NECK of that), turned only by a slow drift of its own, and the eyes kept on the camera as in the stance (where
# it is in each eye then - build_pose.py turned the eyeballs, not their bones, onto it, his right one a little under
# it: pose.EYE_OFF), but for small shifts of their fixation. Every part comes back to nothing at the loop's end, so frame 1 is the stance.
IDLE_FRAMES = 384
IDLE_BREATH = (96, 0.4)                # frames per breath (4 s) and the share of it breathing in
# ... the chest up and the shoulders lifted, the lower back easing forward under it so the head stays where it is (all
# the spine bent back, it went 2 cm back with every breath)
IDLE_BREATH_POSE = {'spine_02': [('x', 0.6)], 'spine_03': [('x', -1.3)],
                    'clavicle_l': [('y', -1.3)], 'clavicle_r': [('y', 1.3)]}
# the steps aside: (foot, frames it moves over, where it goes - metres from where it stands at rest, body axes): the
# right foot out to his right, the left one after it (he stands as before, the whole of him moved over), then the left
# one back and the right one back (the right one alone brought in under him, the feet stood unnaturally close); each
# foot rises IDLE_STEP_LIFT (metres) mid-step, its heel with it (degrees about the ball of the foot)
IDLE_SIDESTEP = 0.05
IDLE_STEPS = (('r', (60, 78), (-IDLE_SIDESTEP, 0.0, 0.0)), ('l', (96, 114), (-IDLE_SIDESTEP, 0.0, 0.0)),
              ('l', (236, 254), (0.0, 0.0, 0.0)), ('r', (272, 290), (0.0, 0.0, 0.0)))
IDLE_STEP_LIFT = (0.012, 5.0)
# ... his weight kept off the moving foot: the pelvis a little more over the other one, the moving side let down (over
# IDLE_STEP_EASE frames before the step and after it); for the right foot, the left one mirrored
IDLE_STEP_POSE = {'pelvis': ([('y', -1.0)], (0.01, 0.0, 0.0))}
IDLE_STEP_EASE = 10
IDLE_SHIFT = ((70, 102), (246, 278))  # frames: the weight going over onto his right leg, and back onto his left (the
# other foot follows as it comes off it: with the weight over first and the other foot after it, the step stood still
# for 2 s between the feet)
# ... and on his right leg: the pelvis over the foot stepped out, its right side up (the left one, unloaded, drops and
# the left knee bends), turned a little to his right (the left hip comes forward); the spine leaning back the other way
# past upright, so the right shoulder is a little the lower (contrapposto), and turned back to the front. The pelvis
# settles as low as the straight leg needs to reach the floor (REACH)
IDLE_SHIFT_POSE = {'pelvis': ([('y', 4.0), ('z', -2.0)], (-0.04 - IDLE_SIDESTEP, 0.0, 0.0)),
                   'spine_01': [('y', -1.6), ('z', 0.7)], 'spine_02': [('y', -1.6), ('z', 0.7)],
                   'spine_03': [('y', -1.8), ('z', 0.6)]}
IDLE_SWAY = (0.002, 0.3)               # the pelvis swaying from side to side twice a loop: metres; the spine's turn, deg
IDLE_BLINKS = (46, 120, 206, 213, 300)  # frames a blink starts: the lids shut over BLINK_SHUT, stay BLINK_HOLD, open
BLINK_SHUT, BLINK_HOLD, BLINK_OPEN = 3, 1, 5  # over BLINK_OPEN (frames; ~0.4 s in all)
LOOK_HOLD, LOOK_NECK = 0.85, 0.4
# the head's own drift: (degrees, cycles per loop) of its turn to his left and its nod up
LOOK_DRIFT = {'turn': ((0.7, 1), (0.3, 3)), 'up': ((0.5, 2),)}
# the eyes' fixation: from each frame on, (degrees to his left, up) off the camera; moved over 2 frames (a saccade)
LOOK_FIX = ((1, (0, 0)), (70, (0.8, 0.2)), (150, (-0.4, -0.3)), (200, (0.5, 0)), (262, (-0.7, 0.2)), (350, (0, 0)))
LOOK_SACCADE = 2


def _ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)


def _idle_keys():
    """IDLE_* as body keys on every frame: {bone: [(frame, (rotations, shift))]}."""
    n = IDLE_FRAMES
    keys = {}
    for f in range(1, n + 1):
        t = (f - 1) / n
        T, inhale = IDLE_BREATH
        p = ((f - 1) % T) / T
        breath = _ease(p / inhale) if p < inhale else 1 - _ease((p - inhale) / (1 - inhale))
        (a0, a1), (b0, b1) = IDLE_SHIFT
        shift = _ease((f - a0) / (a1 - a0)) - _ease((f - b0) / (b1 - b0))
        e = IDLE_STEP_EASE
        unweight = sum((1 if side == 'r' else -1) * (_ease((f - s0 + e) / e) - _ease((f - s1) / e))
                       for side, (s0, s1), _ in IDLE_STEPS)
        sway = math.sin(2 * math.pi * 2 * t)
        blink = 0.0
        for s in IDLE_BLINKS:
            r = f - s
            if r < 0:
                continue
            if r <= BLINK_SHUT:
                blink = max(blink, (r / BLINK_SHUT) ** 2)
            elif r <= BLINK_SHUT + BLINK_HOLD:
                blink = max(blink, 1.0)
            elif r <= BLINK_SHUT + BLINK_HOLD + BLINK_OPEN:
                blink = max(blink, 1 - _ease((r - BLINK_SHUT - BLINK_HOLD) / BLINK_OPEN))
        pose = {}  # bone -> ({axis: degrees}, shift)

        def add(parts, share):
            for b, v in parts.items():
                rot, loc = v if isinstance(v, tuple) else (v, (0, 0, 0))
                r, l = pose.setdefault(b, ({}, [0.0, 0.0, 0.0]))
                for ax, deg in rot:
                    r[ax] = r.get(ax, 0.0) + deg * share
                for i in range(3):
                    l[i] += loc[i] * share
        add(IDLE_BREATH_POSE, breath)
        add(IDLE_SHIFT_POSE, shift)
        add(IDLE_STEP_POSE, unweight)
        add({'pelvis': ([], (IDLE_SWAY[0], 0, 0)), 'spine_02': [('z', IDLE_SWAY[1])]}, sway)
        for b, (r, l) in pose.items():
            keys.setdefault(b, []).append((f, ([(ax, r[ax]) for ax in 'xyz' if ax in r], tuple(l))))
        for s in 'lr':
            keys.setdefault('lid_upper_' + s, []).append((f, ([('eyes', ('blink', blink))], (0, 0, 0))))
    return keys


def _idle_look(f):
    """The head's drift and the eyes' fixation at frame f: ((turn, up), (left, up)) degrees."""
    t = (f - 1) / IDLE_FRAMES
    drift = tuple(sum(a * math.sin(2 * math.pi * c * t) for a, c in LOOK_DRIFT[k]) for k in ('turn', 'up'))
    fix = (0.0, 0.0)
    for i, (f0, v) in enumerate(LOOK_FIX):
        if f < f0:
            break
        prev = LOOK_FIX[i - 1][1] if i else v  # moving from the one before over LOOK_SACCADE frames
        k = _ease((f - f0 + 1) / LOOK_SACCADE)
        fix = tuple(p + (q - p) * k for p, q in zip(prev, v))
    return drift, fix


def _idle_feet(rig, f):
    """Where the feet stand at frame f (IDLE_STEPS): {side: armature-space move from where it stands at rest}."""
    out = {}
    bones = rig.data.bones
    for s in 'lr':
        at, up = Vector(), 0.0
        for side, (f0, f1), to in IDLE_STEPS:
            if side != s or f < f0:
                continue
            u = min(1.0, (f - f0) / (f1 - f0))
            at = at.lerp(Vector(to), _ease(u))
            up = math.sin(math.pi * u)  # off the floor mid-step
        if at.length < 1e-9 and up < 1e-9:
            continue
        ankle, ball = bones['foot_' + s].head_local, bones['ball_' + s].head_local
        fwd = Vector((ball.x - ankle.x, ball.y - ankle.y, 0)).normalized()
        heel = Quaternion(Vector((0, 0, 1)).cross(fwd), math.radians(IDLE_STEP_LIFT[1] * up))  # toe down about the ball
        out[s] = (Matrix.Translation(at + Vector((0, 0, IDLE_STEP_LIFT[0] * up)))
                  @ Matrix.Translation(ball) @ heel.to_matrix().to_4x4() @ Matrix.Translation(-ball))
    return out


MOTIONS['idle'] = dict(frames=IDLE_FRAMES, body=True, keys=_idle_keys(), plant=('l', 'r'), feet=('l', 'r'), look=True,
                       step=_idle_feet, check=[1, 39, 49, 69, 78, 90, 100, 105, 114, 160, 209, 240, 245, 250, 262,
                                               276, 281, 290, 350, 384], arrive=[78, 102, 114, 254, 278, 290])


def _axis(rig, sc, pb, name):
    """An axis of STRESS in armature space (rest)."""
    b = pb.bone
    if name in ('x', 'y', 'z'):
        return Vector([float(name == c) for c in 'xyz'])
    if name == 'own':
        return (b.tail_local - b.head_local).normalized()
    if name == 'hinge':
        p = b.parent
        n = (p.tail_local - p.head_local).cross(b.tail_local - b.head_local)
        if n.length < 1e-6:  # straight: about the parent's own sideways axis
            n = p.matrix_local.to_3x3() @ Vector((1, 0, 0))
        return n.normalized()
    bones = rig.data.bones
    eyes = (bones['eye_l'].head_local - bones['eye_r'].head_local).normalized()
    if name == 'eyes':
        return eyes
    if name == 'face':
        return eyes.cross(Vector((0, 0, 1))).normalized()  # forward, square to the eyes' line
    raise ValueError(name)


def _body_key(rig, sc, pb, frame, rot, loc):
    """A stress pose's turn about body axes (carried by the parent) and shift (metres, body axes) keyed as the bone's
    own: rest rotation Qr, basis = Qr^-1 R Qr."""
    q_rest = pb.bone.matrix_local.to_quaternion()
    r = Quaternion()
    for name, deg in rot:
        if deg == 'blink' or isinstance(deg, tuple):  # each lid its own way down (the stance let them down unlike);
            hd = sc['head']                              # ('blink', share): that share of the way
            share = deg[1] if isinstance(deg, tuple) else 1.0
            deg = float(hd.get('BLINK_' + pb.name[-1].upper(), hd['BLINK_DEG'])) * share
        r = Quaternion(_axis(rig, sc, pb, name), math.radians(deg)) @ r
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = q_rest.inverted() @ r @ q_rest
    pb.location = q_rest.inverted() @ Vector(loc)
    pb.keyframe_insert('rotation_quaternion', frame=frame)
    pb.keyframe_insert('location', frame=frame)


def _key(pb, frame, rot, loc=(0, 0, 0)):
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = (Quaternion((1, 0, 0), math.radians(rot[0])) @ Quaternion((0, 1, 0), math.radians(rot[1]))
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
            if m.get('body'):
                _body_key(rig, sc, pb, k[0], *k[1])
            else:
                _key(pb, k[0], k[1], k[2] if len(k) > 2 else (0, 0, 0))
    sc.frame_start, sc.frame_end = 1, m['frames']
    dangles = [pb for pb in rig.pose.bones if 'dangle' in pb]
    # parents first: a chain's lower bone hangs from the simulated upper one; the sabre and the skirt before what
    # bumps into them or hangs over them
    first = ('dangle_sabre', 'dangle_skirt')
    dangles.sort(key=lambda pb: (len(pb.parent_recursive), next((i for i, f in enumerate(first)
                                                                   if pb.name.startswith(f)), len(first))))
    state, swing = {}, {}
    dt = 1.0 / FPS / SUBSTEPS
    mw = rig.matrix_world
    n = m['frames']
    # the meshes are not needed while the springs run (only the bones and what the loose pieces bump into): the other
    # meshes' skinning left off till the end
    hits = {o for v in HIT.values() for g in _groups(v) for o in g if isinstance(o, str) and o not in LAYERS}
    skins = [md for o in sc.objects if o.type == 'MESH' and o.name != COLLIDER and o.name not in hits
             for md in o.modifiers if md.type == 'ARMATURE' and md.show_viewport]
    for md in skins:
        md.show_viewport = False
    rest = {}  # per loose piece: its hang (world, rest pose) and the points of it that keep off what it hangs over
    sc.frame_set(0)  # before the first key: the rest pose
    for pb in dangles:
        pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0)
    bpy_update(sc)
    trees = _colliders(sc)
    caps = _limb_radii(sc, rig, {b for v in LIMBS.values() for b in v})
    for pb in dangles:
        h, t = mw @ pb.bone.head_local, mw @ pb.bone.tail_local
        limbs = [(b, caps[b]) for b in (_kind(pb.name, LIMBS) or ())]
        walls = [_wall(sc, rig, pb, trees.get(g), h, t, g) for g in _groups(_kind(pb.name, HIT) or ())]
        rest[pb.name] = ((t - h).normalized(), limbs, _contacts(sc, rig, pb, h, t, limbs), [w for w in walls if w])
    look = _camera_in_eyes(sc, rig) if m.get('look') else None
    plant, feet = m.get('plant', ()), m.get('feet', ())
    keyed = [b + s for s in plant for b in ARM] + [b + s for s in feet for b in LEG] + (list(LOOKS) if look else [])
    reach, settled = {}, 0.0
    for step in range(1, 2 * n + 1):  # the first pass only winds the springs up (the motion loops)
        f = (step - 1) % n + 1
        sc.frame_set(f)
        for pb in dangles:  # after the frame's keys: the simulation sets them
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = (1, 0, 0, 0)
        steps = m['step'](rig, f) if 'step' in m else {}
        if feet:
            drop = _settle(rig, feet, steps)
            settled = max(settled, drop)
            if step > n:
                rig.pose.bones['pelvis'].keyframe_insert('location', frame=f)
        for s in plant:
            _plant(rig, s, 'pelvis')
        for s in feet:  # the feet where they stand (or are put)
            reach[s] = max(reach.get(s, 0.0), _plant(rig, s, 'Root', LEG, steps.get(s)))
        if look:
            _look(rig, look, *_idle_look(f))
        bpy_update(sc)
        for pb in dangles:
            k, c = pb['dangle'][:2]
            bpy_update(sc)
            head, held_tail = mw @ pb.head, mw @ pb.tail
            L = (held_tail - head).length
            held = (held_tail - head).normalized()
            hang, limbs, contacts, walls = rest[pb.name]
            # where it would come to rest: as its parent holds it, turned a share back to its own hang under gravity
            # (as far from straight down as in the rest pose, on the side its parent holds it to)
            target = head + held.slerp(_hang(held, hang), _kind(pb.name, HANG)) * L
            # its contact points and the wall it lies on as the parent holds them (the parent's move since rest)
            par = pb.parent
            pm = mw @ par.matrix @ par.bone.matrix_local.inverted() @ mw.inverted()
            held_pts = [(pm @ co, w, d0) for co, w, d0 in contacts]
            planes = []
            for wb, w0, n0, c0, wu in walls:  # the surfaces under it, as the bones carrying them have moved them
                wm = Matrix(((0,) * 4,) * 4)
                for b, w in wb:  # as the surface there is skinned
                    wbp = rig.pose.bones[b]
                    wm += (mw @ wbp.matrix @ wbp.bone.matrix_local.inverted() @ mw.inverted()) * w
                planes.append((wm @ w0, (wm.to_3x3() @ n0).normalized(), c0, wu))
            segs = [(mw @ rig.pose.bones[b].head, mw @ rig.pose.bones[b].tail, r) for b, r in limbs]
            p, v = state.get(pb.name, (held_tail.copy(), Vector()))
            for _ in range(SUBSTEPS):
                a = (target - p) * k - v * c
                v = v + a * dt
                p = p + v * dt
                d = p - head  # the bone keeps its length
                p = head + d.normalized() * L
                for wp, wn, wc, wu in planes:  # not into what it lies on: no nearer that surface than at rest (or CLEAR)
                    into = (head + (p - head) * wu - wp).dot(wn) - wc
                    if into < 0:
                        p = head + (p - wn * (into / wu) - head).normalized() * L
                        v = v - wn * min(0.0, v.dot(wn))
                # no point of it further into a limb than at rest (or than CLEAR off it)
                for hp, w, d0 in held_pts:
                    q = held.rotation_difference((p - head).normalized())
                    x = hp + ((q @ (hp - head)) + head - hp) * w
                    pushes = []
                    for (a_, b_, r), dr in zip(segs, d0):
                        cp = _closest(a_, b_, x)
                        off = x - cp
                        if off.length > 1e-6:
                            pushes.append((min(dr, r + CLEAR) - off.length, off.normalized()))
                    for depth, nrm in pushes:
                        depth -= SLACK
                        if depth > 0:
                            lever = max(w * (hp - head).length / L, 0.15)
                            p = head + (p + nrm * (depth / lever) - head).normalized() * L
                            v = v - nrm * min(0.0, v.dot(nrm))
            d0, d1 = held, (p - head).normalized()
            ang = d0.angle(d1, 0.0)
            most = _kind(pb.name, MAX_SWING_OF) or MAX_SWING
            if ang > most:
                d1 = d0.slerp(d1, most / ang)
                p = head + d1 * L
            state[pb.name] = (p, v)
            q = d0.rotation_difference(d1)
            # world rotation about the head -> the bone's own (basis) rotation (set in both passes: a loose piece
            # hanging from another one follows it)
            bm = mw @ pb.matrix
            rot = bm.to_quaternion()
            pb.rotation_quaternion = rot.inverted() @ q @ rot
            if pb.name in HOLDS and HOLDS[pb.name] in plant:  # the hand on it goes where it goes
                bpy_update(sc)
                _plant(rig, HOLDS[pb.name], pb.name)
            if step <= n:
                continue
            swing[pb.name] = max(swing.get(pb.name, 0.0), math.degrees(d0.angle(d1, 0.0)))
            pb.keyframe_insert('rotation_quaternion', frame=f)
        if step > n:
            for b in keyed:
                rig.pose.bones[b].keyframe_insert('rotation_quaternion', frame=f)
    for md in skins:
        md.show_viewport = True
    print('swing (max degrees): ' + ', '.join('%s %.1f' % kv for kv in sorted(swing.items())))
    if reach:
        print('legs reach (most, of their length): ' + ', '.join('%s %.4f' % kv for kv in sorted(reach.items()))
              + '; the pelvis let down %.1f mm at most for it' % (settled * 1000))
    return m['frames']


ARM, LEG = ('upperarm_', 'lowerarm_', 'hand_'), ('thigh_', 'calf_', 'foot_')
LOOKS = ('neck_01', 'head', 'eye_l', 'eye_r')
REACH = 0.997  # a planted leg reaches out at most this share of its length (straight, it would snap)


def _settle(rig, feet, steps):
    """The pelvis let down as far as the legs need to reach the floor where the feet stand (steps: their moves from
    rest) at REACH of their length; returns how far (metres)."""
    pbs, bones = rig.pose.bones, rig.data.bones
    drop = 0.0
    for s in feet:
        W = (steps.get(s) or Matrix()) @ bones['foot_' + s].head_local
        S = pbs['thigh_' + s].head
        L = (bones['thigh_' + s].length + bones['calf_' + s].length) * REACH
        h = Vector((S.x - W.x, S.y - W.y)).length
        if h < L:
            drop = max(drop, S.z - (W.z + math.sqrt(L * L - h * h)))
    if drop > 0:
        pv = pbs['pelvis']
        pv.matrix = Matrix.Translation((0, 0, -drop)) @ pv.matrix
        bpy_update(None)
    return drop


def camera(sc, rig, yaw=None):
    """Where the leader camera is, in rig's armature space (as render_leader.py places it: the model, as it stands at
    rest, turned into leader space by 90 + yaw degrees - the pose's YAW_DEG - and scaled TARGET_CM tall)."""
    pts = [o.matrix_world @ v.co for o in sc.objects if o.type == 'MESH' and not o.hide_render for v in o.data.vertices]
    z0, z1 = min(p.z for p in pts), max(p.z for p in pts)
    yaw = float(sc.get('pose', {}).get('YAW_DEG', 0.0)) if yaw is None else yaw
    leader = Matrix.Rotation(math.radians(90 + yaw), 4, 'Z') @ Matrix.Scale(TARGET_CM / (z1 - z0), 4)
    return rig.matrix_world.inverted() @ leader.inverted() @ CAMERA


def _camera_in_eyes(sc, rig):
    """The leader camera (camera) and where it is seen from each eye at rest (in the eye bone's own axes)."""
    cam = camera(sc, rig)
    seen = {}
    for s in 'lr':
        b = rig.data.bones['eye_' + s]
        seen[s] = (b.matrix_local.to_3x3().inverted() @ (cam - b.head_local)).normalized()
    return cam, seen


CAMERA, TARGET_CM = Vector((320.0, 0.0, 137.741)), 150.0  # leader space, cm (render_leader.py)


def _turn(pb, q):
    """pb turned by q (armature space) about its head."""
    h = pb.head.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
    bpy_update(None)


def _look(rig, look, drift, fix):
    """The head held steady (LOOK_HOLD of its move since rest taken out, the neck turning LOOK_NECK of that) and turned
    by drift (degrees to his left, up); the eyes on the camera as at rest, off it by fix (degrees to his left, up)."""
    cam, seen = look
    pbs = rig.pose.bones
    for b in LOOKS:
        pbs[b].rotation_mode = 'QUATERNION'
        pbs[b].matrix_basis.identity()
    bpy_update(None)
    neck, head = pbs['neck_01'], pbs['head']
    up = Vector((0, 0, 1))
    left = (rig.data.bones['eye_l'].head_local - rig.data.bones['eye_r'].head_local).normalized()
    q_now = head.matrix.to_quaternion()
    q_want = (Quaternion(up, math.radians(drift[0])) @ Quaternion(left, -math.radians(drift[1]))
              @ head.bone.matrix_local.to_quaternion())
    q_want = q_now.slerp(q_want, LOOK_HOLD)
    _turn(neck, Quaternion().slerp(q_want @ q_now.inverted(), LOOK_NECK))
    _turn(head, q_want @ head.matrix.to_quaternion().inverted())
    left = (pbs['eye_l'].head - pbs['eye_r'].head).normalized()
    for s in 'lr':
        e = pbs['eye_' + s]
        want = (Quaternion(up, math.radians(fix[0])) @ Quaternion(left, -math.radians(fix[1]))) @ (cam - e.head)
        _turn(e, (e.matrix.to_3x3() @ seen[s]).rotation_difference(want.normalized()))


def _plant(rig, s, holder, limb=ARM, put=None):
    """His hand on side s held where it rests on what holder carries (the pelvis: the belt at the back; the sabre's own
    bone: its hilt in his fist): the upper arm and forearm turned by two-bone IK, the elbow on the side it is at rest,
    the hand turned with the holder. With limb=LEG the same for a leg: the foot where it stands on what holder carries
    (Root: the floor), or moved from there by put (armature space), the knee on the side it is at rest. Returns how far
    the limb is reached out, of its length."""
    pbs = rig.pose.bones
    ua, la, hd = (pbs[b + s] for b in limb)
    pv = pbs[holder]
    for pb in (ua, la, hd):
        pb.rotation_mode = 'QUATERNION'
        pb.matrix_basis.identity()
    bpy_update(None)
    move = pv.matrix @ pv.bone.matrix_local.inverted()  # the holder from rest to now (armature space)
    if put is not None:
        move = put @ move
    S = ua.head.copy()
    W = move @ hd.bone.head_local
    P = move @ la.bone.head_local  # the elbow's side
    a, b = ua.bone.length, la.bone.length
    x = W - S
    out = x.length / (a + b)
    d = min(x.length, (a + b) * 0.9999)
    x.normalize()
    y = (P - S) - x * (P - S).dot(x)
    y = y.normalized() if y.length > 1e-6 else Vector((0, 1, 0))
    u = (a * a - b * b + d * d) / (2 * d)
    E = S + x * u + y * math.sqrt(max(a * a - u * u, 0.0))
    for pb, to in ((ua, E), (la, S + x * d)):
        cur = (pb.tail - pb.head).normalized()
        q = cur.rotation_difference((to - pb.head).normalized())
        m = pb.matrix.copy()
        pb.matrix = Matrix.Translation(pb.head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-pb.head) @ m
        bpy_update(None)
    t = hd.matrix.translation.copy()
    hm = move @ hd.bone.matrix_local
    hm.translation = t
    hd.matrix = hm
    bpy_update(None)
    return out


def _kind(name, table):
    return next((v for k, v in table.items() if name.startswith(k)), None)


def _hang(held, hang):
    """held turned to hang as far from straight down as hang does, on held's side (about the vertical)."""
    down = Vector((0, 0, -1))
    side = held - down * held.dot(down)
    if side.length < 1e-4:
        side = hang - down * hang.dot(down)
    if side.length < 1e-4:
        return hang.copy()
    a = hang.angle(down, 0.0)
    return (down * math.cos(a) + side.normalized() * math.sin(a)).normalized()


def _colliders(sc):
    """What the loose pieces bump into, as it is at this frame: per HIT entry, one tree of the uniform's layers
    (tunic, trousers) and the objects named in it."""
    import bpy
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    parts = {}
    uni = sc.objects.get(COLLIDER)
    if uni:
        ev = uni.evaluated_get(dg)
        me = ev.to_mesh()
        co = [ev.matrix_world @ v.co for v in me.vertices]
        part = me.attributes.get('part')
        pv = [d.value for d in part.data] if part else [0] * len(me.polygons)
        for name in LAYERS:  # the outside only: the lining's faces (material 1) face in, and a point by both sides
            # of the cloth took its side from whichever was nearer
            parts[name] = (co, [tuple(p.vertices) for p, pt in zip(me.polygons, pv)
                                if (pt == 0) == (name == 'tunic') and p.material_index == 0])
        ev.to_mesh_clear()
    out = {}
    for key in {g for v in HIT.values() for g in _groups(v)}:
        co, polys, spans = [], [], []
        for name in key:
            if not isinstance(name, str):
                continue
            if name not in parts:
                ob = sc.objects.get(name)
                if ob is None:
                    continue
                ev = ob.evaluated_get(dg)
                me = ev.to_mesh()
                parts[name] = ([ev.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
                ev.to_mesh_clear()
            c, ps = parts[name]
            base = len(co)
            co += c
            spans.append((name, len(polys), len(polys) + len(ps)))
            polys += [tuple(i + base for i in p) for p in ps]
        if polys:
            out[key] = (BVHTree.FromPolygons(co, polys), spans)
    return out


def _groups(hit):
    """A HIT entry as a list of walls (each a tuple of names, maybe with a number)."""
    return list(hit) if hit and isinstance(hit[0], tuple) else ([tuple(hit)] if hit else [])


def _closest(a, b, x):
    """The point of segment a-b nearest x."""
    ab = b - a
    t = max(0.0, min(1.0, (x - a).dot(ab) / max(ab.dot(ab), 1e-12)))
    return a + ab * t


def _limb_radii(sc, rig, bones):
    """Each limb's capsule radius: how far what it carries most of (cloth, boots; the sabre) lies off its bone (LIMB_R
    quantile)."""
    out = {}
    mw = rig.matrix_world
    for b in bones:
        bone = rig.data.bones[b]
        a, t = mw @ bone.head_local, mw @ bone.tail_local
        ds = []
        for o in sc.objects:
            g = o.vertex_groups.get(b) if o.type == 'MESH' and o.name.startswith(LIMB_FROM) else None
            if g is None:
                continue
            for v in o.data.vertices:
                if next((e.weight for e in v.groups if e.group == g.index), 0.0) > 0.6:
                    x = o.matrix_world @ v.co
                    ds.append((x - _closest(a, t, x)).length)
        ds.sort()
        out[b] = ds[int(len(ds) * LIMB_R)] if ds else 0.05
    print('limbs: ' + ', '.join('%s %.3f' % kv for kv in sorted(out.items())))
    return out


def _contacts(sc, rig, pb, head, tail, limbs, bins=8, per_bin=3):
    """Points of what pb carries that keep off the limbs: its vertices it carries most of, a few from each stretch of
    its length nearest them - (rest position, pb's weight there, distances off the limbs' bones at rest)."""
    if not limbs:
        return []
    mw = rig.matrix_world
    segs = [(mw @ rig.data.bones[b].head_local, mw @ rig.data.bones[b].tail_local, r) for b, r in limbs]
    L = (tail - head).length
    ax = (tail - head) / L
    pts = []
    for o, g in _carried(sc, pb):
        for v in o.data.vertices:
            w = next((e.weight for e in v.groups if e.group == g.index), 0.0)
            if w > 0.3:
                co = o.matrix_world @ v.co
                d0 = [(co - _closest(a, b, co)).length for a, b, r in segs]
                score = min(d - r for d, (a, b, r) in zip(d0, segs))
                pts.append((min(0.999, max(0.0, (co - head).dot(ax) / L)), score, co, w, d0))
    out = []
    for b in range(bins):
        sel = sorted((p for p in pts if int(p[0] * bins) == b), key=lambda p: p[1])[:per_bin]
        out += [(co, w, d0) for _, _, co, w, d0 in sel]
    return out


def _carried(sc, pb):
    return [(o, o.vertex_groups[pb.name]) for o in sc.objects if o.type == 'MESH' and pb.name in o.vertex_groups]


def _wall(sc, rig, pb, found, head, tail, group=()):
    """What pb lies on (found: the tree of a HIT group's surfaces at rest and which object each span of its faces is),
    at the point of the bone nearest it (from the group's number, if any, of its length on): (the bones that carry the
    surface there with their weights, the nearest point of it, its outward normal, the bone point's distance off it,
    that point's share of the bone's length from its head) - or None."""
    if found is None:
        return None
    tree, spans = found
    u0 = next((g for g in group if not isinstance(g, str)), 0.2)
    best = None
    for u in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        if u < u0 - 1e-6:
            continue
        x = head + (tail - head) * u
        hit = tree.find_nearest(x, 0.1)
        if hit[0] is not None and (best is None or (x - hit[0]).length < best[0]):
            best = ((x - hit[0]).length, u, x, hit)
    if best is None:
        return None
    _, u, x, hit = best
    name = next((n for n, a, b in spans if a <= hit[2] < b), COLLIDER)
    ob = sc.objects.get(COLLIDER if name in LAYERS else name)
    bones = [(pb.parent.name, 1.0)]
    if ob:  # the bones that carry the surface nearest that point (the skirt over a thigh goes partly with it)
        names = [g.name for g in ob.vertex_groups]
        v = min(ob.data.vertices, key=lambda v: (ob.matrix_world @ v.co - hit[0]).length_squared)
        gs = [(names[g.group], g.weight) for g in v.groups if names[g.group] in rig.pose.bones and g.weight > 0]
        tot = sum(w for _, w in gs)
        bones = [(b, w / tot) for b, w in gs] if tot else bones
    # off the cloth it may come in to CLEAR; off anything else no nearer than at rest (a tassel's bone runs down its
    # middle: let in to CLEAR, half of it was in the scabbard)
    c0 = (x - hit[0]).dot(hit[1])
    return bones, hit[0], hit[1], (min(c0, CLEAR) if name in LAYERS else c0), u


def _sdist(tree, p, normal=False):
    """Signed distance of p off the surface in tree (+ on its outer side), and its normal there."""
    hit = tree.find_nearest(p, 0.08)
    if hit[0] is None:
        return (None, None) if normal else None
    sd = (p - hit[0]).dot(hit[1])
    return (sd, hit[1]) if normal else sd


def bpy_update(sc):
    import bpy
    bpy.context.view_layer.update()
