# Regalia over the posed uniform of alexander_leader.blend (after build_pose.py), as in art/source/alexander_ii_short.png: general's epaulettes
# with bullion fringe, the light-blue sash of St Andrew over the right shoulder to the left hip, gold aiguillettes on
# the right breast. blender -b art/3d/alexander_leader.blend --python art/3d/build_regalia.py   (after build_pose.py)
# Rewrites the file in place; safe to re-run (removes what it made before).
# One material 'Regalia' with its own atlas (albedo + metal/roughness, textures/regalia_*.png), every part skinned to
# the skeleton: rigid parts take the cloth's weights at one point, the sash and cords the cloth's under each vertex.
# MPFB space: metres, Z up, faces -Y; his right = -X.
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_util  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'alexander_leader.blend')  # on the posed uniform (build_pose.py), in place
TEXDIR = os.path.join(HERE, 'textures')
TEX = 2048
ALBEDO_OUT = os.path.join(TEXDIR, 'regalia_albedo.png')
MR_OUT = os.path.join(TEXDIR, 'regalia_mr.png')  # R metal, G roughness
NORMAL_OUT = os.path.join(TEXDIR, 'regalia_normal.png')  # tangent space, OpenGL (Y up)

GOLD_SRGB = mat_util.GOLD_SRGB
SASH_SRGB = (57, 109, 179)       # the St Andrew blue moire of the portrait (between its lit and shaded side)
# The portrait as a view of the model: tools/blender/render_leader.py's 'ref' (orthographic, the figure turned the
# pose's YAW_DEG towards his left, the crown and the soles on these rows of alexander_ii_full.png). The cords, the
# pencil and the epaulettes' reach are read off the portrait in pixels and cast onto the model along the line of sight.
REF_W, REF_CROWN, REF_SOLES, REF_X = 1024, 12, 1510, 515
# Epaulettes: a rigid oval field (a gilt plate, slightly curved over the shoulder - it does not follow the cloth's
# folds) lying on top of the shoulder, centred on it front to back, its outer end a little past the shoulder's end; a
# thick twisted rim; a strap to the collar with a button; bullion fringe hanging from under the rim round its outer
# three quarters, fanning out over the arm (as in the portrait).
EP_R = 0.062                     # the field's radius: a round plate, as a general's epaulette (the portrait's field
                                 # ~14.5 cm across with its rim in the 'ref' view, ~22 cm with the fringe belling out)
EP_REF_X = {'r': 360, 'l': 668}  # the fields' middles where the portrait has them (px across alexander_ii_full.png, as
                                 # the 'ref' view frames the figure): on the shoulder's line front to back, out to there
EP_GAP, EP_DOME, EP_THICK = 0.003, 0.012, 0.006  # the field's underside off the cloth at the nearest, its dome, edge
                                 # (the underside flat: bent over the shoulder, the oval sagged at its front and back)
EP_TILT = {'r': 15.0, 'l': 18.0}  # degrees the field's outer end is lower: in the portrait both fields face the viewer -
                                 # the camera stands to his right, so his left one is tilted out less (as much, it
                                 # showed its edge); the inner end rises over the slope to the collar (tilted 18 deg,
                                 # it rested there and stood 4-5 cm over the shoulder). Not tilted forward: level front
                                 # to back, as it sits on the shoulder (tilted 20-26 deg, it slid down onto the chest)
EP_TO_VIEWER = 8.0               # ... and tilted this much towards the viewer (the camera): the portrait shows both
                                 # fields' faces; level, from chest height they showed their edges (20-26 deg towards
                                 # the front, the field slid down onto the chest)
EP_TURN = {'r': 0.0, 'l': 22.0}   # degrees the field is turned about the upright towards the front: in the portrait his
                                 # left one shows its face nearly square to the viewer as the right one does (the
                                 # shoulder turned away from the camera with the figure, it showed its edge)
EP_PAD = {'r': 0.018, 'l': 0.004}  # the field stands on its padding this far over where it would rest on the shoulder
                                 # (resting on it, his right one looked pressed into the shoulder: the portrait's top
                                 # is ~1 cm higher; with the trapezius falling from the neck in its hollow curve, both
                                 # sank 0.4-1 cm under the portrait's outline)
EP_RIM_R = 0.008                 # the rim's radius: a thick padded roll of bullion, as in the portrait
EP_PRESS = (0.004, 0.008)       # the rim pressed this far into the padded shoulder, its outer and inner (towards the
                                 # neck) half (resting on it on square shoulders, the field stood 5 cm over the
                                 # portrait's; on the sloped ones 2 cm pressed it into the shoulder)
STRAP_X, STRAP_W = 0.085, 0.038   # strap from the field to this |x|, by the collar: the epaulette's own broad shoulder
                                 # strap, gold galloon edged in red, as in the portrait
STRAP_SHORT = 0.006               # ... ending this far short of the collar's foot
STRAP_T, STRAP_GAP = 0.006, 0.002  # its thickness (a stiff padded galloon, not a ribbon); off the cloth
STRAP_REPEATS = 3                # the galloon picture along the strap
STRAP_END = 0.6                  # its end by the collar rounded: a half-round of this share of its width's half ... (a
                                 # square-cut board, it read as a stick)
STRAP_PIPING = 0.0026            # ... red piping round its sides and end, a cord of this radius, as the portrait's
STRAP_WRAPS, STRAP_WRAP_R = 3, 0.003  # ... and bound where it comes out from under the rim: turns of gold cord round it
STRAP_BUTTON = 0.0065            # the button's radius by its rounded end
SASH_HELD = (0.145, 0.16, 1.70, 0.0035)  # on his right shoulder from the collar out to this |x| (fading out by the
                                 # second, over this height) the band lies on the shoulder's own cloth this far off it,
                                 # held down by the strap: on the tightened cloth it stood 1.7 cm over the shoulder by
                                 # the collar, the strap on it standing up at its end (its thickness goes in from
                                 # there: at 2 mm it lay on the tunic)
FRINGE_ARC = 290.0               # the fringe hangs round this arc of the rim, centred on the outer end: none on the
                                 # quarter by the collar, where the strap is (round 316 deg the strands there were buried
                                 # in the collar and the sash, stuck out level like sticks and drew their neighbours out)
FRINGE_LEN, FRINGE_R = 0.09, 0.009  # a strand's length and radius: the portrait's are ~8.5 cm long, ~1.5 cm thick,
                                 # side by side, touching under the rim
FRINGE_DEEP = 0.04                # a strand whose root is this far inside the cloth is left out (at 1.2 cm the front of
                                 # the bell, over the chest, was missing: the cords came out of nowhere beside it)
FRINGE_ROOT = 0.8                # ... at its root under the rim this share of the radius (they crowd there)
DEBUG_FRINGE = bool(os.environ.get('DEBUG_FRINGE'))
FRINGE_DENSE = 89                # the bell worked out at this many points round the rim ...
FRINGE_TOUCH = 1.25              # ... and the strands set along its lower edge this many diameters apart (touching)
FRINGE_TILT = (22.0, 6.0, 4.0)   # degrees off the upright at the outer end, at the front and back, by the collar: the
                                 # portrait's fringe is a stiff bell, ~40 deg out over the arm (fanned out at 38-50 deg
                                 # below level they stood out like a sunburst; hanging nearly straight, a narrow tube)
FRINGE_TILT_MAX = 36.0           # ... out to this at most to clear what is under it (then shortened)
FRINGE_ENDS_TILT = 28.0          # ... but at the front and back (over the chest and the shoulder blade) out to this at
                                 # most: out to 36 deg the bell's ends splayed up, its strands there standing out from
                                 # the rest. Past that a strand lies on what is under it, hanging on down along it
                                 # (drape(); curled out over the rim first to clear it, the ends stood up over the
                                 # chest and the shoulder blade in a lifted lip)
FRINGE_TILT_SPREAD = 0.4         # ... its neighbours tilted as far, less this many degrees a degree round the rim
FRINGE_START, FRINGE_BEND = 40.0, 0.035  # ... coming out from under the rim this far off the upright, turning down to it over this
                                 # (at 55 the strands came out level over the tilted field: the fringe splayed up)
DRAPE_ROUNDS = 12                # drape(): rounds of pushing a strand out and evening it
FRINGE_SAMPLES, FRINGE_SMOOTH = 14, 6  # points down a strand checked; rounds of evening the tilts
FRINGE_CLEAR = 0.002             # a strand's surface off the cloth (and the sash, the cords) under it
FRINGE_STEP = 0.006              # path sampling along a strand (straight: few rings)
FRINGE_TIP = 0.32                # the bright wire end in each strand's rounded tip (x the radius)
# Bullion (canitel): gold wire coiled tight and the coil twisted - the portrait's strands are beaded all over, a slant
# row of grains per turn of the coil, shining (matt, with a rope's twist, they read as moulded rods)
BULLION_COIL, BULLION_GRAINS, BULLION_UV_LEN = 0.0055, 8, 0.147  # the coil's pitch, grains round a turn; metres of
                                 # strand over the width of its atlas region
BULLION_RELIEF = 0.4             # the coil's height (x pitch) in the normal map
BULLION_METAL, BULLION_ROUGH = (0.15, 0.75), (0.7, 0.32)  # in the gaps, on the grains: gold wire catching the light
THREAD_SRGB = (228, 156, 38)     # gold thread: the portrait's saturated yellow gold (the gilt's own hue read pale
                                 # peach on matt thread)
THREAD_SHEEN = (0.6, 0.35)       # thread's sheen (Principled sheen weight, roughness): soft fibre, not metal
# Sash: a band 'SASH_W' wide round the torso in the plane through the top of the right shoulder and the left hip.
SASH_SHOULDER = Vector((-0.193, 0.0, 1.77))  # in the portrait it comes over the shoulder from under the epaulette's
SASH_HIP = Vector((0.107, 0.0, 1.27))   # inner edge and runs steeply down across the chest (~0.6 px across per px down in
                                       # the 'ref' view; nearer the collar and flatter, it lay 30-40 px right of the
                                       # portrait's over the chest)
SASH_FLOOR = (-0.07, 0.08)       # its middle line held SASH_W / 2 + the first over the belt's top, eased in over the
                                       # second: in the portrait the band comes down to the belt at his left hip and
                                       # goes round his side along its top (the plane steep enough for the chest put its
                                       # bottom 15 cm under the belt - over the belt in front and slung below it)
SASH_V = (0.2, 0.0)             # ... that floor rising this much a metre to the front of this y (his side): the band
                                 # at its lowest by the hip at his side, a V there (held level over the belt from the
                                 # front round to the side, it read as a cummerbund)
SASH_BACK = (0.17, (-0.03, 0.08))  # on the back it runs straight from his left side (this x, at the floor's height) up
                                 # to the shoulder, fading in from the side over these y: held over the belt, the plane
                                 # (15 cm under the belt round the side) ran level round the waist like a cummerbund
SASH_W, SASH_GAP, SASH_THICK, SASH_N = 0.12, 0.005, 0.002, 320  # the portrait's band: ~12.5 cm wide
SASH_RELAX = 40                  # rounds of smoothing the band and pushing it out of the cloth
SASH_TIGHTEN = 25                # rounds of envelope() of the cloth the sash lies on
SASH_SETTLE = 14                 # rounds of relax() after the lift over the belt (the band's rows ~6 mm apart: fewer
                                 # left a crease where the lift began)
SASH_EVEN = 30                   # rounds of evening out the width along the band
BRIDGE_DZ, BRIDGE_SLOPE, BRIDGE_SPREAD, BRIDGE_SMOOTH = 0.07, 0.0007, 18, 30  # over the belt: zone round its centre; lift lost per step to a neighbour; steps
TORSO_ARM_Z = 1.5                # below this the upper arms' sleeves are not part of the torso surface
AIG_ARM_Z = 1.36                 # ... for the cords up to here: they lie on the sleeve's front all the way down (cast
                                 # onto the sleeve above 1.5 m and the chest under it, they jumped in depth there and
                                 # twisted together; without the sleeve they fell through the armpit)
GOLD_FLOOR = 0.55                # gold albedo: the pictures' shading only darkens it down to this (the relief does the rest)
NORMAL_STRENGTH = {'pole': 2.0, 'sash': 0.05}  # the pictures' light and dark as relief (the fringe's own)
# Aiguillettes, as the portrait shows them (px of alexander_ii_full.png, cast onto the chest): from under the right
# epaulette's fringe three cords hang down the front by the arm and sweep across in loops to the sash, going in under
# its lower edge one below the other (each carried on under the band to AIG_UNDER past the model's own sash edge,
# thinning there - the band lies over them); outside them a fourth hangs in a loop of its own by the arm, both its ends
# under the fringe. Side by side, at least a cord's thickness apart (where two crossed, the later was lifted over the
# other by its thickness and stood 2 cm off the chest; stack_lift() still keeps them apart if they touch).
AIG_REF = [
    [(396, 352), (401, 378), (409, 405), (416, 430), (425, 452), (438, 471), (456, 483), (476, 481), (494, 467),
     (510, 447)],
    [(406, 352), (411, 375), (419, 398), (430, 420), (444, 440), (460, 452), (478, 449), (497, 432)],
    [(416, 352), (422, 368), (431, 384), (443, 398), (456, 406), (470, 402), (482, 390)],
    [(372, 352), (375, 380), (379, 410), (384, 440), (389, 465), (394, 485), (399, 494), (404, 485), (405, 465),
     (400, 440), (395, 410), (390, 380), (384, 352)],              # the hanging loop by the arm
]
# (left to right under the fringe: the hanging loop's two legs, then the lowest, middle and top sash loops, ~1.6 cm
# apart - the portrait's order; the lowest loop started between the hanging loop's legs and the two twisted together)
# (laid in this order, each over the ones before where they cross: the hanging loop last - in the portrait the lowest
# sash loop runs up behind it; laid first, it had the others lifted over it into a twisted knot)
AIG_INTO_SASH = (True, True, True, False)  # which cords end in under the sash (the hanging loop ends under the fringe)
AIG_UNDER = 0.04                 # a cord's end this far in under the sash's edge (2.2 cm: the band lifted over the
                                 # cord showed its cut end at the edge)
