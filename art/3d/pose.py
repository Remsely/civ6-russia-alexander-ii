# Alexander's stance from alexander_ii_full.png, made the rig's rest pose: the clothes are built round the body as it
# stands in the portrait (folds and fit where they are seen), and the game's idle moves only a little away from it.
# Used by build_uniform.py after the body is shaped: pose(rig, human) poses the bones, bakes the posed body into the
# MPFB mesh and applies the pose as the new rest.
# MPFB space: metres, Z up, the body faces -Y, his left is +X. The torso keeps facing -Y here (the clothes are fitted to
# a square front); the whole figure is turned by YAW_DEG towards his left only in front of the camera (render, export).
# Arms and legs: two-bone IK to a wrist / ankle target with an elbow / knee pole; feet turned out about Z, soles flat.
import bpy, math
from mathutils import Vector, Matrix

YAW_DEG = 25.0                     # the figure turned towards his left: the closure's piping where the portrait has it
                                   # (x 560 of 1024, chest to hem; at 15 deg it was 23 px left of it)
SPINE_TWIST = (0.0, 1.0, 1.0)      # spine_01..03 about Z: the shoulders turned a little further than the hips
SPINE_LEAN = (0.0, 0.0, 0.0)       # ... and tilted about Y: his left shoulder a little lower (the weight on the right leg)
HEAD_TURN = -27.0                  # degrees the face is turned from the shoulders towards his left: to his right, nearly
                                   # square to the camera, as in the portrait (eyes and nose over the portrait's). A plain turn of the neck and head bones
                                   # (turn_head): the head is placed with its own midplane on the body's (head_shape.py),
                                   # so the bones' axis runs up the middle of the neck and the head turns on it.
HEAD_NECK_SHARE = 0.4              # of that turn the neck takes this much, the head the rest
HEAD_PITCH = 0.0                   # head bent forward (degrees about X): none - bent, the chin went down into the collar
HEAD_ROLL = -1.75                  # ... and tilted about its forward line (towards his left shoulder +): a little to his
                                   # right, as in the portrait
LID_DROP = 7.0                     # degrees the upper lids are let down from the generated head's (of a ~59 deg
                                   # blink): in the portrait they cover the irises' tops; wide open, the eyes stared
                                   # (16 deg hid half the iris: sleepy)
CLAVICLE_DROP = {'l': 12.0, 'r': 11.0}  # degrees the shoulders are let down: the portrait's epaulettes and elbows are
                                   # lower than the body's own shoulders put them - a sloping trapezius; his left one more
                                   # (at 8 deg each, over a tunic fitted to the shoulders, his left epaulette stood 2.5 cm
                                   # over the portrait's, his right one's inner end 1-2 cm)
# His left arm hangs too, the elbow out at the belt, the forearm in to the sword's hilt by the left hip, the hand over
# the hilt's top in line with the forearm, back of the hand forward, fingers closed round the grip (as in the portrait;
# bent down at the wrist it looked broken); his right arm hangs down by his side, the elbow at his side and a little
# back, the forearm round the hip to the small of the back, the hand on the belt's middle over the spine, its back
# against the belt (hidden, as in the portrait). The wrist is reached by IK (aimed only, the forearm's own length put
# the hand 5 cm past the spine, under the belt and off the back).
# elbow: where the upper arm points (else a two-bone IK with the pole decides it); palm: the side the palm turns to.
ARM = {
    'l': dict(wrist=(0.255, -0.10, 1.205), elbow=(0.37, 0.04, 1.30), hand_to=(0.19, -0.17, 1.16), palm=(-0.3, 0.3, -1.0)),
    'r': dict(wrist=(-0.07, 0.15, 1.21), elbow=(-0.33, 0.11, 1.24), hand_to=(0.06, 0.13, 1.21), palm=(0, 1, 0)),
}
# Right leg in front, carrying the weight; the left a step behind, its toe turned further out. twist: degrees the leg
# is turned about the hip-to-ankle line (it swings the bent knee: at +20 the right leg bowed off the portrait's
# outline); shin: degrees the shin is turned about its own axis, out with the foot - the trouser stripe on the outer
# seam ~75-85 degrees round from the toe, on the outline in the portrait's view (at twist -30 / 15 and no shin turn
# the right knee pointed 80 degrees inside its foot and the stripe ran down the front of the shin over a turned-out
# boot).
LEG = {
    'r': dict(ankle=(-0.166, -0.006), pole=(-0.159, -0.784), turn=-40.0, twist=0.0, shin=35.0),
    'l': dict(ankle=(0.098, 0.049), pole=(-0.119, -0.791), turn=16.0, twist=0.0),
}
# Fingers: curl about each bone's own X (degrees per joint 1, 2, 3); thumb separately.
CURL = {
    'l': dict(index=(55, 70, 45), middle=(60, 75, 45), ring=(65, 75, 45), pinky=(70, 70, 45), thumb=(15, 30, 25)),
    'r': dict(index=(65, 80, 45), middle=(70, 85, 45), ring=(75, 85, 45), pinky=(80, 80, 45), thumb=(15, 35, 25)),  # a loose fist on the belt
}


