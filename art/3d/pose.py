# Alexander's stance from alexander_ii_full.png, made the rig's rest pose: the clothes are built round the body as it
# stands in the portrait (folds and fit where they are seen), and the game's idle moves only a little away from it.
# Used by build_uniform.py after the body is shaped: pose(rig, human) poses the bones, bakes the posed body into the
# MPFB mesh and applies the pose as the new rest.
# MPFB space: metres, Z up, the body faces -Y, his left is +X. The torso keeps facing -Y here (the clothes are fitted to
# a square front); the whole figure is turned by YAW_DEG towards his left only in front of the camera (render, export).
# Arms and legs: two-bone IK to a wrist / ankle target with an elbow / knee pole; feet turned out about Z, soles flat.
import bpy, math
from mathutils import Vector, Matrix

YAW_DEG = 18.0                     # the figure turned towards his left (the closure is right of centre in the portrait)
SPINE_TWIST = (3.0, 4.0, 4.0)      # spine_01..03 about Z: the shoulders turned further than the hips (contrapposto)
SPINE_LEAN = (0.0, 0.0, 0.0)       # ... and tilted about Y: his left shoulder a little lower (the weight on the right leg)
HEAD_YAW = (-17.5, -25.5)         # neck_01, head about Z: the head as the portrait saw it - its eyes, painted from the
                                   # portrait, look into the camera; the face then turned a little to his right, as there
HEAD_PITCH = 0.0                   # head bent forward (degrees about X): none - bent, the chin went down into the collar
CLAVICLE_DROP = 15.0               # degrees: the shoulders let down and sloping (the portrait's epaulettes sit ~4 cm
                                   # under the body's own shoulder line; level, the shoulders looked square)
# His left arm hangs too, the elbow out at the belt, the forearm in to the sword's hilt by the left hip, the hand over
# the hilt's top in line with the forearm, back of the hand forward, fingers closed round the grip (as in the portrait;
# bent down at the wrist it looked broken); his right arm hangs close by his side, the elbow a little back, the forearm
# across the small of the back on the belt, the back of the hand against it (hidden, as in the portrait - held out
# behind him it stood off the back and twisted the shoulder).
# elbow: where the upper arm points (else a two-bone IK with the pole decides it); palm: the side the palm turns to.
ARM = {
    'l': dict(wrist=(0.215, -0.11, 1.19), elbow=(0.33, 0.04, 1.40), hand_to=(0.195, -0.19, 1.15), palm=(-0.3, 0.3, -1.0)),
    'r': dict(wrist=(-0.035, 0.14, 1.265), elbow=(-0.25, 0.075, 1.36), hand_to=(0.05, 0.125, 1.255), palm=(0, 1, 0)),
}
# Right leg in front, carrying the weight; the left a step behind, its toe turned further out.
LEG = {
    'r': dict(ankle=(-0.165, -0.035), pole=(-0.2, -0.8), turn=-22.0),
    'l': dict(ankle=(0.125, 0.065), pole=(0.2, -0.8), turn=38.0),
}
# Fingers: curl about each bone's own X (degrees per joint 1, 2, 3); thumb separately.
CURL = {
    'l': dict(index=(55, 70, 45), middle=(60, 75, 45), ring=(65, 75, 45), pinky=(70, 70, 45), thumb=(15, 30, 25)),
    'r': dict(index=(45, 55, 30), middle=(50, 60, 35), ring=(55, 60, 35), pinky=(60, 60, 35), thumb=(10, 25, 15)),
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
    _turn_z(pbs['neck_01'], HEAD_YAW[0])
    _turn_z(pbs['head'], HEAD_YAW[1], HEAD_PITCH)


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