AIG_THIN = (-0.002, 0.014, 0.4)   # under the band from the first to the second (m in from its edge) down to this
# The pencil: in the portrait it hangs over the sash from a gilt crook by the band's upper edge (its knob on the
# coat at the band's edge, where the cord it hangs by comes out from under the band - a stub of that cord, pressed
# under the band's edge, showed as a crumpled lump), its point over the band by the buttons.
PENCIL_KNOB, PENCIL_TOP, PENCIL_END = (585, 385), (608, 401), (617, 526)  # px (the top: its axis is lifted off the
                                 # sash and leans, at 615 it came out 7 px right of the portrait's)
KNOB_R, CROOK_R = 0.0085, 0.0058  # the crook's knob and its neck (gilt, cast with the pencil)
AIG_R, AIG_GAP = 0.0050, 0.0015  # the portrait's cords: ~1.2-1.3 cm thick round braid (9 px; at 1.6 cm they
                                 # came out much thicker than the portrait's next to the fringe)
AIG_UP, AIG_UP_X = 45, 15  # px: the cords begin this much over where the portrait shows them, in under the
                                 # epaulette's field (25 px over: with the fringe hanging close round the shoulder their
                                 # cut ends showed under it); and AIG_UP_X px out, towards the arm (the two by the sash
                                 # came up beside the fringe, at its edge)
AIG_STEP = 0.003                 # path sampling along a cord (its braid is modelled in its surface)
AIG_STACK = 0.001                # crossing cords: the one on top at least this far off the one under it
BRAID_N, BRAID_PITCH, BRAID_SLANT = 2, 0.6 / 107, 1.45  # the braid's chevrons round the cord, their pitch along it
                                 # (a whole number of them in CORD_UV_LEN: the texture repeats along a long cord), the
                                 # strands' slant (along per half chevron, x pitch): the herringbone of the portrait's
BRAID_FIBRES = 5                 # fibres across a strand
BRAID_AMP = 0.12                 # the strands stand this much of the radius proud
AIG_AREA = (330, 300, 560, 540)  # px of the portrait the cords lie over (their layer: build_loops)
AIG_BRIDGE = 12                  # px (~1.7 cm): the layer takes the nearest cloth this far round, then is smoothed as far
AIG_STIFF = 10                   # rounds of straightening the cords over the cloth's folds
PENCIL_L = 0.185
# The pencil (the aiguillette's cast tip), top to point: (t along it, radius m, fluted) - a cup the cord goes into, a
# knob, a fluted shaft between ring mouldings, a vase-shaped boss, a second fluted shaft down to a ball (as the portrait's)
PENCIL_PROFILE = [(0.0, 0.0), (0.004, 0.0062), (0.012, 0.0082), (0.045, 0.0088), (0.055, 0.0058), (0.075, 0.0058),
                  (0.095, 0.0092), (0.115, 0.0092), (0.135, 0.0056), (0.15, 0.0056), (0.16, 0.0079), (0.18, 0.0079),
                  (0.19, 0.0062, True), (0.43, 0.0062, True), (0.44, 0.0079), (0.46, 0.0079), (0.47, 0.0060),
                  (0.53, 0.0088), (0.57, 0.0088), (0.62, 0.0060), (0.63, 0.0077), (0.65, 0.0077),
                  (0.66, 0.0058, True), (0.86, 0.0046, True), (0.87, 0.0064), (0.89, 0.0064), (0.90, 0.0046),
                  (0.915, 0.0050), (0.94, 0.0072), (0.965, 0.0074), (0.985, 0.0055), (1.0, 0.0)]  # a ball at the end
PENCIL_FLUTES, PENCIL_FLUTE_D = 10, 0.0009  # flutes round the shafts and their depth
PENCIL_K = 1.55                  # every radius of the profile times this: the portrait's pencil is ~2.2 cm thick
CORD_UV_LEN = 0.6                # metres of cord over the width of its atlas region (the twist repeats along it)

ATLAS = {
    'sash': (0.0, 0.0, 1.0, 0.125),
    'cord': (0.0, 0.75, 1.0, 0.875),      # (twice the texels round the cord and the strand of the regions they had)
    'bullion': (0.0, 0.875, 1.0, 1.0),
    'pole': (0.0, 0.25, 0.5, 0.75),
    'gold': (0.5, 0.25, 0.5625, 0.3125),
    'tip': (0.5625, 0.25, 0.625, 0.3125),  # the fringe strands' bright wire ends
    'strap': (0.5, 0.375, 1.0, 0.5),
    'chased': (0.5, 0.5, 1.0, 0.75),
}
# Gold thread (cords, fringe, galloon, the field's embroidery, the tassels) is yellow fibre, not metal: no metal at
# all, matt, a little smoother on the crests (even a faint metallic on the crests read as metal in a lit viewport);
# the cords and the fringe drawn as fibre - braided strands and twisted plies, each of fine fibres of slightly different
# tone (a smooth helix of coils read as moulded metal). The cast pieces (buttons, pencils) are gilt metal, chased all
# over (the 'chased' region).
THREAD_METAL, THREAD_ROUGH = (0.0, 0.0), (0.92, 0.66)  # in the gaps, on the crests
CAST_METAL, CAST_ROUGH = 0.9, 0.36
CHASED_TILES = (6, 14)           # the pencil's chased ornament: tiles round it, along it
# The generated material pictures (textures/gen, see art/prompts.md) and how often they repeat in their regions.
SASH_CONTRAST = 2.5               # the damask's light and dark, stronger than generated (it is faint on the model)
SASH_REPEATS = 12                # mirrored, even: the band's ends meet on the same column

sc = bpy.context.scene
P = sc['uniform'].to_dict()
rig = bpy.data.objects['HumanRig']
rig.data.pose_position = 'REST'
uni = bpy.data.objects['Uniform']
for o in list(bpy.data.objects):  # previous run
    if o.get('regalia'):
        bpy.data.objects.remove(o)
bones = {b.name for b in rig.data.bones}


def smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- surfaces and weights
def envelope(bm, rounds):
    """bm smoothed from the outside: each round every vertex moves to its neighbours' mean, but never inside where it
    was (along its normal) - the surface tightens over the folds like a band laid across them, the crests kept."""
    bm.normal_update()
    vs = list(bm.verts)
    orig = [v.co.copy() for v in vs]
    nrm = [v.normal.copy() for v in vs]
    nbs = [[e.other_vert(v) for e in v.link_edges] for v in vs]
    for _ in range(rounds):
        new = []
        for v, o, n, nb in zip(vs, orig, nrm, nbs):
            if v.is_boundary or not nb:
                new.append(v.co.copy()); continue
            q = sum((x.co for x in nb), Vector()) / len(nb)
            h = (q - o).dot(n)
            new.append(q + n * -h if h < 0 else q)
        for v, q in zip(vs, new):
            v.co = q


def bvh_of(obs, torso=False, tighten=0, arm_z=None, outer=False):
    """BVH of the objects; torso: the uniform without its sleeves (the sash and the cords lie on the torso - the hanging
    left arm is right by the sash's end at the hip, which would wrap onto it); tighten: rounds of envelope() on the
    uniform (a band lies across its folds, not into them); arm_z: the sleeves go up to this height (TORSO_ARM_Z);
    outer: only the faces turned away from the body (a band's top: its underside, facing in, read a point between the
    band and the cloth as clear of both)."""
    arm_z = TORSO_ARM_Z if arm_z is None else arm_z
    bm = bmesh.new()
    for o in obs:
        me = o.data.copy(); me.transform(o.matrix_world)
        if o == uni:  # the outside only: the lining (material slot 1, build_pose.py) faces inwards
            b2 = bmesh.new(); b2.from_mesh(me)
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.material_index == 1], context='FACES')
            b2.to_mesh(me); b2.free()
        if o == uni and torso:
            b2 = bmesh.new(); b2.from_mesh(me)
            dl = b2.verts.layers.deform.active
            names = [g.name for g in uni.vertex_groups]
            fore = {i for i, n in enumerate(names) if n.startswith(('lowerarm', 'hand'))}
            upper = {i for i, n in enumerate(names) if n.startswith('upperarm')}
            # the sleeves by the hips go; not the cloth behind the shoulders (the arms taken back pull it onto the back)
            bmesh.ops.delete(b2, geom=[v for v in b2.verts
                                       if sum(w for g, w in v[dl].items() if g in fore) > 0.3
                                       or (v.co.z < arm_z and sum(w for g, w in v[dl].items() if g in upper) > 0.5)],
                             context='VERTS')
            b2.to_mesh(me); b2.free()
        if o == uni and tighten:
            b2 = bmesh.new(); b2.from_mesh(me)
            envelope(b2, tighten)
            b2.to_mesh(me); b2.free()
        if outer:
            b2 = bmesh.new(); b2.from_mesh(me)
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.normal.dot(
                f.calc_center_median() - Vector((0.0, 0.0, f.calc_center_median().z - 0.3))) <= 0], context='FACES')
            b2.to_mesh(me); b2.free()
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    t = BVHTree.FromBMesh(bm); bm.free()
    return t


CLOTH = bvh_of([uni] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons')], torso=True)  # the sash lies on these


class Weights:
    """Bone weights of a skinned mesh, looked up at any point (inverse-distance blend of the nearest vertices)."""

    def __init__(self, ob, torso=False):
        """torso: only the vertices the arms do not move (things on the chest and hips lie by the sleeves - the sash's
        end by the left cuff - and must not follow them)."""
        names = [g.name for g in ob.vertex_groups]
        me = ob.data
        arm = lambda n: n.startswith(('upperarm', 'lowerarm', 'hand', 'index', 'middle', 'ring', 'pinky', 'thumb'))  # noqa
        keep = [v for v in me.vertices
                if not torso or sum(g.weight for g in v.groups if arm(names[g.group])) < 0.05]
        self.kd = KDTree(len(keep))
        self.w = []
        for i, v in enumerate(keep):
            self.kd.insert(v.co, i)
            self.w.append({names[g.group]: g.weight for g in v.groups if names[g.group] in bones and g.weight > 0})
        self.kd.balance()

    def at(self, co, k=4):
        acc = {}
        for _, i, d in self.kd.find_n(co, k):
            for n, w in self.w[i].items():
                acc[n] = acc.get(n, 0.0) + w / (d + 1e-4)
        top = sorted(acc.items(), key=lambda x: -x[1])[:4]
        s = sum(w for _, w in top)
        return {n: w / s for n, w in top}


UNI_W = Weights(uni)
TORSO_W = Weights(uni, torso=True)


def outer(bvh, o, d, maxd=0.5):
    """The outermost surface point from o along d (cast back from maxd), its normal; (None, None) if none."""
    loc, nrm, _, _ = bvh.ray_cast(o + d * maxd, -d, maxd)
    return loc, nrm


def front_at(bvh, x, z):
    """Front surface (seen from -Y) at (x, z): point, normal."""
    return bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 2.0)[:2]


# ---------------------------------------------------------------- texture atlas (sRGB)
def srgb(c):
    return np.array(c, np.float32) / 255


def gen_picture(name):
    """textures/gen/<name>.png as an sRGB float array, row 0 = bottom (Blender's order)."""
    img = bpy.data.images.load(os.path.join(TEXDIR, 'gen', name + '.png'), check_existing=False)
    w, hh = img.size
    a = np.array(img.pixels[:], np.float32).reshape(hh, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


def sample(img, u, v):
    """Bilinear lookup at normalised coordinates (arrays), v = 0 bottom."""
    hh, w = img.shape[:2]
    x = np.clip(u * (w - 1), 0, w - 1.001); y = np.clip(v * (hh - 1), 0, hh - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return ((img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx) * (1 - fy)
            + (img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx) * fy)


def grid(w, hh):
    return np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))


def sash_tex(w, hh):
    """The generated damask moire, its height across the band, mirrored repeats along it; toned to the portrait's
    blue."""
    pic = gen_picture('sash_damask')
    u, v = grid(w, hh)
    t = (u * SASH_REPEATS) % 2.0
    rgb = sample(pic, np.where(t > 1, 2 - t, t), v)
    med = np.median(pic.reshape(-1, 3), 0)
    return np.clip(srgb(SASH_SRGB) * (1 + (rgb / med - 1) * SASH_CONTRAST), 0, 1)  # the damask shows a little more