def _upd():
    bpy.context.view_layer.update()


def _aim(pb, target, twist=0.0):
    """Turn pose bone pb (its head where its parent put it) so its tail points at target, minimal turn from rest;
    then twist degrees about its own axis."""
    rest = pb.bone.matrix_local
    d0 = (rest.to_3x3() @ Vector((0, 1, 0))).normalized()
    head = pb.head.copy()
    d = (Vector(target) - head).normalized()
    q = d0.rotation_difference(d)
    if twist:
        q = Matrix.Rotation(math.radians(twist), 3, d).to_quaternion() @ q
    pb.matrix = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ rest.to_3x3().to_4x4()
    _upd()


def _ik(upper, lower, target, pole):
    """Elbow / knee for a two-bone chain reaching target, bending towards pole; aims both bones."""
    s = upper.head.copy()
    a, b = upper.bone.length, lower.bone.length
    t = Vector(target)
    d = min((t - s).length, a + b - 1e-4)
    u = (t - s).normalized()
    x = (a * a - b * b + d * d) / (2 * d)
    hh = math.sqrt(max(a * a - x * x, 0.0))
    p = Vector(pole) - s
    w = (p - u * p.dot(u)).normalized()
    elbow = s + u * x + w * hh
    _aim(upper, elbow)
    _aim(lower, s + u * d)


def _turn_z(pb, deg, pitch=0.0, roll=0.0):
    """Pose bone pb turned about the world Z (then X, then Y) through its head."""
    p = pb.head.copy()
    r = (Matrix.Rotation(math.radians(deg), 4, 'Z') @ Matrix.Rotation(math.radians(pitch), 4, 'X')
         @ Matrix.Rotation(math.radians(roll), 4, 'Y'))
    pb.matrix = Matrix.Translation(p) @ r @ Matrix.Translation(-p) @ pb.matrix
    _upd()


def _curl(rig, side):
    for finger, angles in CURL[side].items():
        for i, ang in enumerate(angles):
            pb = rig.pose.bones.get('%s_%02d_%s' % (finger, i + 1, side))
            if pb:
                pb.rotation_mode = 'XYZ'
                pb.rotation_euler = (math.radians(ang), 0, 0)
    _upd()


def set_pose(rig):
    """Pose the bones of the (refitted) rig; nothing baked."""
    pbs = rig.pose.bones
    for pb in pbs:
        pb.matrix_basis.identity()
    _upd()
    for s, leg in LEG.items():
        thigh, calf, foot = pbs['thigh_' + s], pbs['calf_' + s], pbs['foot_' + s]
        ankle_z = foot.bone.head_local.z
        hip = thigh.head
        _ik(thigh, calf, (leg['ankle'][0], leg['ankle'][1], ankle_z),
            (hip.x + leg['pole'][0], hip.y + leg['pole'][1], 0.6))
        if leg.get('twist'):  # about the hip-to-ankle line: the knee stays on it, the leg turns
            ax = (calf.tail - thigh.head).normalized()
            p = thigh.head.copy()
            thigh.matrix = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(leg['twist']), 4, ax)
                            @ Matrix.Translation(-p) @ thigh.matrix)
            _upd()
        if leg.get('shin'):  # the shin turned about its own axis (knee and ankle stay): it turns out with the foot
            ax = (calf.tail - calf.head).normalized()
            p = calf.head.copy()
            calf.matrix = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(leg['shin']), 4, ax)
                           @ Matrix.Translation(-p) @ calf.matrix)
            _upd()
        # the foot keeps its rest attitude (flat sole) turned about Z, at the new ankle
        rest = foot.bone.matrix_local
        ankle = calf.tail.copy()
        foot.matrix = (Matrix.Translation(ankle) @ Matrix.Rotation(math.radians(leg['turn']), 4, 'Z')
                       @ rest.to_3x3().to_4x4())
        _upd()
    for i, (tw, ln) in enumerate(zip(SPINE_TWIST, SPINE_LEAN)):
        _turn_z(pbs['spine_%02d' % (i + 1)], tw, 0.0, ln)
    for s in 'lr':  # the clavicle turned about the axis that takes its tip straight down
        pb = pbs['clavicle_' + s]
        d = (pb.tail - pb.head).normalized()
        ax = d.cross(Vector((0, 0, -1))).normalized()
        p = pb.head.copy()
        pb.matrix = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(CLAVICLE_DROP[s]), 4, ax)
                     @ Matrix.Translation(-p) @ pb.matrix)
        _upd()
    for s, arm in ARM.items():
        if 'elbow' in arm:
            _aim(pbs['upperarm_' + s], arm['elbow'])
            _aim(pbs['lowerarm_' + s], arm['wrist'])
        else:
            _ik(pbs['upperarm_' + s], pbs['lowerarm_' + s], arm['wrist'], arm['pole'])
        _aim(pbs['hand_' + s], arm['hand_to'])
        _curl(rig, s)
        if 'palm' in arm:  # turned about its own axis till the palm faces that way
            hand = pbs['hand_' + s]
            ax = (hand.tail - hand.head).normalized()
            tips = sum((pbs['%s_03_%s' % (f, s)].tail for f in ('index', 'middle', 'ring')), Vector()) / 3
            cur = tips - pbs['middle_01_' + s].head
            cur = (cur - ax * cur.dot(ax)).normalized()
            want = Vector(arm['palm'])
            want = (want - ax * want.dot(ax)).normalized()
            ang = math.degrees(cur.angle(want))
            if cur.cross(want).dot(ax) < 0:
                ang = -ang
            _aim(hand, arm['hand_to'], ang)
    turn_head(pbs)
    lower_lids(pbs)


