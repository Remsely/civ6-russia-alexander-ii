# Alexander's stance from alexander_ii_full.png, made the rig's rest pose: the clothes are built round the body as it
# stands in the portrait (folds and fit where they are seen), and the game's idle moves only a little away from it.
# Used by build_uniform.py after the body is shaped: pose(rig, human) poses the bones, bakes the posed body into the
# MPFB mesh and applies the pose as the new rest.
# MPFB space: metres, Z up, the body faces -Y, his left is +X. The torso keeps facing -Y here (the clothes are fitted to
# a square front); the whole figure is turned by YAW_DEG towards his left only in front of the camera (render, export).
# Arms and legs: two-bone IK to a wrist / ankle target with an elbow / knee pole; feet turned out about Z, soles flat.
import bpy, math
from mathutils import Vector, Matrix

YAW_DEG = 15.0                     # the figure turned towards his left (the closure is right of centre in the portrait)
SPINE_TWIST = (0.0, 1.0, 1.0)      # spine_01..03 about Z: the shoulders turned a little further than the hips
SPINE_LEAN = (0.0, 0.0, 0.0)       # ... and tilted about Y: his left shoulder a little lower (the weight on the right leg)
HEAD_TURN = -19.0                  # degrees the face is turned from the shoulders towards his left: to his right, nearly
                                   # square to the camera, as in the portrait (fitted to its eyes' middle, nose, eye line
                                   # and left ear in the 'ref' view). The head is symmetric about the body's midplane
                                   # (head_shape.symmetrize) and squared by its eyes first (straighten_head), so it sits
                                   # straight on the neck however far it turns.
HEAD_NECK_SHARE = 0.4              # of that turn the neck takes this much, the head the rest
HEAD_PITCH = 0.0                   # head bent forward (degrees about X): none - bent, the chin went down into the collar
HEAD_ROLL = -1.75                  # ... and tilted about its forward line (towards his left shoulder +): a little to his
                                   # right, as in the portrait
LID_DROP = 16.0                    # degrees the upper lids are let down from the generated head's (of a ~59 deg
                                   # blink): in the portrait they cover the irises' tops; wide open, the eyes stared
CLAVICLE_DROP = 8.0                # degrees the shoulders are let down: the portrait's epaulettes and elbows are ~3 cm
                                   # lower than the body's own shoulders put them (15 deg slumped him like an old man)
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
# is turned out about its own axis (towards his left +) - the right one shows its trouser stripe to the viewer as in
# the portrait (the legs are nearly straight: the knee pole alone bowed them instead of turning them).
LEG = {
    'r': dict(ankle=(-0.162, -0.035), pole=(-0.02, -0.8), turn=-30.0, twist=-30.0),
    'l': dict(ankle=(0.088, 0.065), pole=(0.02, -0.8), turn=26.0, twist=15.0),
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
        pb.matrix = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(CLAVICLE_DROP), 4, ax)
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
    straighten_head(pbs)
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


def straighten_head(pbs):
    """The face square to the shoulders (turned HEAD_TURN from them) and level: neck and head turned about Z till the
    line between the eyes (eye_l, eye_r: build_head.py puts them at the eyeballs' middles) runs as the shoulders' line
    (the spine's twist), then the head rolled about its own forward line till the eyes are at one height; bent forward
    HEAD_PITCH."""
    el, er = pbs.get('eye_l'), pbs.get('eye_r')
    if el is None or er is None:
        return
    want = sum(SPINE_TWIST) + HEAD_TURN
    line = el.head - er.head
    yaw = want - math.degrees(math.atan2(line.y, line.x))
    _turn_z(pbs['neck_01'], yaw * HEAD_NECK_SHARE)
    _turn_z(pbs['head'], yaw * (1 - HEAD_NECK_SHARE), HEAD_PITCH)
    line = el.head - er.head
    q = line.rotation_difference(Vector((line.x, line.y, 0.0)))  # about the face's forward line
    hb = pbs['head']
    p = hb.head.copy()
    hb.matrix = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Matrix.Translation(-p) @ hb.matrix
    _upd()
    if HEAD_ROLL:  # about the face's forward line (square to the eye line, level) through the head's pivot
        line = el.head - er.head
        fw = Vector((line.y, -line.x, 0.0)).normalized()
        p = hb.head.copy()
        hb.matrix = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(HEAD_ROLL), 4, fw) @ Matrix.Translation(-p)
                     @ hb.matrix)
        _upd()
    line = el.head - er.head
    print('head: turned %.1f deg, rolled %.1f deg; eyes %.4f m apart in height, their line %.1f deg from the '
          'shoulders\'' % (yaw, math.degrees(q.angle), line.z, math.degrees(math.atan2(line.y, line.x)) - want))


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