def fibre_noise(shape, seed, wrap=False):
    """Smooth random tone per texel area (0..1): a few octaves of value noise, for the fibres' uneven colour; wrap:
    its right edge runs on into its left (a texture repeated along a tube)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(shape, np.float32)
    for cells, wgt in ((8, 0.5), (32, 0.3), (128, 0.2)):
        g = rng.random((cells + 1, cells + 1)).astype(np.float32)
        if wrap:
            g[:, cells] = g[:, 0]
        y = np.linspace(0, cells, shape[0]); x = np.linspace(0, cells, shape[1])
        y0 = np.minimum(y.astype(int), cells - 1); x0 = np.minimum(x.astype(int), cells - 1)
        fy = (y - y0)[:, None]; fx = (x - x0)[None, :]
        a = g[y0][:, x0]; b = g[y0][:, x0 + 1]; c = g[y0 + 1][:, x0]; d = g[y0 + 1][:, x0 + 1]
        out += wgt * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
    return out


def thread_colour(h, fib, tone):
    """Gold thread: dark ochre deep in the gaps, the gold on the crests, each fibre its own tone."""
    base = srgb(THREAD_SRGB)
    dark = base * np.array([0.42, 0.33, 0.22], np.float32)
    k = np.clip(h, 0, 1)[..., None]
    c = dark * (1 - k) + base * k
    return np.clip(c * (0.93 + 0.07 * fib[..., None]) * (0.9 + 0.2 * tone[..., None]), 0, 1)


def braid_height(along, round_):
    """The round braid's relief (0..1) at 'along' (pitches along the cord) and 'round_' (0..1 round it): BRAID_N
    columns of chevrons, each a pair of strands slanting from the column's middle line out to its sides (the
    herringbone of the portrait's cords), a groove between the strands, between the pairs and along the middle line;
    also the fibre phase across a strand. Shared by the texture and the cord's modelled surface."""
    w = (round_ * BRAID_N) % 1.0
    tri = np.abs(w - 0.5) * 2.0                    # 0 on a chevron's middle line, 1 at its sides
    f = (along + tri * BRAID_SLANT) % 1.0          # across a strand, from groove to groove
    groove = np.abs(np.sin(np.pi * w * 2.0)) ** 0.35  # the middle line and the sides: the strands part there
    h = np.sin(np.pi * f) ** 0.6 * (0.45 + 0.55 * groove)
    return h, f


def braid_tex(w, hh):
    """The aiguillette's braided cord, its length along u (CORD_UV_LEN metres), round it along v (braid_height), each
    strand of BRAID_FIBRES fibres along it. Returns albedo and the height 0..1."""
    u, v = grid(w, hh)
    h, f = braid_height(u * CORD_UV_LEN / BRAID_PITCH, v)
    fib = 0.5 + 0.5 * np.cos(2 * np.pi * f * BRAID_FIBRES)
    h = h * (0.94 + 0.06 * fib)
    tone = fibre_noise(h.shape, 7, wrap=True)
    return thread_colour(h, fib, tone), h


def chased_tex(w, hh):
    """Chased gilt ornament for the cast pieces (the pencils), round them along u, along them along v: tiles of
    scrolls (a spiral leaf, turning the other way in the next tile) between bead rows. Returns the height 0..1."""
    u, v = grid(w, hh)
    tu, tv = u * CHASED_TILES[0], v * CHASED_TILES[1]
    lx, ly = (tu % 1.0) * 2 - 1, (tv % 1.0) * 2 - 1
    flip = np.where((np.floor(tu) + np.floor(tv)) % 2 == 0, 1.0, -1.0)
    r, th = np.hypot(lx, ly), np.arctan2(ly, lx) * flip
    leaf = 0.5 + 0.5 * np.sin(2 * th + 8 * r)
    leaf = np.clip(leaf * 1.4 - 0.2, 0, 1) * (1 - np.clip((r - 0.9) * 6, 0, 1))
    bead = (np.abs(ly) > 0.86) * (0.5 + 0.5 * np.cos(u * 2 * np.pi * CHASED_TILES[0] * 6))
    return blur1(np.maximum(leaf * 0.85, bead))


def strap_tex(w, hh):
    """The epaulette's strap: the generated galloon (gold stripes between red borders) along it, its gold graded to
    the portrait's; returns the colour and a gold mask."""
    u, v = grid(w, hh)
    pic = sample(gen_picture('belt_galloon'), (u * STRAP_REPEATS) % 1.0, v)
    gold = np.clip(((pic[..., 1] > 0.45 * pic[..., 0]) & (pic[..., 0] > 0.25)).astype(np.float32), 0, 1)
    gold = blur1(gold)
    return mat_util.gold_grade(np.clip(pic * 1.15, 0, 1), gold), gold


def pole_tex(w, hh):
    """The epaulette's field from above: the generated round plate (rope rim, beads, eagle)."""
    return sample(gen_picture('epaulette_field'), *grid(w, hh))


def ply_height(phase):
    """A twisted strand's relief (0..1) at the helix phase (turns along it + plies round it): each ply a round
    bulge, a dark seam between; also the phase across the ply. Shared by the texture and the strand's surface."""
    f = np.asarray(phase) % 1.0
    return np.sin(np.pi * f) ** 0.45, f


def bullion_tex(w, hh):
    """A fringe strand, its length along u (BULLION_UV_LEN metres), round it along v: coiled gold wire, a slanting
    turn per BULLION_COIL, each turn a row of BULLION_GRAINS grains (the beaded look of the portrait's fringe), dark in
    the gaps. Returns albedo, roughness (None) and the height in metres per pixel (for the normal map)."""
    u, v = grid(w, hh)
    turns = u * BULLION_UV_LEN / BULLION_COIL + v  # one slanting turn of the coil round the strand per pitch
    f = turns % 1.0
    g = (v * BULLION_GRAINS + np.floor(turns) * 0.5) % 1.0  # grains along each turn, staggered turn to turn
    h = np.sin(np.pi * f) ** 0.7 * (0.3 + 0.7 * np.sin(np.pi * g) ** 0.6)  # beads standing out (0.5: rings)
    tone = fibre_noise(h.shape, 11)
    return thread_colour(h, h, tone), None, h * BULLION_COIL * BULLION_RELIEF