def lower_lids(pbs):
    """The upper lids turned down LID_DROP about the eyeballs' centres (their bones' heads), about the line between
    the eyes - as a blink turns them."""
    el, er = pbs.get('eye_l'), pbs.get('eye_r')
    if el is None or er is None or not LID_DROP:
        return
    ax = (el.head - er.head).normalized()
    for s in 'lr':
        pb = pbs.get('lid_upper_' + s)
        if pb:
            p = pb.head.copy()
            pb.matrix = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(LID_DROP), 4, ax)
                         @ Matrix.Translation(-p) @ pb.matrix)
    _upd()


def turn_head(pbs):
    """Neck and head turned HEAD_TURN about Z (the neck taking HEAD_NECK_SHARE), the head bent HEAD_PITCH and rolled
    HEAD_ROLL - by angles about the bones' own pivots, nothing fitted to the face."""
    _turn_z(pbs['neck_01'], HEAD_TURN * HEAD_NECK_SHARE)
    _turn_z(pbs['head'], HEAD_TURN * (1 - HEAD_NECK_SHARE), HEAD_PITCH)
    if HEAD_ROLL:  # about the head's forward line through its pivot
        hb = pbs['head']
        fw = hb.matrix.to_3x3() @ hb.bone.matrix_local.to_3x3().inverted() @ Vector((0.0, -1.0, 0.0))  # rest front
        fw = Vector((fw.x, fw.y, 0.0)).normalized()
        p = hb.head.copy()
        hb.matrix = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(HEAD_ROLL), 4, fw) @ Matrix.Translation(-p)
                     @ hb.matrix)
        _upd()
    print('head: turned %.1f deg, rolled %.1f deg, bent %.1f deg' % (HEAD_TURN, HEAD_ROLL, HEAD_PITCH))


def bake(rig, h):
    """The posed body baked into h's mesh (helpers included, vertex groups kept, shape keys dropped) and the pose
    applied as the rig's rest. Returns the 4x4 the head bone moved by (for things placed on the rest head)."""
    hb = rig.pose.bones['head']
    head_move = hb.matrix @ hb.bone.matrix_local.inverted()
    masks = [m for m in h.modifiers if m.type == 'MASK']
    for m in masks:
        m.show_viewport = False
    rig.data.pose_position = 'POSE'
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(h.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    for m in masks:
        m.show_viewport = True
    old = h.data
    if old.shape_keys:
        h.shape_key_clear()
    me.name = old.name
    h.data = me
    for mat in old.materials:
        me.materials.append(mat)
    bpy.context.view_layer.objects.active = rig
    for o in bpy.context.scene.objects:
        o.select_set(o == rig)
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    print('pose: baked into %s (%d verts), rest pose applied' % (h.name, len(me.vertices)))
    return head_move


def pose(rig, h):
    set_pose(rig)
    return bake(rig, h)