def normals(height, mx, my):
    """Tangent-space normals (OpenGL) of a height field in metres, mx / my metres per pixel along u / v."""
    gy, gx = np.gradient(height)
    n = np.stack([-gx / mx, -gy / my, np.ones_like(height)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def blur1(a):
    return (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5


def build_atlas():
    rgb = np.zeros((TEX, TEX, 3), np.float32)
    metal = np.zeros((TEX, TEX), np.float32); rough = np.full((TEX, TEX), 0.8, np.float32)
    nrm = np.zeros((TEX, TEX, 3), np.float32); nrm[..., 2] = 1.0

    def px(region):
        u0, v0, u1, v1 = ATLAS[region]
        return int(u0 * TEX), int(v0 * TEX), int(u1 * TEX), int(v1 * TEX)

    def relief(region, c, strength):  # the picture's own light and dark as its relief (raised where bright)
        x0, y0, x1, y1 = px(region)
        lum = blur1(c @ np.array([0.2126, 0.7152, 0.0722], np.float32))
        nrm[y0:y1, x0:x1] = normals(lum * strength, 0.1, 0.1)  # strength x 10: slope per unit of brightness a pixel

    x0, y0, x1, y1 = px('sash')
    pic = sash_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = pic; rough[y0:y1, x0:x1] = 0.6  # silk moire: a soft sheen, no gloss
    relief('sash', pic, NORMAL_STRENGTH['sash'])

    def thread(region, crest):
        """Metal and roughness of gold thread by how high each texel is (crest 0..1)."""
        x0, y0, x1, y1 = px(region)
        metal[y0:y1, x0:x1] = THREAD_METAL[0] + (THREAD_METAL[1] - THREAD_METAL[0]) * crest
        rough[y0:y1, x0:x1] = THREAD_ROUGH[0] + (THREAD_ROUGH[1] - THREAD_ROUGH[0]) * crest

    def gold(region, c, recolour=True):
        """Gold from a generated picture: its shading only darkens bright gold down to GOLD_FLOOR (dark pictures made
        dull brown metal); bright thread shines a little, the gaps between are rough."""
        x0, y0, x1, y1 = px(region)
        lum = c @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        shade = np.clip(lum / max(float(np.percentile(lum, 95)), 1e-3), 0, 1)
        rgb[y0:y1, x0:x1] = (srgb(GOLD_SRGB) * (GOLD_FLOOR + (1 - GOLD_FLOOR) * shade)[..., None] if recolour
                             else mat_util.gold_grade(np.clip(c * 1.25, 0, 1), np.clip(shade * 3, 0, 1)))
        thread(region, shade)
        relief(region, c, NORMAL_STRENGTH[region])

    x0, y0, x1, y1 = px('cord')
    c, hb = braid_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c
    thread('cord', hb)
    nrm[y0:y1, x0:x1] = normals(hb * 0.0012, CORD_UV_LEN / (x1 - x0), 2 * math.pi * AIG_R / (y1 - y0))
    x0, y0, x1, y1 = px('bullion')
    c, r, hgt = bullion_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c
    crest = np.clip((hgt / hgt.max()), 0, 1)
    metal[y0:y1, x0:x1] = BULLION_METAL[0] + (BULLION_METAL[1] - BULLION_METAL[0]) * crest
    rough[y0:y1, x0:x1] = BULLION_ROUGH[0] + (BULLION_ROUGH[1] - BULLION_ROUGH[0]) * crest
    nrm[y0:y1, x0:x1] = normals(hgt, BULLION_UV_LEN / (x1 - x0), 2 * math.pi * FRINGE_R / (y1 - y0))
    x0, y0, x1, y1 = px('pole')
    gold('pole', pole_tex(x1 - x0, y1 - y0), recolour=False)
    x0, y0, x1, y1 = px('strap')
    c, gm = strap_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c
    lum = c @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    shade = np.clip(lum / max(float(np.percentile(lum, 95)), 1e-3), 0, 1)
    thread('strap', shade * gm)
    rough[y0:y1, x0:x1] = np.where(gm > 0.5, rough[y0:y1, x0:x1], 0.75)  # the red borders: silk
    relief('strap', c, 1.0)
    x0, y0, x1, y1 = px('gold')
    rgb[y0:y1, x0:x1] = srgb(GOLD_SRGB); metal[y0:y1, x0:x1] = CAST_METAL; rough[y0:y1, x0:x1] = CAST_ROUGH
    x0, y0, x1, y1 = px('tip')
    rgb[y0:y1, x0:x1] = srgb((236, 226, 196)); metal[y0:y1, x0:x1] = 1.0; rough[y0:y1, x0:x1] = 0.2
    x0, y0, x1, y1 = px('chased')
    h = chased_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = srgb(GOLD_SRGB) * (0.5 + 0.5 * h)[..., None]  # dark in the recesses (worn bright on top)
    metal[y0:y1, x0:x1] = CAST_METAL; rough[y0:y1, x0:x1] = CAST_ROUGH + 0.2 * (1 - h)
    nrm[y0:y1, x0:x1] = normals(h * 0.00035, PENCIL_L / (y1 - y0), 2 * math.pi * 0.007 / (x1 - x0))
    imgs = []
    for name, data, path, cs in (('Regalia_Albedo', rgb, ALBEDO_OUT, 'sRGB'),
                                 ('Regalia_MR', np.stack([metal, rough, np.zeros_like(metal)], 2), MR_OUT, 'Non-Color'),
                                 ('Regalia_Normal', nrm * 0.5 + 0.5, NORMAL_OUT, 'Non-Color')):
        img = bpy.data.images.get(name) or bpy.data.images.new(name, TEX, TEX)
        img.scale(TEX, TEX)
        img.pixels.foreach_set(np.concatenate([data, np.ones((TEX, TEX, 1), np.float32)], 2).astype(np.float32).ravel())
        img.filepath_raw = path; img.file_format = 'PNG'; mat_util.write(img)
        img.filepath = path; img.source = 'FILE'
        img.colorspace_settings.name = cs
        imgs.append(img)
    mat = bpy.data.materials.get('Regalia') or bpy.data.materials.new('Regalia')
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in [nd for nd in nt.nodes if nd.type in ('TEX_IMAGE', 'SEPARATE_COLOR', 'NORMAL_MAP')]:
        nt.nodes.remove(nd)
    bsdf = next(nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED')
    ta, tm, tn = (nt.nodes.new('ShaderNodeTexImage') for _ in range(3))
    ta.image, tm.image, tn.image = imgs
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(ta.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs[0], bsdf.inputs['Metallic'])
    nt.links.new(sep.outputs[1], bsdf.inputs['Roughness'])
    nt.links.new(tn.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    for nd in [nd for nd in nt.nodes if nd.type == 'MATH']:
        nt.nodes.remove(nd)
    sheen = nt.nodes.new('ShaderNodeMath'); sheen.operation = 'MULTIPLY_ADD'  # (1 - metal) x weight: thread only
    sheen.inputs[1].default_value = -THREAD_SHEEN[0]; sheen.inputs[2].default_value = THREAD_SHEEN[0]
    nt.links.new(sep.outputs[0], sheen.inputs[0])
    nt.links.new(sheen.outputs[0], bsdf.inputs['Sheen Weight'])
    bsdf.inputs['Sheen Roughness'].default_value = THREAD_SHEEN[1]
    spec = nt.nodes.new('ShaderNodeMath'); spec.operation = 'MULTIPLY_ADD'  # thread: a weak white specular (it
    spec.inputs[1].default_value = 0.35; spec.inputs[2].default_value = 0.15  # washed the gold out to pale peach)
    nt.links.new(sep.outputs[0], spec.inputs[0])
    nt.links.new(spec.outputs[0], bsdf.inputs['Specular IOR Level'])
    nt.links.new(ta.outputs['Color'], bsdf.inputs['Sheen Tint'])
    print('atlas', ALBEDO_OUT)
    return mat


MAT = build_atlas()


def uv_in(region, u, v):
    u0, v0, u1, v1 = ATLAS[region]
    pad = 2 / TEX
    return (u0 + pad + (u1 - u0 - 2 * pad) * u, v0 + pad + (v1 - v0 - 2 * pad) * v)


# ---------------------------------------------------------------- mesh helpers
def new_part(name, bm, uvs, weights, solidify=0.0):
    """bm with per-vertex UVs and weights (functions of the vertex) -> skinned object 'name'."""
    if uvs is not None:  # None: bm brings its own 'UVMap'
        for lay in list(bm.loops.layers.uv.values()):
            bm.loops.layers.uv.remove(lay)
        lay = bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            for l in f.loops:
                l[lay].uv = uvs(l.vert)
    vw = [weights(v) for v in bm.verts]
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    ob['regalia'] = True
    me.materials.append(MAT)
    for p in me.polygons:
        p.use_smooth = True
    for i, ws in enumerate(vw):
        for n, w in ws.items():
            g = ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)
            g.add([i], w, 'REPLACE')
    if solidify:
        m = ob.modifiers.new('Thick', 'SOLIDIFY'); m.thickness = solidify; m.offset = -1; m.use_rim = True
        for o in sc.objects:
            o.select_set(o == ob)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier='Thick')
    ob.modifiers.new('Armature', 'ARMATURE').object = rig
    print('part %s: %d tris' % (name, sum(len(p.vertices) - 2 for p in me.polygons)))
    return ob


def catmull(pts, step):
    """Catmull-Rom through pts, sampled every ~step."""
    P_ = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            s = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
    out.append(pts[-1])
    return out


def tube(bm, path, r, sides, region, uv_len=CORD_UV_LEN, cap=True, taper=None, relief=None, u0=0.0, cap0=False):
    """A tube along path into bm (the seam column doubled for the UVs); returns its verts and their UVs. relief(s, v):
    the radius' factor at s metres along and v (0..1) round (the strands of a braid, the plies of a twisted cord,
    modelled); u0: where along its atlas region the tube's texture starts. Past the region's end the texture starts
    again on a doubled ring (clamped there, a cord longer than uv_len had the region's last column of texels drawn
    out over its whole tail: a smooth streaked stretch among the braided ones). cap0: the start rounded off too."""
    uvs = {}
    prev_u = None
    rings, s = [], 0.0
    lap = 0          # the texture's repeats passed
    cut = set()      # rings after which a new run starts (no faces across)

    def make_ring(p, u, w, rr, s, uu):
        ring = []
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            rk = rr * (relief(s + u0 * uv_len, k / sides) if relief else 1.0)
            v = bm.verts.new(p + rk * (math.cos(a) * u + math.sin(a) * w))
            uvs[v] = uv_in(region, uu, k / sides)
            ring.append(v)
        return ring
    rr_prev = None
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if prev_u is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            prev_u = t.cross(ref).normalized()
        u = (prev_u - t * prev_u.dot(t)).normalized(); prev_u = u  # parallel transport: no twist
        w = t.cross(u)
        s0 = s
        if i:
            s += (p - path[i - 1]).length
        rr = r * (taper(i / (len(path) - 1)) if taper else 1.0)
        while i and s / uv_len + u0 - lap > 1.0:  # the region's end inside this step: a ring there, twice
            sc = (lap + 1 - u0) * uv_len
            f = (sc - s0) / max(s - s0, 1e-9)
            pc, rc = path[i - 1].lerp(p, f), rr_prev + (rr - rr_prev) * f
            rings.append(make_ring(pc, u, w, rc, sc, 1.0))
            cut.add(len(rings) - 1)
            lap += 1
            rings.append(make_ring(pc, u, w, rc, sc, 0.0))
        rings.append(make_ring(p, u, w, rr, s, s / uv_len + u0 - lap))
        rr_prev = rr
    for j, (r0, r1) in enumerate(zip(rings, rings[1:])):
        if j in cut:
            continue
        for k in range(sides):
            bm.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
    if cap0:  # the same dome on the first ring, pointing back (a cord's top cut square showed under the fringe)
        t = (path[0] - path[1]).normalized()
        rr = r * (taper(0.0) if taper else 1.0)
        tf = -t
        u = (rings[0][0].co - path[0]).normalized()
        w = tf.cross(u)  # the first ring's own frame: the dome's rings line up with it
        prev = rings[0]
        for a in (30, 60):
            ring = []
            for k in range(sides + 1):
                b = 2 * math.pi * k / sides
                v = bm.verts.new(path[0] + t * rr * 0.8 * math.sin(math.radians(a))
                                 + rr * math.cos(math.radians(a)) * (math.cos(b) * u + math.sin(b) * w))
                uvs[v] = uv_in(region, min(u0 + 0.004 * a / 30, 1.0), k / sides)
                ring.append(v)
            for k in range(sides):
                bm.faces.new((ring[k], ring[k + 1], prev[k + 1], prev[k]))
            prev = ring
        tip = bm.verts.new(path[0] + t * rr * 0.8)
        uvs[tip] = uv_in(region, min(u0 + 0.012, 1.0), 0.5)
        for k in range(sides):
            bm.faces.new((prev[k + 1], prev[k], tip))
    if cap:  # rounded end: a dome on the last ring (a cone to a point showed as dark teeth)
        t = (path[-1] - path[-2]).normalized()
        rr = r * (taper(1.0) if taper else 1.0)
        u, w = (rings[-1][0].co - path[-1]).normalized(), None
        w = t.cross(u)
        u_end = s / uv_len + u0 - lap      # the strand's own texture runs on over the dome (another region's UVs there
        for a in (30, 60):            # made a dark ring: the faces between ran across the atlas)
            ring = []
            for k in range(sides + 1):
                b = 2 * math.pi * k / sides
                v = bm.verts.new(path[-1] + t * rr * 0.8 * math.sin(math.radians(a))
                                 + rr * math.cos(math.radians(a)) * (math.cos(b) * u + math.sin(b) * w))
                uvs[v] = uv_in(region, max(u_end - 0.004 * a / 30, 0.0), k / sides)
                ring.append(v)
            for k in range(sides):
                bm.faces.new((rings[-1][k], rings[-1][k + 1], ring[k + 1], ring[k]))
            rings.append(ring)
        tip = bm.verts.new(path[-1] + t * rr * 0.8)
        uvs[tip] = uv_in(region, max(u_end - 0.012, 0.0), 0.5)
        for k in range(sides):
            bm.faces.new((rings[-1][k], rings[-1][k + 1], tip))
    return [v for ring in rings for v in ring], uvs


def braid_relief(s, v):
    return 1.0 + BRAID_AMP * (float(braid_height(s / BRAID_PITCH, v)[0]) - 0.6)


def ply_relief(s, v):
    return 1.0 + BULLION_AMP * (float(ply_height(s / BULLION_PITCH + v * BULLION_STARTS)[0]) - 0.6)


# ---------------------------------------------------------------- sash
def build_sash():
    """A band SASH_W wide round the torso. Its middle line: the outermost cloth (tunic, belt, collar) round the plane
    through SASH_SHOULDER and SASH_HIP that holds the front-back axis, held over the belt (SASH_FLOOR), on the back
    straight up from the side (SASH_BACK), smoothed. Across it, at every point, the band
    runs along the cloth square to the line (the cloth's normal x the line's direction), so it keeps its width where
    the torso turns away from that plane; SASH_GAP off the cloth."""
    U = (SASH_SHOULDER - SASH_HIP).normalized()
    Y = Vector((0, 1, 0))
    N = U.cross(Y).normalized()
    c = (SASH_SHOULDER + SASH_HIP) / 2
    rows = 21  # rows across: fine enough to lie over the cords under it (1.3 cm thick; coarser, they came through it)

    def on_cloth(p):
        loc, nrm, _, _ = CLOTH.find_nearest(p, 0.1)
        return (loc + nrm * SASH_GAP, nrm) if loc is not None else (p, N)

    mid = []
    for j in range(SASH_N):
        th = 2 * math.pi * j / SASH_N  # 0: front, pi/2: up the shoulder
        d = -Y * math.cos(th) + U * math.sin(th)
        loc, nrm = outer(CLOTH, c, d)
        p = (loc + nrm * SASH_GAP) if loc is not None else c + d * 0.2
        zf, ease = P['BELT_ZC'] + P['BELT_H'] / 2 + SASH_W / 2 + SASH_FLOOR[0], SASH_FLOOR[1]
        xs, (y0, y1) = SASH_BACK
        z_back = zf + (xs - p.x) * (SASH_SHOULDER.z - zf) / (xs - SASH_SHOULDER.x)
        p.z = p.z + max(0.0, z_back - p.z) * smoothstep(p.y, y0, y1) * (1 - smoothstep(p.x, xs, xs + 0.06))
        zv = zf + SASH_V[0] * max(0.0, SASH_V[1] - p.y)  # the floor rising to the front from his side
        p.z = 0.5 * (p.z + zv + math.sqrt((p.z - zv) ** 2 + ease * ease))  # a smooth max(z, zv)
        mid.append(p)
    for _ in range(12):  # the cloth's buttons and seams would show through
        mid = [mid[j] * 0.5 + (mid[j - 1] + mid[(j + 1) % SASH_N]) * 0.25 for j in range(SASH_N)]
        mid = [on_cloth(p)[0] for p in mid]
    sides = []
    for j in range(SASH_N):
        t = (mid[(j + 1) % SASH_N] - mid[j - 1]).normalized()
        side = on_cloth(mid[j])[1].cross(t).normalized()
        sides.append(side if side.dot(N) > 0 else -side)
    for _ in range(4):  # no twisting where the cloth's normal turns quickly (the shoulder)
        sides = [(sides[j] * 2 + sides[j - 1] + sides[(j + 1) % SASH_N]).normalized() for j in range(SASH_N)]
    bm = bmesh.new()
    grid, uvs = [], {}
    for i in range(rows):
        s_ = (i / (rows - 1) - 0.5) * SASH_W
        row = []
        for j in range(SASH_N):
            # the band's width is laid out along the cloth in two steps (it bends round the torso)
            p = on_cloth(mid[j] + sides[j] * s_ * 0.5)[0]
            p = on_cloth(p + sides[j] * s_ * 0.5)[0]
            v = bm.verts.new(p)
            row.append(v)
        row.append(row[0])
        grid.append(row)
    def relax(rounds):
        for _ in range(rounds):  # a smooth band (the projection snaps to the belt's and buttons' edges), and nothing
            # of the cloth through it: every vertex at least SASH_GAP outside the surface nearest to it
            new = {}
            for i, row in enumerate(grid):
                for j in range(SASH_N):
                    ns = [row[j - 1].co, row[(j + 1) % SASH_N].co]
                    if 0 < i < rows - 1:
                        ns += [grid[i - 1][j].co, grid[i + 1][j].co]
                    new[row[j]] = row[j].co * 0.5 + sum(ns, Vector()) / len(ns) * 0.5
            for v, co in new.items():
                v.co = co
            for row in grid:
                for v in row[:-1]:
                    loc, nrm, _, _ = CLOTH.find_nearest(v.co, 0.05)
                    if loc is not None and (v.co - loc).dot(nrm) < SASH_GAP:
                        v.co = loc + nrm * SASH_GAP

    relax(SASH_RELAX)
    # an even width: each row's offset from the middle row smoothed along the band (an edge laid onto a fold of the
    # cloth jumps in or out in a notch), then off the cloth again
    midr = rows // 2
    for _ in range(SASH_EVEN):
        offs = [[grid[i][j].co - grid[midr][j].co for j in range(SASH_N)] for i in range(rows)]
        for i in range(rows):
            if i == midr:
                continue
            for j in range(SASH_N):
                o = (offs[i][j - 1] + offs[i][j] * 2 + offs[i][(j + 1) % SASH_N]) / 4
                v = grid[i][j]
                v.co = grid[midr][j].co + o
                loc, nrm, _, _ = CLOTH.find_nearest(v.co, 0.05)
                if loc is not None and (v.co - loc).dot(nrm) < SASH_GAP:
                    v.co = loc + nrm * SASH_GAP
    # over the belt: the band bridges its raised edges (a band laid on each nearest surface dips in behind them and
    # the edge cuts through): how far each vertex must go out (to the outermost surface along the ray from the
    # torso's axis), fading out towards the zone's edges, spread to its neighbours with a gentle slope, the band lifted
    # by it (the radius itself spread, the band above the belt was pushed out to the belt's and fell back in a crease)
    zc = P['BELT_ZC']
    need = [[0.0] * SASH_N for _ in range(rows)]
    for i, row in enumerate(grid):
        for j in range(SASH_N):
            p = row[j].co
            if abs(p.z - zc) < BRIDGE_DZ:
                ax = Vector((0.0, 0.0, p.z))
                d = Vector((p.x, p.y, 0.0)).normalized()
                loc = outer(CLOTH, ax, d)[0]
                if loc is not None:
                    need[i][j] = max(0.0, (loc - ax).length + SASH_GAP + 0.001 - Vector((p.x, p.y, 0.0)).length) * (
                        1 - smoothstep(abs(p.z - zc), BRIDGE_DZ * 0.55, BRIDGE_DZ))
    for _ in range(BRIDGE_SPREAD):
        need = [[max([need[i][j]] + [need[a][b] - BRIDGE_SLOPE for a, b in
                                     ((i - 1, j), (i + 1, j), (i, j - 1), (i, (j + 1) % SASH_N)) if 0 <= a < rows])
                 for j in range(SASH_N)] for i in range(rows)]
    raw = [r[:] for r in need]
    for _ in range(BRIDGE_SMOOTH):  # no steps in the lift: its mean over the neighbours, never below what is needed
        need = [[max(raw[i][j], sum(need[a][b] for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, (j + 1) % SASH_N))
                                    if 0 <= a < rows) / (4 - (i in (0, rows - 1))))
                 for j in range(SASH_N)] for i in range(rows)]
    lifted = 0
    for i, row in enumerate(grid):
        for j in range(SASH_N):
            v = row[j]
            r = Vector((v.co.x, v.co.y, 0.0))
            if need[i][j] > 1e-5:
                v.co = v.co + r.normalized() * need[i][j]
                lifted += 1
    print('sash: %d vertices lifted over the belt' % lifted)
    relax(SASH_SETTLE)  # the lifted part folds nowhere
    # on top of his right shoulder by the collar, under the epaulette's strap, the band lies on the shoulder itself (the
    # tightened cloth bridges the hollow between the neck and the shoulder there): pulled onto it and evened, by turns
    raw = bvh_of([uni])
    x0, x1, z0, held_gap = SASH_HELD
    held = [(v, (1 - smoothstep(-v.co.x, x0, x1)) * smoothstep(v.co.z, z0, z0 + 0.02))
            for row in grid for v in row[:-1] if v.co.x < 0]
    held = [(v, w) for v, w in held if w > 0]
    nbs = {}
    for i, row in enumerate(grid):
        for j in range(SASH_N):
            nbs[row[j]] = [row[j - 1], row[(j + 1) % SASH_N]] + ([grid[i - 1][j]] if i else []) + (
                [grid[i + 1][j]] if i < rows - 1 else [])
    for _ in range(30):  # (12: a crease where the hold fades out)
        for v, w in held:
            loc, nrm, _, _ = raw.find_nearest(v.co, 0.08)
            gap_ = SASH_GAP + (held_gap - SASH_GAP) * w
            if loc is not None and (v.co - loc).dot(nrm) > gap_:
                v.co = v.co.lerp(loc + nrm * gap_, w)
        new = {v: v.co.lerp(sum((n.co for n in nbs[v]), Vector()) / len(nbs[v]), 0.5 * w) for v, w in held}
        for v, co in new.items():
            v.co = co
        for v, w in held:  # nothing of the cloth through it
            loc, nrm, _, _ = raw.find_nearest(v.co, 0.08)
            gap_ = SASH_GAP + (held_gap - SASH_GAP) * w
            if loc is not None and (v.co - loc).dot(nrm) < gap_:
                v.co = loc + nrm * gap_
    print('sash: %d vertices held on the shoulder' % len(held))
    # its edges for the cords that go in under it and the pencil by it: the last row lies towards his right and down
    # (sides[] point that way) - the lower edge
    SASH_EDGES.update(upper=[v.co.copy() for v in grid[0][:-1]], lower=[v.co.copy() for v in grid[-1][:-1]],
                      mid=[v.co.copy() for v in grid[midr][:-1]])
    seam = {}
    for i, (r0, r1) in enumerate(zip(grid, grid[1:])):
        for j in range(SASH_N):
            f = bm.faces.new((r0[j], r0[j + 1], r1[j + 1], r1[j]))
            seam[f] = (i, j)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f, (i, j) in seam.items():  # the closing column gets u = 1, not 0
        for l, (di, dj) in zip(f.loops, ((0, 0), (0, 1), (1, 1), (1, 0))):
            l[uvl].uv = uv_in('sash', (j + dj) / SASH_N, (i + di) / (rows - 1))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    f = bm.faces[0]
    if f.normal.dot(f.calc_center_median() - c) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return new_part('Sash', bm, None, lambda v: TORSO_W.at(v.co), SASH_THICK)


# ---------------------------------------------------------------- the portrait's view
YAW = float(sc.get('pose', {}).get('YAW_DEG', 0.0))
_shown = [(o.matrix_world @ v.co).z for o in sc.objects if o.type == 'MESH' and not o.hide_render
          for v in o.data.vertices]
HEIGHT = max(_shown) - min(_shown)


def ref_ray(px, py):
    """The line of sight through pixel (px, py) of the portrait in model space (as render_leader.py's 'ref' frames
    it): a point in front of the figure, the direction."""
    k = HEIGHT / (REF_SOLES - REF_CROWN)
    a = math.radians(YAW)
    right, d = Vector((math.cos(a), -math.sin(a), 0.0)), Vector((math.sin(a), math.cos(a), 0.0))
    return right * ((px - (REF_W - REF_X)) * k) + Vector((0.0, 0.0, (REF_SOLES - py) * k)) - d, d


def ref_hit(bvh, px, py):
    """Where the portrait's pixel lies on bvh's surface: point, normal (None, None if it misses)."""
    o, d = ref_ray(px, py)
    return bvh.ray_cast(o, d, 2.0)[:2]


# ---------------------------------------------------------------- aiguillettes
SASH_EDGES = {}  # build_sash(): its 'lower' and 'upper' edges and its 'mid' line, round the torso


def sash_in(p, edge='lower'):
    """How far p lies in under the sash from its edge (m across the band; negative outside it)."""
    E, M = SASH_EDGES[edge], SASH_EDGES['mid']
    j = min(range(len(E)), key=lambda i: (E[i] - p).length_squared)
    best = None
    for a in (j - 1, j):
        q0, q1 = E[a % len(E)], E[(a + 1) % len(E)]
        t = max(0.0, min(1.0, (p - q0).dot(q1 - q0) / max((q1 - q0).length_squared, 1e-12)))
        q = q0 + (q1 - q0) * t
        if best is None or (p - q).length < (p - best[0]).length:
            best = (q, M[a % len(M)] - E[a % len(E)])
    q, inward = best
    return (p - q).dot(inward.normalized())


def stack_lift(path, below, frames):
    """Extra lift along the cloth's normal per point of a cord so it lies over the cords laid before it ('below':
    (points, radius) of each) where they cross: at least AIG_STACK off them; ramped along the cord to the crossing.
    frames: (normal, radius) per point."""
    pts = [(q, r) for qs, r in below for q in qs]
    if not pts:
        return [0.0] * len(path)
    kd = KDTree(len(pts))
    for i, (q, _) in enumerate(pts):
        kd.insert(q, i)
    kd.balance()
    need = []
    for p, (n, r) in zip(path, frames):
        t_need = 0.0
        if sash_in(p) > 0:  # under the band they are pressed flat (lifted there, one came out at its edge in a hook)
            need.append(0.0)
            continue
        for q, i, d in kd.find_range(p, 4 * AIG_R):
            D = r + pts[i][1] + AIG_STACK
            w = p - q
            b = w.dot(n)
            disc = b * b - w.length_squared + D * D
            if disc > 0:
                t_need = max(t_need, -b + math.sqrt(disc))
        need.append(min(t_need, 2 * AIG_R + AIG_STACK))  # over one cord at most
    ramp = int(0.03 / AIG_STEP)  # rises over ~3 cm to the crossing
    out = list(need)
    for i, x in enumerate(need):
        for k in range(1, ramp + 1):
            f = x * (1 - (k / (ramp + 1)) ** 2)
            if i - k >= 0:
                out[i - k] = max(out[i - k], f)
            if i + k < len(out):
                out[i + k] = max(out[i + k], f)
    return out


def build_loops(under):
    """The cords of AIG_REF on the cloth 'under' (tightened: they lie over its folds): each cast from the portrait
    onto it (begun AIG_UP px higher, in under the field), the sash cords carried on along their last direction to AIG_UNDER
    in under the sash (SASH_EDGES of the band laid without them) - or cut there - and thinned under it; lifted off the
    cloth by their radius, straightened (a thick cord bridges the cloth's folds), laid over the ones before where
    they cross."""
    bm = bmesh.new()
    uvs = {}
    laid = []
    # one smooth layer for all of them to lie on: the cloth's depth along the line of sight over the cords' part of the
    # portrait, the nearest within AIG_BRIDGE taken and blurred - it bridges the crease where the sleeve meets the
    # chest (cast onto the cloth itself, cords side by side in the portrait lay a few cm apart in depth there, one on
    # the sleeve and one on the chest, and seen from the side they crossed in a knot)
    xs, ys = np.arange(AIG_AREA[0], AIG_AREA[2], 2.0), np.arange(AIG_AREA[1], AIG_AREA[3], 2.0)
    depth = np.full((len(ys), len(xs)), np.nan)
    for i, py in enumerate(ys):
        for j, px in enumerate(xs):
            o, d = ref_ray(px, py)
            hit = under.ray_cast(o, d, 2.0)[0]
            if hit is not None:
                depth[i, j] = (hit - o).dot(d)
    far = np.nanmax(depth)
    dep = np.where(np.isnan(depth), far, depth)
    r = AIG_BRIDGE // 2
    near = dep.copy()
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            if di * di + dj * dj <= r * r:
                near = np.minimum(near, np.roll(np.roll(dep, di, 0), dj, 1))
    for _ in range(AIG_BRIDGE):
        near = (near + np.roll(near, 1, 0) + np.roll(near, -1, 0) + np.roll(near, 1, 1) + np.roll(near, -1, 1)) / 5
    near = np.minimum(near, dep)  # never behind the cloth

    def layer_hit(px, py):
        fx, fy = (px - xs[0]) / 2.0, (py - ys[0]) / 2.0
        j0, i0 = int(min(max(fx, 0), len(xs) - 2)), int(min(max(fy, 0), len(ys) - 2))
        tx, ty = min(max(fx - j0, 0.0), 1.0), min(max(fy - i0, 0.0), 1.0)
        t = (near[i0, j0] * (1 - tx) * (1 - ty) + near[i0, j0 + 1] * tx * (1 - ty) + near[i0 + 1, j0] * (1 - tx) * ty
             + near[i0 + 1, j0 + 1] * tx * ty)
        if t >= far - 1e-6:
            return None
        o, d = ref_ray(px, py)
        return o + d * t
    for k, (ref, into) in enumerate(zip(AIG_REF, AIG_INTO_SASH)):
        ref = ([(ref[0][0] - AIG_UP_X, ref[0][1] - AIG_UP)] + list(ref)
               + ([] if into else [(ref[-1][0] - AIG_UP_X, ref[-1][1] - AIG_UP)]))
        ctrl = [h for h in (layer_hit(px, py) for px, py in ref) if h is not None]
        pts = catmull(ctrl, AIG_STEP)
        if into:
            cut = next((i for i, p in enumerate(pts) if sash_in(p) >= AIG_UNDER), None)
            if cut is not None:
                pts = pts[:cut + 1]
            else:
                for _ in range(80):
                    d = (pts[-1] - pts[-3]).normalized()
                    loc = under.find_nearest(pts[-1] + d * AIG_STEP, 0.05)[0]
                    if loc is None:
                        break
                    pts.append(loc)
                    if sash_in(loc) >= AIG_UNDER:
                        break
        n = len(pts)
        thin = [1.0 - (1.0 - AIG_THIN[2]) * smoothstep(sash_in(p), *AIG_THIN[:2]) if into else 1.0 for p in pts]
        nrm = []
        for p in pts:
            nn = under.find_nearest(p, 0.05)[1]
            nrm.append(nn if nn is not None else Vector((0, -1, 0)))
        base = [AIG_R * t + AIG_GAP for t in thin]
        extra = stack_lift(pts, laid, [(nn, AIG_R * t) for nn, t in zip(nrm, thin)])
        lift = [b + e for b, e in zip(base, extra)]
        # under the band it sinks to the cloth (left at its height, the band's edge cut it and its end crumpled there)
        lift = [l if not into else l * (1 - smoothstep(sash_in(p), -0.004, 0.012)) + AIG_R * t * 0.3 * smoothstep(
            sash_in(p), -0.004, 0.012) for l, p, t in zip(lift, pts, thin)]
        # off the cloth towards the viewer, and stiff: its depth along the line of sight evened out over the cloth's
        # folds, never into it - the portrait's picture of the cord kept exactly (lifted along the cloth's normal and
        # smoothed in 3-D, the cords moved sideways where the sleeve meets the chest and twisted round each other)
        view = ref_ray(0, 0)[1]
        toward = lambda nn: 1.0 / max(-view.dot(nn), 0.3)  # noqa: E731
        path = [p - view * (l * toward(nn)) for p, nn, l in zip(pts, nrm, lift)]
        for _ in range(AIG_STIFF):
            path = [path[0]] + [path[j] + view * (((path[j - 1] + path[j + 1]).dot(view) / 2 - path[j].dot(view)) * 0.5)
                                for j in range(1, n - 1)] + [path[-1]]
            for j in range(1, n - 1):
                loc, nn, _, _ = under.find_nearest(path[j], 0.05)
                if loc is not None:
                    short = lift[j] - (path[j] - loc).dot(nn)
                    if short > 0:
                        path[j] = path[j] - view * (short * toward(nn))
        laid.append((path, AIG_R))
        _, u = tube(bm, path, AIG_R, 12, 'cord', cap=not into, taper=lambda t, th=thin: th[round(t * (len(th) - 1))],
                    relief=braid_relief, u0=0.13 * k, cap0=True)
        uvs.update(u)
        print('aiguillette %d: %d points, %.2f m, %s, lifted over the others up to %.4f' % (
            k, n, sum((b - a).length for a, b in zip(path, path[1:])),
            'in under the sash %.3f' % sash_in(pts[-1]) if into else 'a loop', max(extra)))
    return new_part('Aiguillettes', bm, lambda v: uvs[v], lambda v: TORSO_W.at(v.co))


def press_under(ob, cloth, sash):
    """Vertices of ob under the sash that came out through it (a cord passes between the band's vertices) pressed in
    under its inner side, along the cloth's normal."""
    moved = 0
    for v in ob.data.vertices:
        p = v.co.copy()
        loc, nn, _, _ = cloth.find_nearest(p, 0.06)
        if loc is None:
            continue
        hit = sash.ray_cast(loc + nn * 0.0003, nn, 0.06)[0]
        if hit is None:
            continue
        t = (hit - loc).dot(nn)
        h = (p - loc).dot(nn)
        if h > t - 0.0008:
            v.co = p - nn * (h - max(t - 0.0008, 0.0003))
            moved += 1
    ob.data.update()
    print('%s: %d vertices pressed in under the sash' % (ob.name, moved))


def build_pencil(coat, over):
    """The pencil hanging from its crook, as in the portrait: the crook hooked on the tunic's button by the sash's
    upper edge (the one nearest PENCIL_KNOB: a knob of its own beside the buttons read as a stray extra button), its
    neck arching from the button's dome over to the pencil's top (PENCIL_TOP); the pencil hanging straight down from
    there over the band, resting on it where it would touch (its outline lifted off the surface by its own radius: the
    line over all of it that comes nearest)."""
    k_ref = ref_hit(coat, *PENCIL_KNOB)[0]
    btn = O['Buttons']
    pts = [btn.matrix_world @ v.co for v in btn.data.vertices]
    near = min(pts, key=lambda p: (p - k_ref).length_squared)
    piece = [p for p in pts if (p - near).length < 0.02]  # that button (they are ~7 cm apart)
    centre = sum(piece, Vector()) / len(piece)
    nn = coat.find_nearest(centre, 0.05)[1]
    knob = centre + nn * (max((p - centre).dot(nn) for p in piece) * 0.6)  # the neck comes out of the dome's middle
    a = ref_hit(over, *PENCIL_TOP)[0]

    def on_over(q, lift):
        loc, nn, _, _ = over.find_nearest(q, 0.06)
        return loc + nn * lift if loc is not None else q
    n0 = over.find_nearest(a, 0.05)[1]
    d0 = (Vector((0, 0, -1)) - n0 * -n0.z).normalized()
    sh = []
    for k in range(41):
        t = k / 40
        q = on_over(a + d0 * (t * PENCIL_L), pencil_r(t) + AIG_GAP)
        sh.append(((q - a).dot(d0), (q - a).dot(n0)))
    best = None
    for i in range(len(sh)):
        for j2 in range(i + 1, len(sh)):
            (si, hi), (sj, hj) = sh[i], sh[j2]
            if sj - si < 1e-6:
                continue
            beta = (hj - hi) / (sj - si); alpha = hi - beta * si
            if all(alpha + beta * sk >= hk - 1e-6 for sk, hk in sh):
                cost = sum(alpha + beta * sk - hk for sk, hk in sh)
                if best is None or cost < best[0]:
                    best = (cost, alpha, beta)
    _, alpha, beta = best
    top = a + n0 * alpha
    axis = (d0 + n0 * beta).normalized()
    bm = bmesh.new(); uvs = {}
    pencil(bm, uvs, top, axis, PENCIL_L)
    # the crook: from the button, its neck arching up and over into the pencil's cup
    b2 = bmesh.new()
    up = Vector((0, 0, 1))
    # the portrait's is short and thick, going down from the button straight into the top's side (arched 1.3 cm up
    # and coming down into the top from 1.6 cm over it, it looked half again as long)
    P0, P3 = knob, top + axis * 0.004
    P1, P2 = P0 + (P3 - P0) * 0.35 + up * 0.003, P3 - axis * 0.006 - (P3 - P0) * 0.15
    path = []
    for k in range(25):
        t = k / 24
        q = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3
        loc, nn, _, _ = over.find_nearest(q, 0.05)
        if 0 < k < 24 and loc is not None and (q - loc).dot(nn) < CROOK_R + AIG_GAP:
            q = loc + nn * (CROOK_R + AIG_GAP)
        path.append(q)
    tube(b2, path, CROOK_R, 10, 'gold', cap=False)
    me = bpy.data.meshes.new('tmp'); b2.to_mesh(me); b2.free()
    before = set(bm.verts)
    bm.from_mesh(me); bpy.data.meshes.remove(me)
    lay = bm.loops.layers.uv.get('UVMap')
    gu = uv_in('gold', 0.5, 0.5)
    for f in bm.faces:
        if any(v not in before for v in f.verts):
            for l in f.loops:
                l[lay].uv = gu
    pencils = new_part('AiguilletteTips', bm, None, lambda v: TORSO_W.at(v.co))
    print('pencil: top %.4f off the sash, leaning out %.1f deg; hooked on the button at %s, %.3f from the top' % (
        alpha, math.degrees(math.atan(beta)), tuple(round(v, 3) for v in centre), (knob - top).length))
    return pencils


def pencil_r(t):
    """The pencil's radius at t along it (PENCIL_PROFILE)."""
    for (t0, r0, *_), (t1, r1, *_) in zip(PENCIL_PROFILE, PENCIL_PROFILE[1:]):
        if t0 <= t <= t1:
            return (r0 + (r1 - r0) * (t - t0) / max(t1 - t0, 1e-9)) * PENCIL_K
    return 0.0


def pencil(bm, uvs, top, axis, length, sides=20):
    """The aiguillette's pencil as a turned piece along axis from top: PENCIL_PROFILE's radii, the fluted stretches
    with PENCIL_FLUTES grooves round them; one closed surface, chased all over (loop UVs in bm's 'UVMap': round it
    along u, along it along v of the 'chased' region)."""
    prof = []
    for t_, r_, *f_ in PENCIL_PROFILE:  # resample: the flutes need rings between the knots
        prof.append((t_, r_ * PENCIL_K, *f_))
    rows = []
    for (t0, r0, *f0), (t1, r1, *f1) in zip(prof, prof[1:]):
        n = max(1, int((t1 - t0) * length / 0.004))
        for j in range(n):
            s_ = j / n
            rows.append((t0 + (t1 - t0) * s_, r0 + (r1 - r0) * s_, bool(f0 and f1)))
    rows.append((prof[-1][0], prof[-1][1], False))
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(ref).normalized(); w = axis.cross(u)
    rings = []
    for t, r, fl in rows:
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            rr = r - (PENCIL_FLUTE_D * (0.5 + 0.5 * math.cos(ang * PENCIL_FLUTES)) if fl else 0.0)
            v = bm.verts.new(top + axis * (t * length) + (u * math.cos(ang) + w * math.sin(ang)) * max(rr, 0.0))
            ring.append(v)
        rings.append(ring)
    lay = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    for i, (r0, r1) in enumerate(zip(rings, rings[1:])):
        for k in range(sides):
            f = bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
            for l, (a, b) in zip(f.loops, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                l[lay].uv = uv_in('chased', a / sides, rows[b][0])
    bmesh.ops.remove_doubles(bm, verts=rings[0] + rings[-1], dist=1e-6)  # the two ends close in a point


# ---------------------------------------------------------------- epaulettes
EP_ARM_SHARE = 0.3                # of the upper arm's weight under it the epaulette keeps: it lies on the shoulder


def on_shoulder(ws, side):
    """The cloth's weights for something lying on the shoulder top: most of what the upper arm moves goes to the
    clavicle (raising the arm would tip the whole epaulette up with the sleeve)."""
    ws = dict(ws)
    arm = ws.pop('upperarm_' + side, 0.0)
    ws['upperarm_' + side] = arm * EP_ARM_SHARE
    ws['clavicle_' + side] = ws.get('clavicle_' + side, 0.0) + arm * (1 - EP_ARM_SHARE)
    return {k: v for k, v in ws.items() if v > 0}


def build_epaulette(side):
    """The field: a rigid gilt plate on top of the shoulder - centred on it front to back, its outer end EP_OVER past
    the shoulder's end, tilted out (EP_TILT), its underside flat, lifted till nothing of
    the cloth (and sash, collar) under it is nearer than EP_GAP (it rests on the shoulder's highest points, standing
    off the rest as a plate does). Laid on the cloth's heights it followed every fold and came out soft and crooked.
    The strap from under it to the collar on the cloth; the fringe round its outer three quarters."""
    sign = 1 if side == 'l' else -1
    cb, ub = rig.data.bones['clavicle_' + side], rig.data.bones['upperarm_' + side]
    out = cb.tail_local - cb.head_local
    out = Vector((out.x, out.y, 0)).normalized()
    fwd = Vector((out.y, -out.x, 0))
    fwd = fwd if fwd.y < 0 else -fwd
    joint = ub.head_local.copy()

    def top_at(p):  # the cloth's top over p (x, y)
        return FIELD_CLOTH.ray_cast(Vector((p.x, p.y, 2.3)), Vector((0, 0, -1)), 1.0)[0]

    def outermost(o, d):
        return FIELD_CLOTH.ray_cast(o + d * 0.4, -d, 0.4)[0]
    # along the shoulder's line (its middle front to back, a little under its top) to where the portrait's field
    # middle shows: bisection on the distance out from the joint
    def on_line(d):
        q = joint + out * d
        t = top_at(q)
        zt = t.z if t is not None else joint.z + 0.05
        q = Vector((q.x, q.y, zt - 0.03))
        f_, b_ = outermost(q, fwd), outermost(q, -fwd)
        return q + fwd * (((f_ + b_) / 2 - q).dot(fwd)) if f_ is not None and b_ is not None else q
    # the field's middle where the portrait shows it across the picture: bisection on the distance out from the joint
    k = HEIGHT / (REF_SOLES - REF_CROWN)
    right = Vector((math.cos(math.radians(YAW)), -math.sin(math.radians(YAW)), 0.0))
    px = lambda q: (REF_W - REF_X) + q.dot(right) / k  # noqa: E731
    lo_, hi_ = -0.06, 0.10
    for _ in range(30):
        mid = (lo_ + hi_) / 2
        if (px(on_line(mid)) - EP_REF_X[side]) * sign > 0:
            hi_ = mid
        else:
            lo_ = mid
    c = on_line((lo_ + hi_) / 2)
    e = outermost(Vector((c.x, c.y, c.z)), out)
    print('epaulette %s: middle %.3f out from the shoulder joint, the shoulder ends %.3f out' % (
        side, (c - joint).dot(out), (e - joint).dot(out) if e is not None else float('nan')))
    turn = Matrix.Rotation(-sign * math.radians(EP_TURN[side]), 3, 'Z')  # towards the front (the viewer)
    out_f = turn @ out
    Z = Vector((0, 0, 1)) + out_f * math.tan(math.radians(EP_TILT[side]))
    to_cam = Vector((-math.sin(math.radians(YAW)), -math.cos(math.radians(YAW)), 0.0))
    Z += to_cam * math.tan(math.radians(EP_TO_VIEWER))
    Z.normalize()
    X = (out_f - Z * out_f.dot(Z)).normalized()
    Y = Z.cross(X)
    XS = (out - Z * out.dot(Z)).normalized()  # the strap runs along the shoulder to the collar, however the field is
    YS = Z.cross(XS)                          # turned
    C = top_at(c) or c
    L = lambda x, y, z: C + X * x + Y * y + Z * z  # noqa: E731
    LS = lambda x, y, z: C + XS * x + YS * y + Z * z  # noqa: E731
    rings, segs = 6, 48

    def cloth_h(x, y):
        hit = FIELD_CLOTH.ray_cast(L(x, y, 0.2), -Z, 0.5)[0]
        return (hit - C).dot(Z) if hit is not None else -1.0
    # the lift: by its edge and rim the plate clears the cloth by EP_GAP; inside, the padded field presses the cloth
    # down - nothing of it may come up through the field's face (cleared everywhere, the field stood 3-4 cm over the
    # round of the shoulder)
    h0 = -1.0
    for i in range(0, 10):
        f = i / 8  # to 1.125: the rim's outside
        for k in range(segs):
            a = 2 * math.pi * k / segs
            x, y = EP_R * f * math.cos(a), EP_R * f * math.sin(a)
            if f >= 0.85:  # (the inner half of the rim, towards the neck, presses into the padded cloth)
                need = (EP_GAP if f <= 1.0 else EP_RIM_R - EP_THICK * 0.5 + EP_GAP) - EP_PRESS[math.cos(a) < 0]
            else:
                need = 0.003 - EP_THICK - EP_DOME * (1 - f * f)
            hh = cloth_h(x, y) + need
            if hh > h0:
                h0, worst = hh, (round(f, 2), round(math.degrees(a)), tuple(round(v, 3) for v in L(x, y, 0)))
    if DEBUG_FRINGE:
        for a_ in (0, 90, 180, 270):
            print('  ep %s a %d: ' % (side, a_) + ' '.join(
                '%.2f:%.3f' % (f_, cloth_h(EP_R * f_ * math.cos(math.radians(a_)), EP_R * f_ * math.sin(math.radians(a_))))
                for f_ in (0.0, 0.25, 0.5, 0.75, 1.0, 1.12)))
    h0 += EP_PAD[side]
    U = lambda x, y: h0  # noqa: E731  the plate's underside (flat)
    print('epaulette %s: centre %s, normal %s (%.0f deg), plate %.3f over the shoulder top (held up at %s)' % (
        side, tuple(round(v, 3) for v in C), tuple(round(v, 2) for v in Z), math.degrees(Z.angle(Vector((0, 0, 1)))),
        h0, worst))
    ws = on_shoulder(UNI_W.at(C), side)
    bm = bmesh.new(); uvs = {}
    topv = bm.verts.new(L(0, 0, U(0, 0) + EP_THICK + EP_DOME)); uvs[topv] = uv_in('pole', 0.5, 0.5)
    grid = []
    for i in range(1, rings + 1):
        f = i / rings
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            x, y = EP_R * f * math.cos(a), EP_R * f * math.sin(a)
            v = bm.verts.new(L(x, y, U(x, y) + EP_THICK + EP_DOME * (1 - f * f)))
            uvs[v] = uv_in('pole', 0.5 + 0.5 * f * math.cos(a), 0.5 + 0.5 * f * math.sin(a))
            ring.append(v)
        grid.append(ring)
    for k in range(segs):
        bm.faces.new((topv, grid[0][k], grid[0][(k + 1) % segs]))
    for r0, r1 in zip(grid, grid[1:]):
        for k in range(segs):
            bm.faces.new((r0[k], r1[k], r1[(k + 1) % segs], r0[(k + 1) % segs]))
    bot = []
    for k, v in enumerate(grid[-1]):
        a = 2 * math.pi * k / segs
        x, y = EP_R * math.cos(a), EP_R * math.sin(a)
        b = bm.verts.new(L(x, y, U(x, y))); uvs[b] = uv_in('gold', 0.5, 0.5); bot.append(b)
    for k in range(segs):
        bm.faces.new((grid[-1][k], bot[k], bot[(k + 1) % segs], grid[-1][(k + 1) % segs]))
    botc = bm.verts.new(L(0, 0, U(0, 0))); uvs[botc] = uv_in('gold', 0.5, 0.5)
    for k in range(segs):
        bm.faces.new((bot[(k + 1) % segs], bot[k], botc))
    # the twisted rim round the field's edge
    rim = []
    for k in range(97):
        a = 2 * math.pi * k / 96
        x, y = EP_R * math.cos(a), EP_R * math.sin(a)
        rim.append(L(x, y, U(x, y) + EP_THICK * 0.5))
    _, u = tube(bm, rim, EP_RIM_R, 12, 'bullion', uv_len=BULLION_UV_LEN * 3, cap=False); uvs.update(u)
    # strap to the collar, from under the field: a padded galloon tongue, flat across, its end by the collar rounded,
    # red piping round its sides and end, a button by the end, bound in gold cord where it comes out from under the
    # rim (as the portrait's); along its length it lies on the cloth (and the sash) under it, evened - a stiff board
    # over their highest points stood off the shoulder at its end, over the sash's edge
    x_end = sign * STRAP_X - C.x
    strap_len = abs(x_end / XS.x) if abs(XS.x) > 1e-3 else 0.1

    def over_collar(x):  # the collar stands higher than the cloth there
        p0 = LS(x, 0.0, 0.0) + Z * 0.15
        a_, b_ = FIELD_CLOTH.ray_cast(p0, -Z, 0.4)[0], STRAP_CLOTH.ray_cast(p0, -Z, 0.4)[0]
        return a_ is not None and (b_ is None or (a_ - b_).dot(Z) > 0.002)
    for _ in range(40):  # the strap ends STRAP_SHORT before the collar's foot (run up onto it, it bridged the hollow
        if not over_collar(-strap_len - STRAP_SHORT):  # before it, 1 cm off the shoulder)
            break
        strap_len -= 0.002
    s0 = EP_R * 0.6
    hw0 = STRAP_W / 2
    hw = lambda d: hw0 * (1 - 0.15 * (d - s0) / (strap_len - s0))  # noqa: E731  (narrowing a little to the collar)
    re = hw(strap_len) * STRAP_END                                 # the rounded end's radius
    ds = [s0 + (strap_len - re - s0) * i / 20 for i in range(21)]   # along it, then round the end
    ends = [(strap_len - re + re * math.sin(math.radians(a_)), math.cos(math.radians(a_))) for a_ in (20, 40, 60, 75, 88)]
    # each row laid on what is under it, across as well (flat across and tilted with the field, it stood 2 mm off the
    # shoulder at one edge and 7 at the other): its height and its slope across, fitted to the cloth there - on the
    # sash where it is under most of the strap's width, else on the tunic (over the band's edge, which crosses under its
    # end, it stood 1 cm off the tunic beyond it)
    a_raw, k_raw = [], []
    for d in ds:
        hh, hu = [], []
        for y in np.linspace(-hw(d), hw(d), 7):
            hit = STRAP_CLOTH.ray_cast(LS(-d, y, 0.0) + Z * 0.15, -Z, 0.4)[0]
            bare = STRAP_UNI.ray_cast(LS(-d, y, 0.0) + Z * 0.15, -Z, 0.4)[0]
            if hit is not None and bare is not None:
                hh.append((y, (hit - C).dot(Z))); hu.append((y, (bare - C).dot(Z)))
        if not hh:
            a_raw.append(a_raw[-1] if a_raw else 0.0); k_raw.append(k_raw[-1] if k_raw else 0.0)
            continue
        on_sash = sum(a_[1] - b_[1] > 0.003 for a_, b_ in zip(hh, hu))
        pts = np.array(hh if on_sash * 2 > len(hh) else hu)
        k_ = float(np.polyfit(pts[:, 0], pts[:, 1], 1)[0]) if len(pts) > 2 else 0.0
        k_raw.append(k_); a_raw.append(float((pts[:, 1] - k_ * pts[:, 0]).max()))
        if DEBUG_FRINGE:
            print('  strap %s d %.3f on sash %d/%d: %s | %s' % (side, d, on_sash, len(hh), ' '.join('%.1f' % (1000 * h) for _, h in hh), ' '.join('%.1f' % (1000 * h) for _, h in hu)))
    a_raw, k_raw = np.array(a_raw), np.array(k_raw)
    line, slope = a_raw.copy(), k_raw.copy()
    for _ in range(4):  # even along it, never into what is under it
        line[1:-1] = (line[:-2] + line[1:-1] * 2 + line[2:]) / 4
        slope[1:-1] = (slope[:-2] + slope[1:-1] * 2 + slope[2:]) / 4
    line = np.maximum(line, a_raw)
    surf = lambda d, y: float(np.interp(d, ds, line)) + float(np.interp(d, ds, slope)) * y + STRAP_GAP  # noqa: E731
    print('strap %s: %.3f long, lifted over the cloth by evening it 0..%.1f mm, slope across %.2f..%.2f' % (
        side, strap_len, 1000 * float((line - a_raw).max()), float(slope.min()), float(slope.max())))
    cols = np.linspace(-1.0, 1.0, 7)
    rows_ = [(d, hw(d)) for d in ds] + [(d, (hw(strap_len) - re) + re * c) for d, c in ends]  # (along, half-width)

    def top_h(c):  # padded: a little rounded across
        return STRAP_T * (0.7 + 0.3 * (1 - c * c))
    tops, bots = [], []
    for d, w in rows_:
        tr, br = [], []
        for c in cols:
            p = LS(-d, w * c, surf(d, w * c))
            b = bm.verts.new(p); t = bm.verts.new(p + Z * top_h(c))
            uvs[b] = uvs[t] = uv_in('strap', 0.5 * d / strap_len, 0.40 + 0.03 * c)  # a plain gold band of the galloon
            br.append(b); tr.append(t)
        tops.append(tr); bots.append(br)
    m = len(cols)
    for r0, r1 in zip(tops, tops[1:]):
        for k in range(m - 1):
            bm.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
    for r0, r1 in zip(bots, bots[1:]):
        for k in range(m - 1):
            bm.faces.new((r1[k], r1[k + 1], r0[k + 1], r0[k]))
    for r0, r1, b0, b1 in zip(tops, tops[1:], bots, bots[1:]):  # the long sides
        bm.faces.new((b0[0], b1[0], r1[0], r0[0]))
        bm.faces.new((r0[-1], r1[-1], b1[-1], b0[-1]))
    for k in range(m - 1):  # across its rounded end, and under the field
        bm.faces.new((tops[-1][k], tops[-1][k + 1], bots[-1][k + 1], bots[-1][k]))
        bm.faces.new((bots[0][k], bots[0][k + 1], tops[0][k + 1], tops[0][k]))
    # the piping: along one side from under the rim, round the end, back along the other
    side_pts = lambda c: [LS(-d, (w + STRAP_PIPING * 0.4) * c, surf(d, w * c) + STRAP_T * 0.5)  # noqa: E731
                          for d, w in rows_[:len(ds)] if d > EP_R * 0.8]
    def end_pt(c, a_):
        d = strap_len - re + (re + STRAP_PIPING * 0.4) * math.sin(math.radians(a_))
        y = (hw(strap_len) - re + (re + STRAP_PIPING * 0.4) * math.cos(math.radians(a_))) * c
        return LS(-d, y, surf(d, y) + STRAP_T * 0.5)
    tip = [end_pt(c, a_) for c, aa in ((-1, range(0, 91, 15)), (1, range(90, -1, -15))) for a_ in aa]
    pipe = side_pts(-1) + tip + side_pts(1)[::-1]
    vs, u = tube(bm, catmull(pipe, 0.003), STRAP_PIPING, 8, 'strap', cap=True, cap0=True)
    for v in vs:
        u[v] = uv_in('strap', 0.5, 0.04)  # the galloon picture's red border
    uvs.update(u)
    # the binding: closed turns of cord round it just outside the rim
    for k in range(STRAP_WRAPS):
        d = EP_R + EP_RIM_R * 0.8 + STRAP_WRAP_R * (1 + 2.1 * k)
        w, h = hw(d) + STRAP_PIPING + STRAP_WRAP_R * 0.6, STRAP_T * 0.5 + STRAP_WRAP_R * 0.8
        h_low = STRAP_T * 0.5 + STRAP_GAP - STRAP_WRAP_R - 0.0005  # under it flat on the cloth (round, it went in)
        loop = []
        for j in range(25):
            t_ = 2 * math.pi * j / 24
            ct, st = math.cos(t_), math.sin(t_)
            y = w * math.copysign(abs(ct) ** 0.4, ct)
            loop.append(LS(-d, y, surf(d, y) + STRAP_T * 0.5 + (h if st > 0 else h_low) * math.copysign(abs(st) ** 0.4, st)))
        _, u = tube(bm, loop, STRAP_WRAP_R, 8, 'cord', cap=False); uvs.update(u)
    btn_at = LS(-(strap_len - re), 0.0, surf(strap_len - re, 0.0) + top_h(0.0))
    b2 = bmesh.new()
    bmesh.ops.create_uvsphere(b2, u_segments=12, v_segments=6, radius=STRAP_BUTTON)
    bmesh.ops.delete(b2, geom=[v for v in b2.verts if v.co.z < -1e-4], context='VERTS')
    for v in b2.verts:
        v.co.z *= 0.6
    bmesh.ops.transform(b2, matrix=Matrix.Translation(btn_at) @ Z.to_track_quat('Z', 'Y').to_matrix().to_4x4(),
                        verts=b2.verts[:])
    me = bpy.data.meshes.new('tmp'); b2.to_mesh(me); b2.free()
    before = set(bm.verts)
    bm.from_mesh(me); bpy.data.meshes.remove(me)
    for v in set(bm.verts) - before:
        uvs[v] = uv_in('gold', 0.5, 0.5)
    field = new_part('Epaulette_' + side, bm, lambda v: uvs[v], lambda v: ws)
    # fringe: thick bullion strands side by side round the outer FRINGE_ARC of the rim (a second row behind, half a
    # step round, fills the gaps that open between them lower down) - a neat bell as in the portrait. Each strand
    # hangs from under the rim nearly straight down (FRINGE_TILT, smooth round the rim); where the shoulder, the arm,
    # the chest, the sash or the cords are in the way it is carried out over them (straight out from the field's
    # middle) and, past the widest of them, hangs on from there; how far out at each height is evened round the rim
    # (FRINGE_OUT_SPREAD a step), so the strands lie side by side like a skirt. (Bent over the body one by one, each
    # its own way, they came out a tangle of crooked sticks; kept straight, they had to stand out 45-70 deg to clear
    # the shoulder - a sunburst.)
    bm = bmesh.new(); uvs = {}; wmap = {}
    half = math.radians(FRINGE_ARC) / 2
    # the arc without fringe centred on the strap (the field may be turned off the strap's line): angles round the
    # rim are taken from a_off
    a_off = math.atan2(-(-XS).dot(Y), -(-XS).dot(X))
    down = Vector((0, 0, -1))
    ns = FRINGE_SAMPLES

    def base_tilt(a):  # FRINGE_TILT at the outer end, the front and back, the ends by the collar
        aa = abs(a)
        if aa < math.pi / 2:
            return FRINGE_TILT[1] + (FRINGE_TILT[0] - FRINGE_TILT[1]) * math.cos(aa) ** 2
        return FRINGE_TILT[1] + (FRINGE_TILT[2] - FRINGE_TILT[1]) * smoothstep(aa, math.pi / 2, half)

    def under(q):  # what is under q: (height over it, the point, its normal) - the cloth or the sash's top over it
        best = (1.0, None, None)
        loc, nrm, _, _ = FRINGE_CLOTH.find_nearest(q, 0.1)
        if loc is not None:
            best = ((q - loc).dot(nrm), loc, nrm)
        loc, nrm, _, _ = SASH_TOP.find_nearest(q, 0.1)
        if loc is not None:
            v = q - loc
            h = v.dot(nrm)
            if (v - nrm * h).length < 0.004 and h < best[0]:  # over the band, not beside it
                best = (h, loc, nrm)
        return best

    def gap(q):  # the strand's surface at q off what is under it
        return under(q)[0] - FRINGE_R - FRINGE_CLEAR

    def drape(pts, push):
        """The strand lying on what is under it where it would go into it (FRINGE_CLEAR off it): its points pushed
        out and evened along it by turns, its steps kept - one smooth bend (pushed out point by point, the strands
        over the cords came out kinked and crossing). Pushed out along its own push only (straight out from the field):
        along the normals of the cords under them, they were pushed aside across their neighbours."""
        step = (pts[1] - pts[0]).length

        def out_of(q):
            h, loc, nrm = under(q)
            g = h - FRINGE_R - FRINGE_CLEAR
            if loc is None or g >= 0:
                return q
            d = push if nrm.dot(push) > 0.6 else (push + nrm).normalized()  # (along the surface, the push flung
            return q - d * (g / max(nrm.dot(d), 0.6))                          # the end strands out in a hook)
        out = [p.copy() for p in pts]
        for _ in range(DRAPE_ROUNDS):
            out = [out[0]] + [out_of(q) for q in out[1:]]
            out = [out[0]] + [out[i].lerp((out[i - 1] + out[i + 1]) / 2, 0.5) for i in range(1, len(out) - 1)] + [out[-1]]
            for i in range(1, len(out)):  # its length kept
                out[i] = out[i - 1] + (out[i] - out[i - 1]).normalized() * step
        return [out[0]] + [out_of(out_of(q)) for q in out[1:]]  # and nowhere into what is under it

    def line(start, push, t, ln):
        """A strand's line from start, ns steps: out from under the rim FRINGE_START off the upright, turning down at
        an even rate over FRINGE_BEND of its length to its own tilt t, straight on from there - every strand bent
        alike, a rigid dome as in the portrait (straight from the rim, the bell was a cone, a lampshade)."""
        a0 = max(t, math.radians(FRINGE_START))
        pts, p, step = [start], start.copy(), ln / ns
        for j in range(ns):
            tt = a0 + (t - a0) * min((j + 0.5) * step / FRINGE_BEND, 1.0)
            p = p + (down * math.cos(tt) + push * math.sin(tt)).normalized() * step
            pts.append(p)
        return pts
    def course(a, rf, shorter):
        """The bell at angle a round the rim: root, flat radial, the strand's line before carrying out, how far out it
        must be at each point (None where it is buried)."""
        x, y = EP_R * rf * math.cos(a + a_off), EP_R * rf * math.sin(a + a_off)
        root = L(x, y, U(x, y) - 0.002 - FRINGE_R * 0.6)  # under the field, the rim over its top
        radial = X * math.cos(a + a_off) * EP_R + Y * math.sin(a + a_off) * EP_R  # square to the rim
        flat = Vector((radial.x, radial.y, 0.0)).normalized()
        h, loc, nrm = under(root)
        if loc is not None and h < FRINGE_R + 0.002:
            # its root in the cloth (the field's front and inner end are pressed onto the shoulder): out onto it -
            # unless it is deep in (by the collar and the sash: brought out that far, they hung loose over the chest)
            if h < -FRINGE_DEEP:
                return None
            root = loc + nrm * (FRINGE_R + 0.002)
        ends = 0.75 + 0.25 * smoothstep(half - abs(a), 0.0, 0.9)  # shorter towards the collar (as long, the last ones
                                                                  # hung down the chest over the cords on their own;
                                                                  # at 0.55 they were stubs bent over the cords' tops)
        length = FRINGE_LEN * shorter * ends
        # carried out away from what is under it: between straight out from the field and off the body there (by the
        # collar straight out ran along the shoulder into the neck and never cleared it)
        t0 = math.radians(base_tilt(a))
        mid = root + (down * math.cos(t0) + flat * math.sin(t0)) * (length / 2)
        _, _, nb = under(mid)
        push = flat
        if nb is not None and Vector((nb.x, nb.y, 0.0)).length > 0.2:
            push = (flat + Vector((nb.x, nb.y, 0.0)).normalized()).normalized()
        # straight and stiff, as the portrait's: a bell of rods. Tilted off the upright at least by its own
        # (FRINGE_TILT) and as far as it must to clear what is under it, up to FRINGE_TILT_MAX (FRINGE_ENDS_TILT at the
        # front and back); past that it lies on what is under it from where it reaches it (drape). Laid over the body
        # from the root, the bell hugged the arm - a narrow tube, not the portrait's wide fan
        def clear_len(t):
            for j, q in enumerate(line(root, push, t, length)):
                if length * j / ns > FRINGE_R * 1.5 and gap(q) < 0:
                    return length * (j - 1) / ns
            return length
        t_max = FRINGE_TILT_MAX + (FRINGE_ENDS_TILT - FRINGE_TILT_MAX) * smoothstep(abs(flat.y), 0.2, 0.6)
        t = t0
        while clear_len(t) < length and t < math.radians(t_max):
            t += math.radians(1.0)
        if DEBUG_FRINGE:
            print('  a %4.0f root h %.3f tilt %.0f -> %.0f, clear %.3f of %.3f' % (
                math.degrees(a), h, math.degrees(t0), math.degrees(t), clear_len(t), length))
        return dict(a=a, root=root, push=push, tilt=t, length=length)
    # the bell round the rim, finely; the tilt evened round it (each at least its neighbours' less FRINGE_TILT_SPREAD
    # a degree round the rim, then smoothed): a neat bell, no strand standing out from the next
    dense = [c for c in (course(-half + 2 * half * k / (FRINGE_DENSE - 1), 1.0, 1.0) for k in range(FRINGE_DENSE)) if c]
    tilts = [max(o['tilt'] - math.radians(FRINGE_TILT_SPREAD) * math.degrees(abs(o['a'] - c['a'])) for o in dense)
             for c in dense]
    for _ in range(FRINGE_SMOOTH):
        tilts = [max(tilts[j], (tilts[max(j - 1, 0)] + 2 * tilts[j] + tilts[min(j + 1, len(tilts) - 1)]) / 4)
                 for j in range(len(tilts))]
    for c, t in zip(dense, tilts):  # as long as it is, lying on what is under it where it reaches it
        c['tilt'] = t
        c['path'] = drape(line(c['root'], c['push'], t, c['length']), c['push'])
    # ... each evened with its neighbours round the rim, then out of what is under it again: the strands lying over
    # the cords one way and the next another came out crossing in a heap at the front
    for _ in range(FRINGE_SMOOTH):
        paths = [c['path'] for c in dense]
        for j, c in enumerate(dense):
            p0, p1 = paths[max(j - 1, 0)], paths[min(j + 1, len(paths) - 1)]
            c['path'] = [c['path'][0]] + [(a_ + b_ + q * 2) / 4 for a_, b_, q in zip(p0[1:], p1[1:], c['path'][1:])]
    for c in dense:
        c['path'] = drape(c['path'], c['push'])
        c['tip'] = c['path'][-1]
    # strands side by side along the bell's lower edge, touching there (spaced along the rim, they stood apart below
    # with the cloth between them); their roots crowd under the rim
    run = [0.0]
    for c0, c1 in zip(dense, dense[1:]):
        run.append(run[-1] + ((c1['tip'] - c0['tip']).length if abs(c1['a'] - c0['a']) < 0.2 else FRINGE_R * 2))
    count = max(2, int(run[-1] / (FRINGE_R * 2 * FRINGE_TOUCH)))
    specs = []
    for k in range(count):
        target = run[-1] * (k + 0.5) / count
        i = max(0, min(len(dense) - 2, next((j for j in range(len(run) - 1) if run[j + 1] >= target), len(run) - 2)))
        t = (target - run[i]) / max(run[i + 1] - run[i], 1e-9)
        c0, c1 = dense[i], dense[i + 1]
        p0, p1 = c0['path'], c1['path']
        specs.append(dict(a=c0['a'] + (c1['a'] - c0['a']) * t, path=[p.lerp(q, t) for p, q in zip(p0, p1)]))
    print('fringe %s: %d strands, the bell %.2f m round at the tips' % (side, len(specs), run[-1]))
    for i, sp in enumerate(specs):
        path = catmull(sp['path'], FRINGE_STEP)
        root, d = path[0], (path[-1] - path[-2]).normalized()
        vs, u = tube(bm, path, FRINGE_R, 10, 'bullion', uv_len=BULLION_UV_LEN,
                     taper=lambda t: FRINGE_ROOT + (1 - FRINGE_ROOT) * smoothstep(t, 0.0, 0.25),
                     u0=0.3 * ((i * 0.618) % 1.0))
        uvs.update(u)
        b2 = bmesh.new()  # the wire's bright end in the tip
        bmesh.ops.create_uvsphere(b2, u_segments=8, v_segments=5, radius=FRINGE_R * FRINGE_TIP)
        bmesh.ops.translate(b2, vec=path[-1] + d * (FRINGE_R * 0.72), verts=b2.verts[:])
        me = bpy.data.meshes.new('tmp'); b2.to_mesh(me); b2.free()
        before = set(bm.verts)
        bm.from_mesh(me); bpy.data.meshes.remove(me)
        for v in set(bm.verts) - before:
            uvs[v] = uv_in('tip', 0.5, 0.5)
        wt = on_shoulder(UNI_W.at(root), side)
        for v in uvs:
            if v not in wmap:
                wmap[v] = wt
    fringe = new_part('EpauletteFringe_' + side, bm, lambda v: uvs[v], lambda v: wmap[v])
    return field, fringe


O = bpy.data.objects
# the sash laid once without the cords: where its edges run (the cords go in under its lower edge, the pencil hangs by
# its upper one); then the cords on the tightened cloth (over its folds, as the sash), the sash over them (in the
# portrait they go under it), whatever of them still comes through it pressed in under it
CLOTH = bvh_of([uni, O['Belt'], O['Buckle'], O['Buttons']], torso=True, tighten=SASH_TIGHTEN)
O.remove(build_sash())
loops = build_loops(bvh_of([uni, O['Buttons']], torso=True, tighten=SASH_TIGHTEN, arm_z=AIG_ARM_Z))
CLOTH = bvh_of([uni, loops, O['Belt'], O['Buckle'], O['Buttons']], torso=True, tighten=SASH_TIGHTEN)
sash = build_sash()
UNDER_SASH, SASH_BVH = bvh_of([uni], torso=True), bvh_of([sash])
press_under(loops, UNDER_SASH, SASH_BVH)
pencils = build_pencil(bvh_of([uni, O['Belt'], O['Buckle'], O['Buttons']]),
                       bvh_of([uni, sash, O['Belt'], O['Buckle'], O['Buttons']]))
# what the fringe clears (the cords' tops go in under it) and what the field and strap lie on
CLOTH = bvh_of([uni, sash, loops] + [O[n] for n in ('Belt', 'Buckle', 'Buttons', 'Collar')])
FRINGE_CLOTH, SASH_TOP = bvh_of([uni, loops] + [O[n] for n in ('Belt', 'Buckle', 'Buttons', 'Collar')]), bvh_of([sash], outer=True)
FIELD_CLOTH = bvh_of([uni, sash, O['Collar']])
STRAP_CLOTH, STRAP_UNI = bvh_of([uni, sash]), bvh_of([uni])
eps = [build_epaulette(s) for s in 'lr']

rig.data.pose_position = 'POSE'
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))
