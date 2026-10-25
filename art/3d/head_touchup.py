# The head's colour mended in place, its mesh and UVs untouched (build_head.py is not repeatable, see
# head_retexture.py): textures/head_albedo_base.png (the baked texture: the portrait's skin with its wrinkles, pores
# and painted light) -> textures/head_albedo.png, only where the portrait's or the generation's colour is wrong:
#   blender -b art/3d/alexander_rest.blend --python art/3d/head_touchup.py
# 1. green and grey casts on the skin (the generation's temples and lids, the forehead's edges) to the skin's hue;
# 2. the portrait's dark under the eyes (the bags and their painted outlines, darker on his right) lifted to the cheek
#    under them, their purple-red to its hue; the nose's sides between the eyes and the sockets' upper inner corners
#    under the brows (darker than the brows) to the bridge's colour, lone dark flecks there to the skin round them; the
#    upper lids one colour, a little lighter, out to their inner ends, there a little darker and redder (as in life),
#    the portrait's shade past their outer corners lifted to the skin round it;
#    the texels the blink's Eyelids take their colour from: the lids' colour and one lash colour, both eyes alike;
# 3. the portrait's shade on his right side of the face (its light comes from his left) lifted to his left's level;
# 4. the ears one skin colour with grain (the bake's dark streaks, rings and flakes of hair on them);
# 5. the portrait's shade under the chin's front (a dark band over the plain underside, read as a pale rim) to the
#    chin's colour; the plain skin (the neck, the chin's underside: one flat colour) given grain.
# 0, 6-16 (the bake's seams, the nose's underside, the lips, under the brows, the hair's strands and edges, the beard's
# edge, his right temple's edge as his left one's): see their
# constants. Faces thinner than THIN in the texture: every texel along them has its surface point (the GPU reads
# them; left to the next island's padding they came out as pale shards and dark thorns).
# Each is a gain or a hue shift of the texel's own colour (the ears and the chin's band: a colour with the texel's
# fine detail), by masks from the surface point of each texel (the cheeks' vertices are 5-8 mm apart: masks per vertex
# came out as strips); nothing is made darker but the lids' inner ends (asked for). Safe to re-run: it always starts
# from the base.
# TOUCHUP_DEBUG=1: the masks over the base instead (red under the eyes, green the ears and the lids, blue the light
# lifted, yellow between the eyes); TOUCHUP_GRID=1: lines of height (every 2 mm) and across (every 5 mm) round each
# eyeball's middle, to read the eyes' surroundings off a render.
import bpy, math, os, sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mat_util  # noqa: E402
BASE = os.path.join(HERE, 'textures', 'head_albedo_base.png')
OUT = os.path.join(HERE, 'textures', 'head_albedo.png')
LEADER = os.path.join(HERE, 'alexander_leader.blend')  # its Eyelids (the blink's) take their colour off this texture
TEX = 2048
THIN = 2.0                        # px: faces thinner than this in the texture have every texel along them
LUM = mat_util.LUM

BAKE_FILL = ((92, 38, 17), 6, 1.9, 1.0)  # 0. the bake's fill colour (sRGB) within this, and texels next to it redder
                                  # than this R/G: the colour round them averaged over voxels this big (mm)
SKIN_L = (0.42, 0.56)             # sRGB luminance (per vertex smoothed 2 rounds; per texel the 3 px mean): hair under
                                  # the first, skin by the second
SKIN_HUE = (0.680, 0.444)         # the skin's G/R and B/R (the plain neck's: the portrait's skin colour)
GREEN = ((0.035, 0.10), (0.05, 0.13))  # G/R, B/R over SKIN_HUE's: a green / grey cast from the first, fully by the
                                  # second
EYE_KEEP = 0.009                  # m round each eyeball's middle: the lash lines, no hue change (the lids above it
                                  # take it: a grey-green patch on his left lid)
UNDER_EYE = (-0.020, 0.036, 0.016)  # m: the band's middle under the eyeball's middle, its half-width, half-height
UNDER_EYE_RIM = (0.005, 0.009)    # m under the eyeball's middle: the lower lid's lash line kept, lifted by the second
UNDER_EYE_REF = (-0.040, -0.052)  # ... the cheek under it (z from the eyeball's middle) the dark is lifted to
UNDER_EYE_HUE = 0.6               # ... its hue this much to the cheek's (the bags are purple-red)
UNDER_EYE_LINES = (6, 0.95)       # ... its painted dark lines (against the px mean) this much lighter: the bags'
                                  # outlines (the bags themselves are in the surface; at 0.7 their lower edge stayed a
                                  # purple-brown line, a bruise's rim)
LIGHT_R = 6                       # px: the local light (box mean) the lifts compare
LIFT_MAX = 1.45                   # no texel brighter than this times itself
BRIDGE_X = (0.004, 0.012)         # between the eyes: from the first towards the nose from each eyeball's middle,
                                  # fully by the second
BRIDGE_Z = (-0.032, -0.024, 0.012, 0.017)  # ... z from the eyes' middle: fading in, full, fading out (the brows' inner
                                  # ends over it), none - the nose's sides and the sockets' upper inner corners, where
                                  # the portrait's shade is darker than the brows (L 0.14-0.4 against the bridge's 0.72)
BRIDGE_EYE = (0.017, 0.0065, 1.0, 1.1)  # ... not in the eye's opening: an ellipse round the eyeball's middle (half-width
                                  # with the inner corner, half-height), from the third of it fading in by the fourth
BRIDGE_REF = (0.004, -0.012, 0.0)  # ... to the colour of the bridge's ridge: |x - middle| under the first, z from the
                                  # eyes' middle between these
BRIDGE_DETAIL = (0.97, 1.03)      # ... its fine light and dark (against the 3 px mean) kept within these (wider, the
                                  # bake's noise in the shade came out as scales)
BRIDGE_GRAIN = 0.03               # ... and the skin's grain: brightness +- this (as PLAIN_GRAIN)
BRIDGE_TONE = 0.94                # ... the ridge's colour times this (the lids' and the cheeks' light; the ridge itself
                                  # is the lightest skin there: a pale patch)
SPECK = (0.72, 0.12, 5)           # between the eyes: a fleck darker than this times round it (px mean of the third),
                                  # alone (under the second share of the texels round it dark: not a wrinkle's line), to
                                  # the colour round it (a dark dot under his left brow)
BRIDGE_SHADE = (0.02, 0.12)       # ... by how much the light (6 px mean) is under that: none / all of it (the lids keep
                                  # their own colour; the weight smooth, else the half-lifted bake's noise shows as scales)
LID_LO = (0.0035, 0.020)          # the upper lid (the fold from the lash line to under the brow) from this far over the
                                  # eyeball's middle at its middle, down to it at the ends, this far either side
LID_HI = (0.0125, 0.024)          # ... up to this, down to it at the ends this far either side (the brow over it)
LID_FADE = (0.001, 0.002)         # ... fading in under the lash line, out under the brow, over these
LID_DARK = (0.30, 0.40)           # ... texels this light (3 px mean) and over are the lid (under: the lashes, the brow)
LID_DETAIL = (0.88, 1.08)         # ... its fine light and dark (against the 3 px mean) kept within these (the crease)
LID_LIGHT = 0.5                   # ... both one colour (the two lids' hue: his right one was darker and browner), its
                                  # light this share of the way to the bridge's (the lids were dull, not as light as
                                  # the nose)
LID_INNER = (0.0, 0.013, 0.019, 0.026)  # ... towards its inner end: m towards the nose from the eyeball's middle,
                                  # fading in, full, fading out, none (on into the socket's corner by the nose)
LID_INNER_Z = (0.0, 0.003, 0.010, 0.017)  # ... z from the eyeball's middle: fading in, full, fading out under the brow
LID_INNER_TONE = (0.74, (1.10, 0.95, 0.85))  # ... a little darker and redder there (thin skin by the nose: in the
                                  # portrait and in life the lid's inner end is darker, red-brown; one lid colour all
                                  # the way read as unnatural)
CORNER = ((0.013, 0.016, 0.024, 0.028), (-0.010, -0.007, 0.005, 0.008), 0.035)  # past each eye's outer corner: m out
                                  # from the eyeball's middle fading in, full, fading out, none; z from it likewise; in
                                  # front of its y + the third (the portrait's shade past his right eye's corner: a dark
                                  # red-brown wedge from the lash line to the temple, L 0.25-0.45 against 0.55-0.65 round
                                  # it and his left's 0.5-0.7 - from the side it read as a stain on the lid)
CORNER_REF = ((0.016, 0.024), (-0.012, -0.009), (0.008, 0.011))  # ... lifted to the skin's light under and over it:
                                  # m out, z bands under and over (their median)
CORNER_DETAIL = (0.92, 1.06)      # ... its fine light and dark (against the 3 px mean) kept within these (the creases)
CORNER_DARK = (0.03, 0.10)        # ... by how much its light (6 px mean) is under the skin's: none / all of it
SIDE_X = (0.0, -0.025)            # his right side (x < the face's middle) from the first, fully by the second
SIDE_Z = (1.80, 1.84, 2.04, 2.08)  # ... between these heights (fading in, fading out)
SIDE_Y = (0.0, 0.03)              # ... in front of this (y; the ears at ~0), fading out by the second
SIDE_ROUNDS = 12                  # mesh rounds the light is averaged over on both sides
SIDE_MAX = 1.3
SIDE_HUE = 0.8                    # ... and its hue this much to his left's (the portrait's red blotch on his right
                                  # cheek)
PURPLE = (0.09, 0.2)              # round the eyes (EYE_NEAR): B/G over the skin's from the first, fully by the second
                                  # is a purple cast (his right upper lid), to the skin's hue
EYE_NEAR = (0.028, 0.038)         # m from the eyeball's middle, fading out by the second
INNER = (0.017, -0.003, 0.009)    # the dark in each eye's inner corner by the nose: its middle (x towards the nose, z
                                  # from the eyeball's middle), radius; lifted to the cheek's light as under the eye
EAR = {1: [(-0.022, 1.891), (-0.030, 1.905), (-0.030, 1.921), (-0.025, 1.940), (-0.016, 1.952), (-0.004, 1.958),
            (0.008, 1.957), (0.013, 1.950), (0.015, 1.935), (0.015, 1.918), (0.012, 1.905), (0.004, 1.893),
            (-0.006, 1.887), (-0.015, 1.887)],
       -1: [(-0.025, 1.888), (-0.033, 1.905), (-0.031, 1.930), (-0.025, 1.942), (-0.012, 1.947), (0.000, 1.945),
            (0.008, 1.938), (0.012, 1.928), (0.013, 1.912), (0.008, 1.898), (0.000, 1.889), (-0.012, 1.885)]}
                                  # each ear (by the side of x) seen from that side: its outline (y, z; rest pose, m),
                                  # taken off the head's relief seen sideways (off the base texture, his left one's ran
                                  # 9 mm back past the rim onto the head behind it: a flat skin sheet there; his right
                                  # one's stopped 7 mm short of its rim; its top over the rim's, 8 mm up, was the
                                  # hair's: skin colour on it)
EAR_BACK = {1: [(-0.029, 1.906), (-0.028, 1.927), (-0.024, 1.946), (-0.012, 1.955), (0.004, 1.957), (0.016, 1.951),
                 (0.023, 1.936), (0.024, 1.912), (0.019, 1.890), (0.010, 1.882), (-0.006, 1.883), (-0.022, 1.892)],
            -1: [(-0.025, 1.888), (-0.033, 1.905), (-0.031, 1.930), (-0.025, 1.942), (-0.012, 1.947), (0.002, 1.945),
                 (0.012, 1.938), (0.020, 1.928), (0.020, 1.910), (0.013, 1.894), (0.002, 1.886), (-0.012, 1.883)]}
                                  # ... and out to these: where it faces back (the rim's back) also the ear
EAR_X = (0.068, 0.075)            # ... |x| out from the head: the ear from the first, fully by the second (the hair
                                  # and the skin round it are nearer the head)
EAR_EDGE = 0.002                  # m inside the outline the ear is fully its colour
EAR_HALO = (0.0005, 0.002, 0.009, 0.013)  # m outside the outline: skin colour on the hair round the ear (over his right
                                  # one, behind his left one) to the hair's, from / fully / fading out / none
HALO_SKIN = (0.36, 0.48)          # ... texels this light (3 px mean) are skin colour
EAR_TINT = (1.0, 0.97, 0.97)      # the ears: the skin colour times this (a little redder)
EAR_GRAIN = 0.04                  # ... their grain: brightness +- this (the bake's light and dark on them are rings
                                  # and streaks, none of it kept)
EAR_RED = (0.010, (1.0, 0.89, 0.86))  # ... nearer the head than the rim (the bowl) by this much: redder by this, the
                                  # light kept (the portrait's ear: a warm bowl, a paler rim - one flat colour read as
                                  # plastic)
EAR_MOTTLE = (0.006, 0.035)       # ... and blotches this big (m), brightness +- the second
CHIN = (1.826, 1.831, 1.846, 1.856)  # z: the portrait's shade under the chin's front (L 0.41-0.55 against 0.70 over
                                  # it and the plain underside's 0.65), fading in and out
CHIN_X = (0.06, 0.075)            # ... |x| from the middle, fading out by the second (the beard: CHIN_HAIR)
CHIN_HAIR = (0.28, 0.36)          # ... the texel's 3 px mean luminance: the beard under the first, the shade by the
                                  # second (as dark as 0.41)
CHIN_REF = (1.849, 1.860)         # ... to the chin's colour over it
CHIN_DETAIL = (0.92, 1.08)        # ... its fine light and dark (against the 3 px mean) kept within these
SHUT_R = (2.5, 4.0)               # px round each texel the blink's Eyelids take their colour from (two a lid: its edge
                                  # and its skin): the skin the lids' colour, the edges one lash colour, fading out by
                                  # the second (a single texel each - the skin's on his right lid was a darker crease)
PLAIN_GRAIN = 0.035               # the plain skin's grain: brightness +- this (noise at ~1.5 and ~5 mm)
UNDER_EYE_TINT = ((0.036, 0.042), (0.022, 0.026), (-0.002, -0.004), (-0.032, -0.040))  # under each eye: m out from
                                  # its middle (away from the nose), towards the nose, z from its middle under the lash
                                  # line, down to (each: full, none) - the hue the face's (the portrait's lower lids
                                  # purple, the bags under them yellow-green: a bruise in the light)
BAGS = ((-0.010, 0.002), (0.006, 0.018), 0.82, (1.05, 1.0, 1.05))  # ... the bags: their middle (z from the eyeball's
                                  # middle, x out from it), half-height, half-width; no lighter than the cheek's light
                                  # times this (the portrait's: 0.81-0.82; lifted to the cheek's they read as none), a
                                  # little redder and bluer than the face (theirs: R/G 1.6-1.7, B/G 0.75 against 1.54,
                                  # 0.64)
LASH = (0.6, 1.2, 0.5, 1.0)       # his left eye's lash lines (the lid lowered over its eyeball by head_lid.py: the lid's
                                  # skin colour ran to its edge, the eye looked smaller): the upper one fully this far
                                  # (mm) from the lid's edge, none by the second, the lower one the same by the last
                                  # two; their colour by the distance off the edge as his right eye's
NOSE = ((-0.147, 1.917), (0.034, 0.030, 0.022), 0.7)  # 6. round the nose's underside: y, z of the middle (x the face's);
                                  # semi-axes (x, y, z), fully from this share of them in (out over the wings' joins
                                  # with the cheeks: the islands' seams there, the zone's edge on them, showed as a
                                  # jagged pale rim and a red crease)
NOSE_CREASE = ((0.0225, -0.1245, 1.9215), 0.007)  # ... and round each wing's crease by the cheek (x either side of the
                                  # face's middle, y, z; radius): the portrait's red shade in it
NOSE_SMOOTH = (1.0, 3)            # ... the colour averaged in space over voxels this big (mm), a box this many voxels
                                  # either side, twice (the portrait's nostrils projected onto the tip's underside and
                                  # its shade by the nose's wings: brown and red blotches, pale streaks - averaged over
                                  # the texture they bled into the next islands)
NOSE_OVER = (1.902, 1.906, 1.908, 1.912)  # ... z: facing down over the first two the nose (under them the moustache),
                                  # facing any way over the last two (the portrait's shade by the nostrils' outer ends)
NOSE_FRONT = (0.55, 0.85, 0.6)    # ... facing forward this much (from, fully): the averaged hue, the light only this
                                  # share of the way to the average (the nose's front: averaged it came out pale and
                                  # flat; its blotches are pink, a hue)
NOSE_LIT = (0.85, 0.97)          # ... averaging only texels this light (against the median there) and over
NOSE_DETAIL = (0.96, 1.04)        # ... the fine light and dark kept within these
NOSTRIL = (0.009, -0.1475, (5.0, 2.7), 22.0, 1.2)  # ... the nostrils (shallow dips in the mesh): either side of the
                                  # middle this far, at this y; semi-axes (along, across; mm), the back end turned out
                                  # this many degrees; the soft edge (mm)
NOSTRIL_SRGB = ((92, 44, 32), (120, 60, 44))  # ... their colour, in the middle and at the edge (the portrait's: a warm
                                  # dark, not black)
NOSE_UNDER = (1.904, 1.908, (0.15, 0.35))  # ... under the nose's base (z: all of it nose over the second) only what
                                  # faces down this much (from, fully): what faces forward there is the moustache's top
                                  # (its light brown passes for skin by its light: averaged with the nose, pale patches)
LOWER_LIP = (0.009, 0.005, (0.0, 0.022), 0.00025, (0.020, 0.026), 1.858)  # 7. the lower lip: this tall under the
                                  # mouth's line (LIP) at the middle, this at |x - middle| past the third's range (the
                                  # portrait's is fullest at the middle), the soft edge; |x - middle| fading out between
                                  # these; under it down to this z the chin's colour, the fine light and dark kept (the
                                  # portrait's shade under the lip, on its underside and in the groove under it: a red
                                  # roll seen from below, the lip twice its size)
LIP = ((196, 94, 74), 0.95, (0.92, 1.08), (1.8852, 0.004, (0.006, 0.024)), (0.22, 0.30))  # ... over that edge up to
                                  # the mouth's line the portrait's lit lip colour (sRGB), this share of the way, the
                                  # fine light and dark kept within these; the mouth's line: z at the middle, that much
                                  # lower past |x - middle| between these; texels this light (3 px mean; from, fully)
                                  # and over (under: the moustache) - the bake's lip was the skin's colour where the
                                  # portrait's light was on it, its shade under it gone: no lip at all
LIP_EDGE = (0.0007, 0.88)         # ... its lower edge's vermilion border: this far over it, this times darker (the
                                  # portrait's lip is drawn crisply against the chin; a pale pink band blurred into it)
LIP_SHADE = (0.35, 1.05, (0.80, 0.68, 0.62))  # ... the lower lip modelled as the portrait's (the mesh's lip is flat: no light on
                                  # its top, no shade under it - the two lips ran into one pink band): its top this
                                  # share of its height lit by the second, under that down to its lower edge to the
                                  # third, warmer (the portrait's: 221 124 94 on top, 143 63 41 at the edge; evenly the
                                  # lip's foot went mauve)
UNDER_LIP = (0.0065, 0.0035, (0.66, 0.52, 0.48))  # ... and the shade under it: this deep under its edge at the middle,
                                  # this at the corners, the chin's colour times these at the edge (warmer: the
                                  # portrait's 129 61 39 under the lip, 243 166 112 on the chin), fading out down
MOUTH_RIM = (0.0015, 0.0025, 0.35, 0.8)  # ... the upper lip's underside (from this under the mouth's line to this over
                                  # it, facing down more than this) the lip's colour times this (the bake put the lower
                                  # lip's light on parts of it: flecks in the mouth's line, white teeth seen from below)
UPPER_GAP = (0.009, (1.883, 1.899), (0.008, (1.874, 1.884)))  # 7. the upper lip in the moustache's gap: |x - middle|
                                  # under, z between: no lighter than the lower lip (|x - middle| under, z between) -
                                  # the portrait's light on it was a glowing knob (the lips' own colours kept: a flat
                                  # pink band and a flat chin under it read as no lips at all)
UPPER_GAP_HUE = 0.8               # ... and this share of the way to the lip's hue (its light there: white-yellow)
UPPER_GAP_CAP = 0.82              # ... no lighter than this times the lower lip (as light as it, the two lips ran into
                                  # one pink patch: in the portrait the upper one, under the moustache, is the darker)
MOUTH_LINE = (0.0025, (0.016, 0.022), (0.70, 0.82), 0.45, (0.40, 0.50))  # 7. the mouth's line: within this of it
                                  # (z), |x - middle| fading out between these, texels darker than the lip by these
                                  # (3 px light over the lip's; fully, none) to this times the lip's colour, not those
                                  # this dark and under (the moustache's hair) - the bake's line ran 3 mm in a soft ramp
                                  # from the upper lip's pink, the portrait's is a crisp dark stroke
SIDEBURN = ((-0.064, -0.058), (-0.039, -0.034), (1.878, 1.884), (1.956, 1.962), 0.05)  # 13. his left sideburn in front
                                  # of the ear: y in (none, full), y out, z in, z out, |x - middle| over: the hair of his
                                  # right one there, mirrored (the bake's skin colour off the ear: a pale strip)
SIDEBURN_PALE = (1.15, 1.5, 0.35)  # ... fully where lighter than the hair by the first to the second times, else this
                                  # share of it
HAIR_L = (0.30, 0.40)             # 3 px mean luminance: hair under the first, skin over the second
ROOF = (3.0, 1.0, 20.0)           # 8. under each brow: from this far (mm) under the fold over the lid to this far over
                                  # it, facing down there (the overhang's underside); within this mm across the eye
                                  # (4 mm over it took in the brows' lower edges: their hair lid-coloured, the brows
                                  # thin and dull)
ROOF_TONE = 0.97                  # ... lifted to the lids' colour times this, the fine light and dark kept, the hue the
                                  # skin's (the portrait's shade under the brows: dark brown and grey-green patches)
STRANDS = ((110, 1.0), (260, 0.6), (620, 0.35))  # 10. hair strands where skin colour turns hair: across them (per
                                  # metre, weight)
STRAND_CONTRAST = 0.28            # ... brightness +- this
BEARD_UNDER = (1.880, 0.35, 0.42, (0.012, 0.25))  # ... the beard's underside: under this z, facing down by more
                                  # than this: strands of this contrast and clumps (m, brightness +-) - one flat colour
                                  # there read as a plank, not hair
STREAK = (1.25, 1.25, 0.5)        # 11. in the hair at the sides: texels this much lighter than the hair round them,
                                  # skin-hued (R/G over the second), with hair all round (share over the third): the
                                  # skin colour the bake left in the whiskers - pale strips
BACK = (0.035, 0.050)             # 12. behind the ears (y) from the first, fully by the second: the hair's hue and the
                                  # nape's skin's, the light kept (red-brown blotches of the generation's on the back)
BEARD_ZONE = ((1.848, 1.856), (1.888, 1.898), (0.058, 0.066), (-0.065, -0.055))  # ... the beard's back ends under
                                  # the ears: z in, z out, |x - middle| in, y in (behind the cheeks): all hair
SPECK2 = (0.70, 1.60, 5)          # ... flecks on the skin by the hair's edge darker than this times round them, in the
                                  # hair lighter than the second (px mean of the third): to what is round them
EDGES = [((-0.21, -0.20, -0.062, -0.052), (-0.095, -0.088, -0.022, -0.012), (1.918, 1.928, 2.000, 2.010)),
         ((0.008, 0.011, 0.026, 0.030), (-0.21, -0.20, -0.118, -0.110), (1.868, 1.872, 1.892, 1.896)),
         ((-0.030, -0.026, -0.011, -0.008), (-0.21, -0.20, -0.118, -0.110), (1.868, 1.872, 1.892, 1.896)),
         ((-0.047, -0.043, -0.024, -0.020), (-0.21, -0.20, -0.118, -0.112), (1.894, 1.897, 1.912, 1.915))]
                                  # 14. the hair's edge drawn again where the bake left it in teeth (texel steps of the
                                  # islands' edges, skin slivers in the hair, hair flecks on the skin - a seam): on his
                                  # right temple, by the mouth's corners and along his right moustache's top under the
                                  # fold from the nose (a pale beaded line) (x from the face's middle, y, z: fading in,
                                  # full, full, fading out)
MOUSTACHE_END = ((-0.058, -0.055, -0.040, -0.037), (-0.130, -0.128, -0.119, -0.117), (1.884, 1.886, 1.897, 1.899),
                 (0.35, 0.55), 0.009, 0.30)  # 14. his right moustache's top end by the cheek (x from the face's
                                  # middle, y, z: fading in, full, full, fading out): what the light calls skin there
                                  # (from, fully) the moustache's own hair this much nearer the middle at the same
                                  # height (texels darker than the last) - the bake's skin on the hair's bump: a pink
                                  # knob with a red fleck at the foot of the fold from the nose (his left moustache is
                                  # narrower: skin there, mirrored)
EDGE_SMOOTH = (0.5, 2, 3)         # ... the skin's share averaged in space over voxels this big (mm), a box this many
                                  # voxels either side, twice; the skin's and the hair's colour over this many
EDGE_BAND = ((0.03, 0.15), (0.85, 0.97), (0.35, 0.65))  # ... redrawn where the averaged share is between these
                                  # (fading), the new edge where it crosses these (soft)
EDGE_DETAIL = (0.93, 1.07)        # ... the fine light and dark kept within these
EDGE_SKIN = (5, (0.90, 0.99))     # ... and the skin by the edge (the share averaged over this many voxels under the
TEMPLE_EDGE = ((1.895, 1.910, 2.000, 2.010), (2.0, 6), (0.02, 0.10, 0.90, 0.98), 0.012, 0.3)  # 16. his right
                                  # temple's hair edge (EDGES' first zone's |x - middle| and y, between these z) as his
                                  # left one's: the band across the edge (the skin's share averaged in space over voxels
                                  # this big, mm, a box this many either side, between these: fading in, full, fading
                                  # out, none) takes the colour of his left one's texel at the same height and the same
                                  # share (one unit of it counting as this many m, y this much) - its strands combed
                                  # over the skin onto his right one's own edge (there a smooth blurred seam; mirrored
                                  # by position the left's skin came onto the right's hair, the sides' shapes differ;
                                  # drawn strands read as scratches)
BEARD_EDGE = ((1.800, 1.810, 1.895, 1.905), (0.010, 0.016, 0.075, 0.085), (-0.060, -0.040), (0.12, 0.20, 0.55, 0.65),
              (0.03, 0.08), (0.028, 0.032, 1.869, 1.873))  # 15. the beard's edge on the lower face: z, |x - middle|
                                  # (fading in, full, fading out, none), in front of y (fully by the first); the texels
                                  # between the hair's light and the skin's (3 px mean: from, full, to, none) and redder
                                  # than the skin (its G/R over theirs: from, fully) - not the lips (|x - middle| under
                                  # these, z over these): the red-brown hair's half tones by the skin, a red rim round
                                  # the chin (the portrait's beard edge is wisps of ash brown)
BEARD_EDGE_HUE = (1.0, 0.66, 0.46)  # ... to this hue (R G B, R = 1: the skin's a shade browner), the light kept
                                  # second: ~4 mm) its colour averaged too (shards of the next islands' skin there, a
                                  # patchwork of pink, grey and pale)


def smoothstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def vnoise(p, f, seed):
    """3D value noise, -1..1, at f cells per metre."""
    q = p * f
    i = np.floor(q).astype(np.int64); t = q - i
    t = t * t * (3 - 2 * t)

    def hsh(a, b, c):
        h = (a * 73856093) ^ (b * 19349663) ^ (c * 83492791) ^ seed
        h = (h ^ (h >> 13)) * 1274126177
        return ((h ^ (h >> 16)) & 0xffff).astype(np.float32) / 65535.0
    r = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                wgt = (t[..., 0] if dx else 1 - t[..., 0]) * (t[..., 1] if dy else 1 - t[..., 1]) * \
                      (t[..., 2] if dz else 1 - t[..., 2])
                r = r + wgt * hsh(i[..., 0] + dx, i[..., 1] + dy, i[..., 2] + dz)
    return r * 2 - 1


head = bpy.data.objects['Head']
me = head.data
co = np.array([v.co[:] for v in me.vertices], np.float32)
nrm = np.array([v.normal[:] for v in me.vertices], np.float32)
ed = np.array([e.vertices[:] for e in me.edges])
nv = len(co)
deg = np.maximum(np.bincount(ed.ravel(), minlength=nv), 1).astype(np.float32)


def mesh_smooth(a, rounds, w=None):
    """Per-vertex values averaged over their neighbours, rounds times; with w a weighted average (w = 0 counts not)."""
    a = np.asarray(a, np.float32).reshape(nv, -1)
    w = np.ones(nv, np.float32) if w is None else np.asarray(w, np.float32)
    s, ws = a * w[:, None], w.copy()
    for _ in range(rounds):
        acc, wacc = s.copy(), ws.copy()
        np.add.at(acc, ed[:, 0], s[ed[:, 1]]); np.add.at(acc, ed[:, 1], s[ed[:, 0]])
        np.add.at(wacc, ed[:, 0], ws[ed[:, 1]]); np.add.at(wacc, ed[:, 1], ws[ed[:, 0]])
        s, ws = acc / (deg + 1)[:, None], wacc / (deg + 1)
    return s / np.maximum(ws, 1e-6)[:, None]


img = bpy.data.images.load(BASE)
img.colorspace_settings.name = 'sRGB'
w_, h_ = img.size
px = np.array(img.pixels[:], np.float32).reshape(h_, w_, 4)
rgb = px[..., :3].copy()

# per vertex: the texture's colour round its UVs (3 px mean), averaged over its loops
uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
soft = mat_util.blur(rgb, 3)
ix = np.clip((uv[:, 0] * w_).astype(int), 0, w_ - 1); iy = np.clip((uv[:, 1] * h_).astype(int), 0, h_ - 1)
vcol = np.zeros((nv, 3), np.float32); np.add.at(vcol, lv, soft[iy, ix])
vcol /= np.maximum(np.bincount(lv, minlength=nv), 1)[:, None]
vL = vcol @ LUM
skin_v = smoothstep(mesh_smooth(vL, 2)[:, 0], *SKIN_L)

# the eyeballs' middles
eyes = bpy.data.objects['Eyes']
ec = np.array([eyes.matrix_world @ v.co for v in eyes.data.vertices], np.float32)
mid_x = float(ec[:, 0].mean())
EYE = {}
for s, m in (('l', ec[:, 0] > mid_x), ('r', ec[:, 0] <= mid_x)):
    e = ec[m]
    EYE[s] = (e.min(0) + e.max(0)) / 2
    print('eye %s: middle %s' % (s, np.round(EYE[s], 3)))

# --- 3. his right side: per vertex the gain to his left's mirror image's light --------------------------------------
kd = KDTree(nv)
for i, q in enumerate(co):
    kd.insert(q, i)
kd.balance()
Lside = mesh_smooth(vL, SIDE_ROUNDS, skin_v)[:, 0]
mir = np.array([kd.find((2 * mid_x - q[0], q[1], q[2]))[1] for q in co])
side_w = (smoothstep(mid_x - co[:, 0], -SIDE_X[0], -SIDE_X[1])
          * smoothstep(co[:, 2], SIDE_Z[0], SIDE_Z[1]) * (1 - smoothstep(co[:, 2], SIDE_Z[2], SIDE_Z[3]))
          * (1 - smoothstep(co[:, 1], *SIDE_Y)) * skin_v * skin_v[mir])
g = np.clip(Lside[mir] / np.maximum(Lside, 1e-3), 1, SIDE_MAX)
side_v = 1 + (g - 1) * side_w
Cside = mesh_smooth(vcol / np.maximum(vL, 1e-4)[:, None], SIDE_ROUNDS, skin_v)
side_ch = 1 + (Cside[mir] / np.maximum(Cside, 1e-4) - 1) * (side_w * SIDE_HUE)[:, None]  # per channel
print('right side: gain up to %.2f, %d vertices over 1.05' % (side_v.max(), int((side_v > 1.05).sum())))


# --- per texel ------------------------------------------------------------------------------------------------------
data, cov = mat_util.raster(me, TEX, np.concatenate([np.stack([side_v, skin_v], 1), side_ch], 1))
# faces too small to cover a texel's middle (the decimation's slivers by the ears and the beard): the texel under
# each one's middle is its, else it kept whatever island's padding lay there (dark and pale shards)
uvl = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uvl); uvl = uvl.reshape(-1, 2)
vals = np.concatenate([co, nrm, np.stack([side_v, skin_v], 1), side_ch], 1)
small = 0
for poly in me.polygons:
    li = list(poly.loop_indices)
    c_ = uvl[li].mean(0) * TEX
    tx, ty = int(c_[0]), int(c_[1])
    if 0 <= tx < TEX and 0 <= ty < TEX and not cov[ty, tx]:
        data[ty, tx] = vals[list(poly.vertices)].mean(0); cov[ty, tx] = True; small += 1
print('faces under a texel: %d' % small)
# ... and faces thinner than THIN px in the texture (long slivers: by the hair's edge on his right temple, pale shards
# standing out of the hair): every texel within a texel of one is its, at the nearest point of it (the GPU reads the
# texels along it, not only the one under its middle)
me.calc_loop_triangles()
thin = 0
thin_m = np.zeros(cov.shape, bool)
for t_ in me.loop_triangles:
    P = uvl[list(t_.loops)] * TEX
    e_ = [P[(i + 1) % 3] - P[i] for i in range(3)]
    area = abs(e_[0][0] * e_[1][1] - e_[0][1] * e_[1][0]) / 2
    if 2 * area / max(max(np.hypot(*v) for v in e_), 1e-9) >= THIN:
        continue
    V = vals[list(t_.vertices)]
    x0, y0 = np.floor(P.min(0) - 1).astype(int)
    x1, y1 = np.ceil(P.max(0) + 1).astype(int)
    for ty in range(max(y0, 0), min(y1, TEX - 1) + 1):
        for tx in range(max(x0, 0), min(x1, TEX - 1) + 1):
            if cov[ty, tx]:
                continue
            c_ = np.array([tx + 0.5, ty + 0.5])
            best = None
            for i in range(3):  # the nearest point on the triangle's edges (it is thinner than a texel)
                a_, d_ = P[i], e_[i]
                s_ = float(np.clip((c_ - a_) @ d_ / max(d_ @ d_, 1e-12), 0, 1))
                dist = np.hypot(*(a_ + d_ * s_ - c_))
                if best is None or dist < best[0]:
                    best = (dist, i, s_)
            if best[0] <= 1.0:
                i, s_ = best[1], best[2]
                data[ty, tx] = V[i] * (1 - s_) + V[(i + 1) % 3] * s_; cov[ty, tx] = True; thin_m[ty, tx] = True
                thin += 1
print('texels along thin faces: %d' % thin)
pos, tn = data[..., 0:3], data[..., 3:6]
side_g, skin_tv, side_c = data[..., 6:7], data[..., 7], data[..., 8:11]


def smooth3d(a, w, vox, r, prior=None, at=None):
    """a (H, W, C) averaged over space where w > 0 (weighted by w): voxels vox m big, a box r voxels either side, twice;
    sampled back trilinearly (in the texture, the islands next to each other are not next to each other on the head).
    prior (colour, share): that colour counted in as this share of the median weight round a texel (where little of w
    is near, the average is that colour). at: where to sample it (else where w > 0)."""
    m = w > 0
    at = m if at is None else at & cov
    lo = np.minimum(pos[m].min(0), pos[at].min(0)) - vox * (r + 2)
    hi = np.maximum(pos[m].max(0), pos[at].max(0))
    shape = tuple(((hi - lo) / vox + r + 3).astype(int))
    q = (pos[m] - lo) / vox
    i0 = np.floor(q).astype(int); t = q - i0
    acc = np.zeros(shape + (a.shape[-1] + 1,), np.float32)
    val = np.concatenate([a[m] * w[m][:, None], w[m][:, None]], 1)
    for c in np.ndindex(2, 2, 2):
        k = np.prod(np.where(np.array(c), t, 1 - t), 1)[:, None]
        idx = tuple((i0 + np.array(c)).T)
        for j in range(acc.shape[-1]):
            np.add.at(acc[..., j], idx, val[:, j] * k[:, 0])
    for _ in range(2):
        for ax in range(3):
            cs = np.cumsum(np.pad(acc, [(r + 1, r) if i == ax else (0, 0) for i in range(3)] + [(0, 0)]), ax)
            acc = (np.take(cs, np.arange(2 * r + 1, cs.shape[ax]), ax) - np.take(cs, np.arange(0, cs.shape[ax] - 2 * r - 1), ax))
    q = (pos[at] - lo) / vox
    i0 = np.floor(q).astype(int); t = q - i0
    res = 0
    for c in np.ndindex(2, 2, 2):
        k = np.prod(np.where(np.array(c), t, 1 - t), 1)[:, None]
        res = res + acc[tuple((i0 + np.array(c)).T)] * k
    if prior is not None:
        s = prior[1] * float(np.median(res[:, -1]))
        res = res + np.concatenate([np.asarray(prior[0], np.float32) * s, [s]])[None]
    o = a.copy()
    o[at] = res[:, :-1] / np.maximum(res[:, -1:], 1e-6)
    return o


# 0. the bake's fill colour on covered texels (its seams: a red-brown dotted line across the beard) to the colour round
# them on the head
fill_ = cov & (np.abs(rgb * 255 - BAKE_FILL[0]).max(-1) <= BAKE_FILL[1])
fill_ = cov & (mat_util.blur(fill_.astype(np.float32), 1) > 0) & (rgb[..., 0] / np.maximum(rgb[..., 1], 1e-4) > BAKE_FILL[2])
cell = np.floor(pos / 0.004).astype(np.int64)  # (only what is near them: 4 mm cells next to theirs)
ckey = lambda c: (c[..., 0] + 1000) * 4000000 + (c[..., 1] + 1000) * 2000 + (c[..., 2] + 1000)
near_ = np.unique(np.concatenate([ckey(cell[fill_] + np.array(d) - 1) for d in np.ndindex(3, 3, 3)]))
near_ = cov & np.isin(ckey(cell), near_)
rgb = smooth3d(rgb, (near_ & ~fill_).astype(np.float32), BAKE_FILL[3] / 1000, 2, at=fill_)
print("the bake's fill colour: %d texels" % int(fill_.sum()))
# ... and the texels along thin faces (the next island's padding was there) the colour round them on the head
near_ = np.unique(np.concatenate([ckey(cell[thin_m] + np.array(d) - 1) for d in np.ndindex(3, 3, 3)]))
near_ = cov & ~thin_m & np.isin(ckey(cell), near_)
has_ = smooth3d(np.ones_like(rgb[..., :1]), near_.astype(np.float32), BAKE_FILL[3] / 1000, 2, at=thin_m)[..., 0] > 0.5
rgb = np.where((has_ & thin_m)[..., None], smooth3d(rgb, near_.astype(np.float32), BAKE_FILL[3] / 1000, 2, at=thin_m),
               rgb)  # (none near: the padding's as it was)


def in_outline(y, z, poly):
    """How far inside the polygon (m; negative outside) each point is."""
    P = np.array(poly, np.float32); Q = np.roll(P, -1, 0)
    inside = np.zeros(y.shape, bool); dist = np.full(y.shape, 1e9, np.float32)
    for (ay, az), (by, bz) in zip(P, Q):
        cross = (az > z) != (bz > z)
        yi = ay + (z - az) * (by - ay) / ((bz - az) if bz != az else 1e-9)
        inside ^= cross & (y < yi)
        ey, ez = by - ay, bz - az
        t = np.clip(((y - ay) * ey + (z - az) * ez) / (ey * ey + ez * ez), 0, 1)
        dist = np.minimum(dist, np.hypot(y - (ay + t * ey), z - (az + t * ez)))
    return np.where(inside, dist, -dist)


# 4. the ears, per texel
ear = np.zeros(pos.shape[:2], np.float32)
halo = []
for sg, poly in EAR.items():
    # the band behind the rim to EAR_BACK's outline: the ear where it faces back (the rim's back curling in), the head
    # where it faces out (hair: the portrait has none of his skin there)
    db = in_outline(pos[..., 1], pos[..., 2], EAR_BACK[sg])
    ear = np.maximum(ear, smoothstep(db, 0, EAR_EDGE) * smoothstep(tn[..., 1], 0.3, 0.6) * smoothstep(pos[..., 0] * sg, *EAR_X) * cov)
    din = in_outline(pos[..., 1], pos[..., 2], poly)
    ear = np.maximum(ear, smoothstep(din, 0, EAR_EDGE) * smoothstep(pos[..., 0] * sg, *EAR_X) * cov)
    ring = (smoothstep(-din, *EAR_HALO[:2]) * (1 - smoothstep(-din, *EAR_HALO[2:])) * (pos[..., 0] * sg > 0.05)
            * cov)
    halo.append(ring)
ear = ear[..., None]
print('ears: %d texels' % int((ear > 0.5).sum()))
L = rgb @ LUM
Lb = mat_util.blur(L, LIGHT_R)
skin = np.minimum(skin_tv, smoothstep(mat_util.blur(L, 3), *SKIN_L))
chroma = rgb / np.maximum(L, 1e-4)[..., None]
plain_rgb = np.median(rgb[cov & (pos[..., 2] < 1.76)], 0)  # the plain neck: the portrait's skin colour
plain = mat_util.blur((np.abs(rgb - plain_rgb).max(-1) < 0.012).astype(np.float32), 2)[..., None]

# 1. hue: green / grey casts to the skin's
gr, br = rgb[..., 1] / np.maximum(rgb[..., 0], 1e-4), rgb[..., 2] / np.maximum(rgb[..., 0], 1e-4)
cast = np.maximum(smoothstep(gr - SKIN_HUE[0], *GREEN[0]), smoothstep(br - SKIN_HUE[1], *GREEN[1]))
near_eye = np.zeros_like(L)
round_eye = np.zeros_like(L)
for e in EYE.values():
    de = np.linalg.norm(pos - e, axis=-1)
    near_eye = np.maximum(near_eye, 1 - smoothstep(de, EYE_KEEP, EYE_KEEP * 1.4))
    round_eye = np.maximum(round_eye, 1 - smoothstep(de, *EYE_NEAR))
bg = rgb[..., 2] / np.maximum(rgb[..., 1], 1e-4)
cast = np.maximum(cast, smoothstep(bg - SKIN_HUE[1] / SKIN_HUE[0], *PURPLE) * round_eye)
cast = (cast * skin * (1 - near_eye) * cov)[..., None]
skin_ch = np.array([1, SKIN_HUE[0], SKIN_HUE[1]], np.float32)
chroma = chroma + (skin_ch / float(skin_ch @ LUM) - chroma) * cast
# 3. his right side's hue to his left's
chroma = chroma * side_c
chroma = chroma / np.maximum(chroma @ LUM, 1e-4)[..., None]
print('hue: %d texels with a cast over 0.5' % int((cast[..., 0] > 0.5).sum()))

# 2. under the eyes
front = smoothstep(-tn[..., 1], 0.2, 0.5)
front_s = smoothstep(-tn[..., 1], -0.1, 0.25)  # (out by the eyes' outer corners the skin faces sideways)
gain = np.ones_like(L)
lines = np.zeros_like(L)
for s, e in EYE.items():
    dz = pos[..., 2] - e[2]
    d = np.sqrt(((pos[..., 0] - e[0]) / UNDER_EYE[1]) ** 2 + ((dz - UNDER_EYE[0]) / UNDER_EYE[2]) ** 2)
    w = ((1 - smoothstep(d, 0.65, 1.0)) * front_s * smoothstep(-dz, *UNDER_EYE_RIM)
         * skin_tv * cov)  # (skin by the mesh's, not the texel's light: the bags' painted rims are as dark as hair)
    ref = cov & (dz < UNDER_EYE_REF[0]) & (dz > UNDER_EYE_REF[1]) & (np.abs(pos[..., 0] - e[0]) < UNDER_EYE[1] * 0.7) \
        & (front > 0.5) & (skin > 0.9)
    lref = float(np.median(Lb[ref]))
    cref = np.median(chroma[ref], 0)
    gain = np.maximum(gain, 1 + (np.clip(lref / np.maximum(Lb, 1e-3), 1, LIFT_MAX) - 1) * w)
    chroma = chroma + (cref - chroma) * (w * UNDER_EYE_HUE)[..., None]
    lines = np.maximum(lines, w)
    sx = 1 if e[0] > mid_x else -1  # out from the nose
    di = np.sqrt((pos[..., 0] - (e[0] - sx * INNER[0])) ** 2 + (dz - INNER[1]) ** 2) / INNER[2]
    wi = (1 - smoothstep(di, 0.5, 1.0)) * front * skin * cov
    gain = np.maximum(gain, 1 + (np.clip(lref / np.maximum(Lb, 1e-3), 1, LIFT_MAX) - 1) * wi)
    lines = np.maximum(lines, wi * 0.5)
    print('under eye %s: cheek light %.3f, band light %.3f (median), %d texels' % (
        s, lref, float(np.median(Lb[w > 0.5])), int((w > 0.5).sum())))
# ... and their hue, lids to the cheeks, the face's
face = cov & (np.abs(pos[..., 0] - mid_x) < 0.05) & (pos[..., 2] > 1.90) & (pos[..., 2] < 1.95) & (front > 0.5) & (skin > 0.9)
face_ch = np.median(chroma[face], 0)
ut = UNDER_EYE_TINT
for s, e in EYE.items():
    dxo = (pos[..., 0] - e[0]) * (1 if e[0] > mid_x else -1)  # out from the nose
    dz = pos[..., 2] - e[2]
    wt = ((1 - smoothstep(dxo, *ut[0])) * (1 - smoothstep(-dxo, *ut[1])) * smoothstep(-dz, -ut[2][0], -ut[2][1])
          * (1 - smoothstep(-dz, -ut[3][0], -ut[3][1])) * front_s * skin_tv * cov)
    chroma = chroma + (face_ch - chroma) * wt[..., None]
    print('under eye %s: hue to the face %s, %d texels' % (s, np.round(face_ch, 3), int((wt > 0.5).sum())))
r_, k_ = UNDER_EYE_LINES
dark = np.maximum(mat_util.blur(L, r_) / np.maximum(L, 1e-3), 1)  # how much darker than round it
L = L * (1 + (dark - 1) * k_ * lines)
out = chroma * L[..., None]
# 2, 3. light
gain = np.clip(gain[..., None] * side_g, 1, LIFT_MAX)
out = out * gain
# (lifted past 1, the red would clip first and the colour turn yellow-green: the bags' painted light under the eyes,
# streaks like a fading bruise; brought back within 1 with its hue)
out = out / np.maximum(out.max(-1, keepdims=True), 1)
# ... the bags no lighter than the portrait's, a little under the cheek's light, a little redder (the fine light and
# dark kept)
lo6 = mat_util.blur(out @ LUM, LIGHT_R)
bag_tint = np.array(BAGS[3], np.float32); bag_tint = bag_tint / float(bag_tint @ LUM)
for s, e in EYE.items():
    dz, dxo = pos[..., 2] - e[2], (pos[..., 0] - e[0]) * (1 if e[0] > mid_x else -1)
    db = np.hypot((dz - BAGS[0][0]) / BAGS[1][0], (dxo - BAGS[0][1]) / BAGS[1][1])
    wb = (1 - smoothstep(db, 0.45, 1.0)) * front * skin * cov
    ref = cov & (dz < UNDER_EYE_REF[0]) & (dz > UNDER_EYE_REF[1]) & (np.abs(pos[..., 0] - e[0]) < UNDER_EYE[1] * 0.7)         & (front > 0.5) & (skin > 0.9)
    lc = float(np.median(lo6[ref]))
    k = np.clip(lc * BAGS[2] / np.maximum(lo6, 1e-4), 0.7, 1.0)
    out = out * (1 + (k - 1) * wb)[..., None] * (1 + (bag_tint - 1) * wb[..., None])
    print('the bags %s: no lighter than %.3f (the cheek %.3f), %d texels' % (s, lc * BAGS[2], lc, int((wb > 0.5).sum())))

# 2. between the eyes: the nose's sides and the sockets' upper inner corners to the bridge's colour with grain (the
# wrinkles are in the surface)
ez = (EYE['l'][2] + EYE['r'][2]) / 2
xl, xr = sorted((EYE['l'][0], EYE['r'][0]))
dzb = pos[..., 2] - ez
near = np.minimum(*(np.hypot((pos[..., 0] - e[0]) / BRIDGE_EYE[0], (pos[..., 2] - e[2]) / BRIDGE_EYE[1])
                    for e in EYE.values()))
bw = (smoothstep(pos[..., 0], xl + BRIDGE_X[0], xl + BRIDGE_X[1]) * (1 - smoothstep(pos[..., 0], xr - BRIDGE_X[1], xr - BRIDGE_X[0]))
      * smoothstep(dzb, *BRIDGE_Z[:2]) * (1 - smoothstep(dzb, *BRIDGE_Z[2:])) * smoothstep(near, *BRIDGE_EYE[2:])
      * smoothstep(-tn[..., 1], -0.3, 0.0) * cov)  # (the socket's wall by the nose faces the eye, sideways)
lo_ = out @ LUM
ridge = cov & (np.abs(pos[..., 0] - mid_x) < BRIDGE_REF[0]) & (dzb > BRIDGE_REF[1]) & (dzb < BRIDGE_REF[2]) & (tn[..., 1] < -0.5)
bridge_rgb = np.median(out[ridge], 0)
lb = mat_util.blur(lo_, 3)
tone = float(bridge_rgb @ LUM) * BRIDGE_TONE
bk = (bw * smoothstep(tone - mat_util.blur(lo_, 6), *BRIDGE_SHADE))[..., None]
detail = np.clip(lo_ / np.maximum(lb, 1e-4), *BRIDGE_DETAIL)[..., None]
skin_grain = (0.6 * vnoise(pos, 1 / 0.0015, 11) + 0.4 * vnoise(pos, 1 / 0.005, 23))[..., None]
out = out + (np.clip(bridge_rgb * BRIDGE_TONE * detail * (1 + BRIDGE_GRAIN * skin_grain), 0, 1) - out) * bk
lo_ = out @ LUM
sr = SPECK[2]
core = ((lo_ / np.maximum(mat_util.blur(lo_, sr), 1e-4) < SPECK[0]) & cov).astype(np.float32)
core *= (mat_util.blur(core, 3) < SPECK[1]) * (mat_util.blur(bw, 4) > 0.05) * (mat_util.blur(lo_, sr) > SKIN_L[0])
fleck = np.clip(mat_util.blur(core, 2) * 12, 0, 1)  # with its rim, 2 px round it
clear = (1 - fleck) * smoothstep(lo_, *SKIN_L)  # the skin round it (by the brow: not its hair)
fill = mat_util.blur(out * clear[..., None], sr) / np.maximum(mat_util.blur(clear, sr), 1e-4)[..., None]
out = out + (fill - out) * fleck[..., None]
print('between the eyes: %d texels of dark flecks' % int((fleck > 0.5).sum()))
print('between the eyes: to %s (sRGB), %d texels over half' % (np.round(bridge_rgb * 255), int((bk > 0.5).sum())))

# 2. the upper lids: one colour, a little lighter, to their inner ends (over what the bridge's fix left there: its
# colour stopped short at the lid's)
lo_ = out @ LUM
lid_light = smoothstep(mat_util.blur(lo_, 3), *LID_DARK)
lid_w, lid_med = {}, {}
for s, e in EYE.items():
    dx, dz = pos[..., 0] - e[0], pos[..., 2] - e[2]
    lo = LID_LO[0] * np.sqrt(np.clip(1 - (dx / LID_LO[1]) ** 2, 0, 1))
    hi = LID_HI[0] * np.sqrt(np.clip(1 - (dx / LID_HI[1]) ** 2, 0, 1))
    lid_w[s] = (smoothstep(dz - lo, -LID_FADE[0], 0) * (1 - smoothstep(dz - hi, -LID_FADE[1], 0))
                * (1 - smoothstep(np.abs(dx), LID_HI[1] - 0.003, LID_HI[1])) * (hi > lo) * cov)
    out_side = (dx * (1 if e[0] > mid_x else -1)) > -0.004  # the middle and outer part: the bridge's fix not there
    lid_med[s] = np.median(out[(lid_w[s] > 0.9) & (lid_light > 0.9) & out_side], 0)
ch = np.mean([c / float(c @ LUM) for c in lid_med.values()], 0)
l0 = np.mean([float(c @ LUM) for c in lid_med.values()])
lid_rgb = ch * (l0 + (tone - l0) * LID_LIGHT)
detail = np.clip(lo_ / np.maximum(mat_util.blur(lo_, 3), 1e-4), *LID_DETAIL)[..., None]
lidk = np.zeros_like(lo_)
for s in EYE:
    k = (lid_w[s] * lid_light)[..., None]
    out = out + (np.clip(lid_rgb * detail * (1 + BRIDGE_GRAIN * skin_grain), 0, 1) - out) * k
    lidk = np.maximum(lidk, k[..., 0])
    print('upper lid %s: %s -> %s (sRGB)' % (s, np.round(lid_med[s] * 255), np.round(lid_rgb * 255)))
# ... their inner ends a little darker and redder, on into the socket's corner
tint = np.array(LID_INNER_TONE[1], np.float32)
tint = LID_INNER_TONE[0] * tint / float(tint @ LUM)
for s, e in EYE.items():
    dxi, dz = (e[0] - pos[..., 0]) * (1 if e[0] > mid_x else -1), pos[..., 2] - e[2]  # towards the nose
    wi = (smoothstep(dxi, *LID_INNER[:2]) * (1 - smoothstep(dxi, *LID_INNER[2:]))
          * smoothstep(dz, *LID_INNER_Z[:2]) * (1 - smoothstep(dz, *LID_INNER_Z[2:])) * cov)[..., None]
    out = out * (1 + (tint - 1) * wi)
    lidk = np.maximum(lidk, wi[..., 0])

# ... and past their outer corners the portrait's shade lifted to the skin round it (not the lash line: the corner
# itself is inside the eyeball's radius)
lo_ = out @ LUM
lb = mat_util.blur(lo_, LIGHT_R)
detail = np.clip(lo_ / np.maximum(mat_util.blur(lo_, 3), 1e-4), *CORNER_DETAIL)[..., None]
corner_w = np.zeros_like(lo_)  # (skin there: not the hair's pale strips, 11 - dark, the shade had read as hair)
for s, e in EYE.items():
    dxo, dz = (pos[..., 0] - e[0]) * (1 if e[0] > mid_x else -1), pos[..., 2] - e[2]
    front = pos[..., 1] < e[1] + CORNER[2]
    wc = (smoothstep(dxo, *CORNER[0][:2]) * (1 - smoothstep(dxo, *CORNER[0][2:]))
          * smoothstep(dz, *CORNER[1][:2]) * (1 - smoothstep(dz, *CORNER[1][2:])) * front * cov)
    (rx0, rx1), under_, over_ = CORNER_REF
    ref = (cov & front & (dxo > rx0) & (dxo < rx1) & (lo_ > SKIN_L[1])
           & (((dz > under_[0]) & (dz < under_[1])) | ((dz > over_[0]) & (dz < over_[1]))))
    ref_c = np.median(out[ref], 0)
    ref_l = float(ref_c @ LUM)
    k = (wc * smoothstep(ref_l - lb, *CORNER_DARK))[..., None]
    corner_w = np.maximum(corner_w, wc)
    out = out + (np.clip(ref_c * detail * (1 + PLAIN_GRAIN * skin_grain), 0, 1) - out) * k
    print('outer corner %s: skin round it %s (sRGB, L %.2f), %d texels lifted over half' % (
        s, np.round(ref_c * 255), ref_l, int((k[..., 0] > 0.5).sum())))


# his left eye's lash lines as his right eye's: by the height over the upper lid's edge (the lowest of its skin on
# the eyeball, per 0.5 mm across) and under the lower one's
def lid_edges(e):
    r = float(np.median(np.linalg.norm(ec[ec[:, 0] > mid_x if e[0] > mid_x else ec[:, 0] <= mid_x] - e, axis=1)))
    d = (np.linalg.norm(pos - e, axis=-1) - r) * 1000
    dz, dx = (pos[..., 2] - e[2]) * 1000, (pos[..., 0] - e[0]) * 1000
    on = cov & (d > -0.3) & (d < 1.0) & (tn[..., 1] < -0.3) & (np.abs(dx) < 16)
    col = np.round(dx / 0.5).astype(int)
    up, lo = np.full(69, np.nan), np.full(69, np.nan)
    for c_ in range(-34, 35):
        m_ = on & (col == c_)
        if (m_ & (dz > 0.5)).any():
            up[c_ + 34] = dz[m_ & (dz > 0.5)].min()
        if (m_ & (dz < -0.5)).any():
            lo[c_ + 34] = dz[m_ & (dz < -0.5)].max()
    xs_ = np.arange(-34, 35) * 0.5
    fill = lambda a: np.interp(xs_, xs_[~np.isnan(a)], a[~np.isnan(a)])
    up_e, lo_e = np.interp(dx, xs_, fill(up)), np.interp(dx, xs_, fill(lo))
    return dz - up_e, lo_e - dz, dx, d
prof = {}
du, dl, dxr, dr = lid_edges(EYE['r'])
bins_ = np.arange(0, 1.81, 0.3)
for nm, dd in (('upper', du), ('lower', dl)):
    prof[nm] = []
    for a_, b_ in zip(bins_[:-1], bins_[1:]):
        m_ = cov & (dd >= a_) & (dd < b_) & (np.abs(dxr) < 9) & (dr < 2.5) & (tn[..., 1] < -0.3)
        prof[nm].append(np.median(out[m_], 0) if m_.sum() > 5 else None)
du, dl, dxl, dl_ = lid_edges(EYE['l'])
lash_k = np.zeros_like(L)
for nm, dd, (a_, b_) in (('upper', du, LASH[:2]), ('lower', dl, LASH[2:])):
    cols = [c for c in prof[nm] if c is not None]
    mids = [(x + 0.15) for x, c in zip(bins_[:-1], prof[nm]) if c is not None]
    tgt = np.stack([np.interp(dd, mids, [c[j] for c in cols]) for j in range(3)], -1)
    wk = ((1 - smoothstep(dd, a_, b_)) * (dd > -0.3) * (1 - smoothstep(np.abs(dxl), 12, 15)) * (dl_ < 2.5)
          * (tn[..., 1] < -0.2) * cov)
    wk = wk * ((out @ LUM) > (tgt @ LUM))  # (only where lighter than his right eye's)
    out = out + (tgt - out) * wk[..., None]
    lash_k = np.maximum(lash_k, wk)
    print("his left eye's %s lash line: %s (sRGB, by the edge) on %d texels" % (nm, np.round(cols[0] * 255), int((wk > 0.5).sum())))

# the blink's Eyelids: one colour each, off a texel by its edge and one over it (build_skin.py); shut, both lids that
# colour and their edges one lash colour
with bpy.data.libraries.load(LEADER) as (src, dst):
    dst.meshes = [m for m in src.meshes if m == 'Eyelids']
if dst.meshes:
    lm = dst.meshes[0]
    luv = np.zeros(len(lm.loops) * 2, np.float32); lm.uv_layers[0].data.foreach_get('uv', luv)
    spots = np.unique(np.round(luv.reshape(-1, 2) * TEX - 0.5, 1), axis=0)  # texel coordinates (x, y)
    yy, xx = np.mgrid[0:TEX, 0:TEX]
    lo_ = out @ LUM
    found = []
    for x, y in spots:
        iy, ix = int(round(y)), int(round(x))
        found.append((x, y, pos[iy, ix, 0] > mid_x, float(mat_util.blur(lo_, 2)[iy, ix])))
    edges = [f for f in found if f[3] < np.median([g[3] for g in found])]
    lash_rgb = np.mean([out[int(round(f[1])), int(round(f[0]))] for f in edges], 0)
    for x, y, left, l in found:
        k = (1 - smoothstep(np.hypot(xx - x, yy - y), *SHUT_R))[..., None]
        out = out + ((lash_rgb if (x, y, left, l) in edges else lid_rgb) - out) * k
    print("the blink's lids: skin %s, edges %s (sRGB), off %d texels" % (
        np.round(lid_rgb * 255), np.round(lash_rgb * 255), len(found)))

# 5. the shade under the chin's front: the chin's colour, the fine light and dark kept
cx = np.abs(pos[..., 0] - mid_x)
cf = cov & (pos[..., 1] < -0.06) & (tn[..., 2] > -0.7)
chin_w = (smoothstep(pos[..., 2], CHIN[0], CHIN[1]) * (1 - smoothstep(pos[..., 2], CHIN[2], CHIN[3]))
          * (1 - smoothstep(cx, *CHIN_X)) * smoothstep(mat_util.blur(L, 3), *CHIN_HAIR) * cf)[..., None]
chin_rgb = np.median(rgb[cf & (cx < 0.035) & (pos[..., 2] > CHIN_REF[0]) & (pos[..., 2] < CHIN_REF[1])], 0)
lo_ = out @ LUM
detail = np.clip(lo_ / np.maximum(mat_util.blur(lo_, 3), 1e-4), *CHIN_DETAIL)[..., None]
out = out + (np.clip(chin_rgb * detail, 0, 1) - out) * chin_w
print('chin: to %s (sRGB), %d texels' % (np.round(chin_rgb * 255), int((chin_w > 0.5).sum())))

hairw = 1 - smoothstep(mat_util.blur(rgb @ LUM, 3), *HAIR_L)  # the hair (and the brows' and the beard's) by the base


def detail_of(a, lo, hi):
    l_ = a @ LUM
    return np.clip(l_ / np.maximum(mat_util.blur(l_, 3), 1e-4), lo, hi)[..., None]


# 6. round the nose's underside: the colour averaged in space, the fine light and dark kept; the nostrils (shallow dips
# in the mesh) their own dark
dxm = pos[..., 0] - mid_x
skin_l = 1 - hairw
dn = np.sqrt((dxm / NOSE[1][0]) ** 2 + ((pos[..., 1] - NOSE[0][0]) / NOSE[1][1]) ** 2
             + ((pos[..., 2] - NOSE[0][1]) / NOSE[1][2]) ** 2)
nz = (1 - smoothstep(dn, NOSE[2], 1.0)) * cov
for sg in (-1, 1):
    dc = np.linalg.norm(pos - np.array([mid_x + sg * NOSE_CREASE[0][0], *NOSE_CREASE[0][1:]]), axis=-1) / NOSE_CREASE[1]
    nz = np.maximum(nz, (1 - smoothstep(dc, 0.6, 1.0)) * cov)
# (the nose's own underside is skin however dark the portrait's smudge on it: what faces down over the moustache)
skin_l = np.maximum(skin_l, np.maximum(smoothstep(-tn[..., 2], 0.25, 0.5) * smoothstep(pos[..., 2], *NOSE_OVER[:2]),
                                       smoothstep(pos[..., 2], *NOSE_OVER[2:])) * (nz > 0))
lo_ = mat_util.blur(out @ LUM, 3)
fr = (dn < 1.0) & cov & (skin_l > 0.9) & (tn[..., 1] < -0.5)  # (its front: the portrait's light)
l_nose = float(np.median(lo_[fr]))
lit = smoothstep(lo_ / l_nose, *NOSE_LIT)  # (the averaged colour only the skin's in the light, not its painted shade)
nose_rgb = np.median(out[fr & (lit > 0.9)], 0)
avg = smooth3d(out, (dn < 1.3) * cov * skin_l * lit, NOSE_SMOOTH[0] / 1000, NOSE_SMOOTH[1], (nose_rgb, 0.3), nz > 0)
grain_n = (0.6 * vnoise(pos, 1 / 0.0015, 11) + 0.4 * vnoise(pos, 1 / 0.005, 23))[..., None]
full_n = avg * detail_of(out, *NOSE_DETAIL) * (1 + BRIDGE_GRAIN * grain_n)
# (its front: the averaged hue, the light only partly - the portrait's light and shade on it kept)
l_o, l_a = out @ LUM, full_n @ LUM
hue_n = full_n / np.maximum(l_a, 1e-4)[..., None] * (l_o + (l_a - l_o) * NOSE_FRONT[2])[..., None]
nf = (smoothstep(-tn[..., 1], *NOSE_FRONT[:2]) * (pos[..., 2] > NOSE_OVER[1]))[..., None]
n_own = np.maximum(smoothstep(pos[..., 2], *NOSE_UNDER[:2]), smoothstep(-tn[..., 2], *NOSE_UNDER[2]))  # (not the
# moustache's top under it)
out = out + (np.clip(full_n * (1 - nf) + hue_n * nf, 0, 1) - out) * (nz * skin_l * n_own)[..., None]
uw = (nz * smoothstep(-tn[..., 2], 0.15, 0.4)).astype(np.float32)  # (facing down)
nw = np.zeros_like(uw); nd = np.full_like(uw, 9.0)
for sg in (-1, 1):
    a_ = math.radians(NOSTRIL[3])
    u = np.array([sg * math.sin(a_), math.cos(a_)]); v = np.array([math.cos(a_), -sg * math.sin(a_)])
    dp = np.stack([dxm - sg * NOSTRIL[0], pos[..., 1] - NOSTRIL[1]], -1) * 1000
    d = np.hypot((dp @ u) / NOSTRIL[2][0], (dp @ v) / NOSTRIL[2][1])
    nw = np.maximum(nw, (1 - smoothstep(d, 1 - NOSTRIL[4] / NOSTRIL[2][1], 1)) * uw)
    nd = np.minimum(nd, d)
n_in, n_out = (np.array(c, np.float32) / 255 for c in NOSTRIL_SRGB)
nostril = n_in + (n_out - n_in) * smoothstep(nd, 0.2, 1.0)[..., None]
out = out + (np.clip(nostril * (1 + BRIDGE_GRAIN * grain_n), 0, 1) - out) * nw[..., None]
print('round the nose: %d texels averaged (to %s sRGB where none of them light, the front light %.3f); nostrils %d texels' % (
    int((nz * skin_l > 0.5).sum()), np.round(nose_rgb * 255), l_nose, int((nw > 0.5).sum())))

# 7. the lower lip the portrait's lip colour, under its edge the chin's, modelled as the portrait's (lit on top, darker
# to its edge, the shade under it); the upper lip's underside and the upper lip in the moustache's gap darker than the
# lower lip, their detail kept; the mouth's line a crisp dark stroke
adx = np.abs(dxm)
front_l = smoothstep(-tn[..., 1], 0.1, 0.35)
lb = LOWER_LIP
mouth = LIP[3][0] - LIP[3][1] * smoothstep(adx, *LIP[3][2])
border = mouth - lb[0] + (lb[0] - lb[1]) * smoothstep(adx, *lb[2])
wl = ((1 - smoothstep(pos[..., 2], border - lb[3], border + lb[3])) * smoothstep(pos[..., 2], lb[5], lb[5] + 0.003)
      * (1 - smoothstep(adx, *lb[4])) * (pos[..., 1] < -0.10) * skin_tv * cov)  # (skin by the mesh's: the portrait's
# shade there is as dark as hair)
chin_u = cov & (adx < 0.015) & (pos[..., 2] > lb[5] - 0.008) & (pos[..., 2] < lb[5]) & (tn[..., 1] < -0.3) & (skin_l > 0.9)
under_rgb = np.median(out[chin_u], 0)
out = out + (np.clip(under_rgb * detail_of(out, 0.95, 1.05), 0, 1) - out) * wl[..., None]
lip_rgb = np.array(LIP[0], np.float32) / 255
wlip = (smoothstep(pos[..., 2], border - lb[3], border + lb[3]) * (1 - smoothstep(pos[..., 2], mouth - 0.0008, mouth))
        * (1 - smoothstep(adx, *lb[4])) * (pos[..., 1] < -0.10)
        * smoothstep(mat_util.blur(rgb @ LUM, 3), *LIP[4]) * cov)
out = out + (np.clip(lip_rgb * detail_of(out, *LIP[2]), 0, 1) - out) * (wlip * LIP[1])[..., None]
edge_l = (wlip * (1 - smoothstep(pos[..., 2], border + LIP_EDGE[0], border + LIP_EDGE[0] + 0.0004)))[..., None]
out = out * (1 - (1 - LIP_EDGE[1]) * edge_l)
# the lip's light and shade (the user's call: small relief the mesh lacks, as the portrait has it)
ls_, l_top, l_bot = LIP_SHADE
f_up = np.clip((pos[..., 2] - border) / np.maximum(mouth - border, 1e-4), 0, 1)  # 0 at the lip's edge, 1 at the mouth
lit = np.array(l_bot, np.float32) + (l_top - np.array(l_bot, np.float32)) * smoothstep(f_up, 0.0, 1.0 - ls_)[..., None]
lip_w = (smoothstep(pos[..., 2], border - 0.0002, border + 0.0002) * (1 - smoothstep(pos[..., 2], mouth - 0.0006, mouth))
         * (1 - smoothstep(adx, *lb[4])) * (pos[..., 1] < -0.10) * cov)
out = out * (1 + (lit - 1) * lip_w[..., None])
ud = UNDER_LIP[0] + (UNDER_LIP[1] - UNDER_LIP[0]) * smoothstep(adx, *lb[2])
under = (1 - smoothstep(pos[..., 2], border - 0.0002, border + 0.0002)) * (
    np.clip(1 - (border - pos[..., 2]) / ud, 0, 1) ** 0.8) * (1 - smoothstep(adx, *lb[4])) * (pos[..., 1] < -0.10) * cov
fac = np.array(UNDER_LIP[2], np.float32)
out = out * (1 + (fac - 1) * under[..., None])
print('the lip modelled: %d texels lit and shaded, %d shaded under it' % (int((lip_w > 0.5).sum()), int((under > 0.3).sum())))
lo_ = out @ LUM
rim = (cov * smoothstep(pos[..., 2], mouth - MOUTH_RIM[0], mouth - MOUTH_RIM[0] + 0.0005)
       * (1 - smoothstep(pos[..., 2], mouth + MOUTH_RIM[1] - 0.0005, mouth + MOUTH_RIM[1]))
       * smoothstep(-tn[..., 2], MOUTH_RIM[2], MOUTH_RIM[2] + 0.15) * (1 - smoothstep(adx, *lb[4])) * (pos[..., 1] < -0.10)
       * smoothstep(mat_util.blur(rgb @ LUM, 3), *LIP[4]))
l_lip = float(lip_rgb @ LUM)
out = out + (np.clip(lip_rgb * MOUTH_RIM[3] * detail_of(out, *LIP[2]), 0, 1) - out) * rim[..., None]
print('the lower lip: to %s, under it to %s (sRGB), %d / %d texels; the upper one\'s underside %d texels' % (
    LIP[0], np.round(under_rgb * 255), int((wlip > 0.5).sum()), int((wl > 0.5).sum()), int((rim > 0.5).sum())))
lo_ = out @ LUM
lower = cov & (adx < UPPER_GAP[2][0]) & (pos[..., 2] > UPPER_GAP[2][1][0]) & (pos[..., 2] < UPPER_GAP[2][1][1]) & (front_l > 0.5) & (skin_l > 0.9)
lip_l = float(np.median(lo_[lower]))
wg = (cov * (1 - smoothstep(adx, UPPER_GAP[0] * 0.7, UPPER_GAP[0])) * smoothstep(pos[..., 2], UPPER_GAP[1][0], UPPER_GAP[1][0] + 0.002)
      * (1 - smoothstep(pos[..., 2], UPPER_GAP[1][1] - 0.002, UPPER_GAP[1][1])) * skin_l * front_l)
cap = np.minimum(lip_l * UPPER_GAP_CAP / np.maximum(mat_util.blur(lo_, 3), 1e-4), 1)
out = out * (1 + (cap - 1) * wg)[..., None]
lip_hue = lip_rgb / l_lip  # (and half way to the lip's hue: the portrait's light on it was white)
out = out + (np.clip(lip_hue * (out @ LUM)[..., None], 0, 1) - out) * (wg * UPPER_GAP_HUE)[..., None]
print('the upper lip in the gap: no lighter than %.3f (the lower lip times %.2f), %d texels' % (
    lip_l, UPPER_GAP_CAP, int((wg * (cap < 0.97) > 0.5).sum())))
ml = MOUTH_LINE
k_l = mat_util.blur(out @ LUM, 1) / l_lip
wm = (cov * (1 - smoothstep(np.abs(pos[..., 2] - mouth), ml[0] * 0.7, ml[0])) * (1 - smoothstep(adx, *ml[1]))
      * (pos[..., 1] < -0.10) * smoothstep(k_l, *ml[4]) * (1 - smoothstep(k_l, *ml[2])))
out = out + (np.clip(lip_rgb * ml[3] * detail_of(out, 0.92, 1.08), 0, 1) - out) * wm[..., None]
print("the mouth's line: %d texels to %s sRGB" % (int((wm > 0.5).sum()), np.round(lip_rgb * ml[3] * 255)))

# 8. under the brows: the fold over each lid (where the face steps out most steeply going up) and the overhang's
# underside over it: the lids' colour, the skin's hue, the fine light and dark kept
tree = BVHTree.FromPolygons([Vector(q) for q in co], [tuple(p.vertices) for p in me.polygons])
roof = np.zeros_like(L)
for s_, e in EYE.items():
    sx = 1 if e[0] > mid_x else -1
    fx = np.arange(-ROOF[2], ROOF[2] + 0.1, 1.0)
    zs = np.arange(6.0, 26.0, 0.25)
    folds = []
    for dx in fx:
        dd = []
        for z in zs:
            hit = tree.ray_cast(Vector((e[0] + sx * dx / 1000, -0.5, e[2] + z / 1000)), Vector((0, 1, 0)), 1.0)
            dd.append(hit[0].y if hit[0] is not None else np.nan)
        step = -np.gradient(np.nan_to_num(np.array(dd) - e[1], nan=0.0)) / 0.25
        folds.append(zs[int(np.argmax(step))])
    folds = np.convolve(np.pad(np.array(folds), 3, mode='edge'), np.ones(7) / 7, 'valid')
    dxo = (pos[..., 0] - e[0]) * sx * 1000
    dz = (pos[..., 2] - e[2]) * 1000
    f = np.interp(dxo, fx, folds)
    wr = (smoothstep(dz, f - ROOF[0] - 1.0, f - ROOF[0]) * (1 - smoothstep(dz, f + ROOF[1] - 1.0, f + ROOF[1]))
          * np.where(dz > f, smoothstep(-tn[..., 2], 0.0, 0.3), 1.0) * (1 - smoothstep(np.abs(dxo), ROOF[2] - 4, ROOF[2]))
          * (pos[..., 1] < e[1]) * cov)
    roof = np.maximum(roof, wr)
    print('under the brow %s: fold %.1f..%.1f mm over the eyeball middle' % (s_, folds.min(), folds.max()))
lo_ = out @ LUM
rt = float(lid_rgb @ LUM) * ROOF_TONE
rk = mat_util.blur(roof, 3) * smoothstep(rt - mat_util.blur(lo_, 8), -0.08, 0.0)  # (by the 3 px light: islands)
out = out + (np.clip(lid_rgb * ROOF_TONE * detail_of(out, *BRIDGE_DETAIL) * (1 + BRIDGE_GRAIN * skin_grain), 0, 1) - out) * rk[..., None]
gr_ = out[..., 1] / np.maximum(out[..., 0], 1e-4)
gcast = roof * smoothstep(gr_ - SKIN_HUE[0], *GREEN[0])  # the grey-green there whatever its light (it was dark)
ch_ = out / np.maximum(out @ LUM, 1e-4)[..., None]
out = (ch_ + (skin_ch / float(skin_ch @ LUM) - ch_) * gcast[..., None]) * (out @ LUM)[..., None]
print('under the brows: %d texels lifted, %d with a green cast' % (int((rk > 0.5).sum()), int((gcast > 0.5).sum())))

# 4. the ears (a warmer bowl, a paler rim, blotches; the light from the mesh); 5. the plain skin's grain
grain = skin_grain
ear_rgb = plain_rgb * np.array(EAR_TINT) * (1 + EAR_GRAIN * grain + EAR_MOTTLE[1] * vnoise(pos, 1 / EAR_MOTTLE[0], 37)[..., None])
red = np.array(EAR_RED[1], np.float32); red = red / float(red @ LUM)
ax = np.abs(pos[..., 0])
for sg in (1, -1):
    m_ = (ear[..., 0] > 0.5) & (pos[..., 0] * sg > 0)
    if m_.any():
        rim = float(np.percentile(ax[m_], 97))
        kr = (smoothstep(rim - ax, 0.0, EAR_RED[0]) * (pos[..., 0] * sg > 0))[..., None]
        ear_rgb = ear_rgb * (1 + (red - 1) * kr)
out = out + (np.clip(ear_rgb, 0, 1) - out) * ear


def strand_pattern(c, a, seed):
    """Strands across c (m), waving a little along a (m): -1..1."""
    rng = np.random.default_rng(seed)
    t = np.zeros_like(c)
    for f, w in STRANDS:
        ph = rng.uniform(0, 2 * np.pi)
        t += w * np.sin(2 * np.pi * c * f + ph + 1.2 * np.sin(2 * np.pi * a * 35 + ph))
    return t / sum(w for _, w in STRANDS)


# hair combed down the sides (round a vertical axis through the head), the beard's underside out from the chin
side_strands = strand_pattern(np.arctan2(pos[..., 0] - mid_x, pos[..., 1]) * 0.09, pos[..., 2], 5)
beard_strands = strand_pattern(np.arctan2(pos[..., 0] - mid_x, pos[..., 1] + 0.075) * 0.06,
                               np.hypot(pos[..., 0] - mid_x, pos[..., 1] + 0.075), 9)
Lo = out @ LUM
hair_ref = np.median(out[(hairw > 0.9) & cov & (np.abs(pos[..., 0] - mid_x) > 0.05) & (pos[..., 2] > 1.86)
                         & (pos[..., 2] < 1.95) & (tn[..., 1] < -0.2)], 0)
# the skin colour on the hair round the ears to the hair's there, with strands
light = smoothstep(mat_util.blur(Lo, 3), *HALO_SKIN)
for ring in halo:
    k = (ring * light)[..., None]
    out = out + (np.clip(hair_ref * (1 + STRAND_CONTRAST * side_strands[..., None]), 0, 1) - out) * k
    print('round an ear: %d texels of skin colour to the hair %s (sRGB)' % (int((k > 0.5).sum()), np.round(hair_ref * 255)))
# 10. the beard's underside: strands over its plain colour
bu = (cov * (pos[..., 2] < BEARD_UNDER[0]) * smoothstep(-tn[..., 2], BEARD_UNDER[1], BEARD_UNDER[1] + 0.2) * hairw
      * (np.abs(pos[..., 0] - mid_x) > 0.0) * (1 - ear[..., 0]))
clumps = vnoise(pos * np.array([1.0, 1.0, 0.4]), 1 / BEARD_UNDER[3][0], 41)  # (longer down the beard)
out = out * (1 + (BEARD_UNDER[2] * beard_strands + BEARD_UNDER[3][1] * clumps) * bu)[..., None]
print("the beard's underside: strands on %d texels" % int((bu > 0.5).sum()))
# 11. skin-coloured strips in the whiskers to the hair's colour, with strands; dark flecks on the skin by the hair's
# edge and pale ones in the hair to what is round them
Lo = out @ LUM
lat = smoothstep(np.abs(pos[..., 0] - mid_x), 0.045, 0.06) * cov * (pos[..., 2] < 2.0) * (1 - ear[..., 0])
round_hair = mat_util.blur(hairw, 6)
rg = out[..., 0] / np.maximum(out[..., 1], 1e-4)
beard_zone = (smoothstep(pos[..., 2], *BEARD_ZONE[0]) * (1 - smoothstep(pos[..., 2], *BEARD_ZONE[1]))
              * smoothstep(np.abs(pos[..., 0] - mid_x), *BEARD_ZONE[2]) * smoothstep(pos[..., 1], *BEARD_ZONE[3]))
round_need = STREAK[2] * (1 - beard_zone)  # (in the beard under the ears all of it is hair: wide strips there too)
streak = (lat * smoothstep(Lo / np.maximum(float(hair_ref @ LUM), 1e-4), STREAK[0], STREAK[0] + 0.3)
          * smoothstep(rg, STREAK[1], STREAK[1] + 0.1)
          * np.maximum(smoothstep(round_hair, round_need, round_need + 0.2), beard_zone))  # (a small island all skin
# colour there has no hair round it in the atlas)
streak = np.clip(mat_util.blur(streak, 2) * 1.5, 0, 1) * (1 - corner_w)
out = out + (np.clip(hair_ref * (1 + STRAND_CONTRAST * side_strands[..., None]), 0, 1) - out) * streak[..., None]
# 13. his left sideburn in front of the ear: his right one's hair, mirrored (nearest texel, the x's offset counting less:
# the two sides are not alike in depth)
sb = SIDEBURN
ws_ = (smoothstep(pos[..., 1], *sb[0]) * (1 - smoothstep(pos[..., 1], *sb[1])) * smoothstep(pos[..., 2], *sb[2])
       * (1 - smoothstep(pos[..., 2], *sb[3])) * (pos[..., 0] - mid_x > sb[4]) * (1 - ear[..., 0]) * cov)
pale_ = smoothstep(mat_util.blur(out @ LUM, 2) / float(hair_ref @ LUM), *SIDEBURN_PALE[:2])
ws_ = ws_ * (SIDEBURN_PALE[2] + (1 - SIDEBURN_PALE[2]) * pale_)  # (his left's own hair mostly kept: the right one's is
# darker at the top, a black patch)
src =(cov & (mid_x - pos[..., 0] > sb[4] - 0.01) & (pos[..., 1] > sb[0][0] - 0.006) & (pos[..., 1] < sb[1][1] + 0.006)
       & (pos[..., 2] > sb[2][0] - 0.006) & (pos[..., 2] < sb[3][1] + 0.006))
hair_src = 1 - smoothstep(mat_util.blur(out @ LUM, 2) / float(hair_ref @ LUM), *SIDEBURN_PALE[:2])
sy, sx_ = np.nonzero(src)
kd_s = KDTree(len(sy))
for i, (yy_, xx_) in enumerate(zip(sy, sx_)):
    p_ = pos[yy_, xx_]
    kd_s.insert((p_[0] * 0.3, p_[1], p_[2]), i)
kd_s.balance()
ty, tx_ = np.nonzero(ws_ > 0)
for yy_, xx_ in zip(ty, tx_):
    p_ = pos[yy_, xx_]
    j = kd_s.find(((2 * mid_x - p_[0]) * 0.3, p_[1], p_[2]))[1]
    k_ = ws_[yy_, xx_] * hair_src[sy[j], sx_[j]]  # (not the cheek's skin where his right one ends sooner)
    out[yy_, xx_] += (out[sy[j], sx_[j]] - out[yy_, xx_]) * k_
print('his left sideburn: %d texels of his right one\'s hair' % int((ws_ > 0.5).sum()))
Lo = out @ LUM
sr2 = SPECK2[2]
Lm = mat_util.blur(Lo, sr2)
skinny = mat_util.blur(1 - hairw, 4)
dark_f = (Lo / np.maximum(Lm, 1e-4) < SPECK2[0]) & (skinny > 0.6)
pale_f = (Lo / np.maximum(Lm, 1e-4) > SPECK2[1]) & (round_hair > 0.6)
zone_f = (lat > 0.5) | (mat_util.blur(ear[..., 0], 4) > 0.05)  # (and on the ears and round them)
fl = np.clip(mat_util.blur(((dark_f | pale_f) & zone_f).astype(np.float32), 2) * 6, 0, 1)
fl = fl * (1 - ear[..., 0])  # (never on the ears: their small islands' neighbours in the atlas are the hair's)
keep_ = (1 - fl) * cov  # (not the atlas's empty texels: the bake's black)
fl = fl * smoothstep(mat_util.blur(keep_, sr2), 0.05, 0.2)  # (nothing kept round it - a lone texel of a sliver: as it is)
fill2 = mat_util.blur(out * keep_[..., None], sr2) / np.maximum(mat_util.blur(keep_, sr2), 1e-4)[..., None]
out = out + (fill2 - out) * fl[..., None]
print('whiskers: %d texels of skin-coloured strips to the hair; %d of flecks filled' % (
    int((streak > 0.5).sum()), int((fl > 0.5).sum())))
# 14. the hair's edge drawn again in its zones: the skin's share (by the light) averaged in space, the new edge where
# that crosses half; either side its own colour averaged the same way, the fine light and dark kept
def _box(v, e):
    return smoothstep(v, e[0], e[1]) * (1 - smoothstep(v, e[2], e[3]))


zw = np.zeros_like(L)
for ex, ey, ez in EDGES:
    zw = np.maximum(zw, _box(dxm, ex) * _box(pos[..., 1], ey) * _box(pos[..., 2], ez) * cov)
zone = zw > 0
sk = smoothstep(mat_util.blur(out @ LUM, 1), *HAIR_L)
vox = EDGE_SMOOTH[0] / 1000
s3 = smooth3d(sk[..., None], zone.astype(np.float32), vox, EDGE_SMOOTH[1])[..., 0]
skin_avg = smooth3d(out, (zone & (sk > 0.9)).astype(np.float32), vox, EDGE_SMOOTH[2], (plain_rgb, 0.05), zone)
hair_avg = smooth3d(out, (zone & (sk < 0.1)).astype(np.float32), vox, EDGE_SMOOTH[2], (hair_ref, 0.05), zone)
s_new = smoothstep(s3, *EDGE_BAND[2])[..., None]
redrawn = np.clip((skin_avg * s_new + hair_avg * (1 - s_new)) * detail_of(out, *EDGE_DETAIL), 0, 1)
bw = zw * smoothstep(s3, *EDGE_BAND[0]) * (1 - smoothstep(s3, *EDGE_BAND[1]))
s3w = smooth3d(sk[..., None], zone.astype(np.float32), vox, EDGE_SKIN[0])[..., 0]
bw = np.maximum(bw, zw * smoothstep(s3, 0.5, 0.8) * (1 - smoothstep(s3w, *EDGE_SKIN[1])))
out = out + (redrawn - out) * bw[..., None]
print("the hair's edge redrawn: %d texels" % int((bw > 0.5).sum()))
# 16. ... and on his right temple his left one's edge: the texel at the same height and as far from the edge
te = TEMPLE_EDGE
side_z = _box(pos[..., 1], EDGES[0][1]) * _box(pos[..., 2], te[0]) * cov * (1 - ear[..., 0])
zr, zl = _box(dxm, EDGES[0][0]) * side_z, _box(-dxm, EDGES[0][0]) * side_z
both = (zr > 0) | (zl > 0)
sk_f = smoothstep(mat_util.blur(out @ LUM, 1), *HAIR_L)
s_far = smooth3d(sk_f[..., None], both.astype(np.float32), te[1][0] / 1000, te[1][1])[..., 0]
band = zr * _box(s_far, te[2])
sy, sx_ = np.nonzero((zl > 0.5) & (s_far > 0) & (s_far < 1))
kd_s = KDTree(len(sy))
for i, (yy_, xx_) in enumerate(zip(sy, sx_)):
    kd_s.insert((pos[yy_, xx_, 2], s_far[yy_, xx_] * te[3], pos[yy_, xx_, 1] * te[4]), i)
kd_s.balance()
ty, tx_ = np.nonzero(band > 0)
took = out.copy()
for yy_, xx_ in zip(ty, tx_):
    j = kd_s.find((pos[yy_, xx_, 2], s_far[yy_, xx_] * te[3], pos[yy_, xx_, 1] * te[4]))[1]
    took[yy_, xx_] = out[sy[j], sx_[j]]
out = out + (took - out) * band[..., None]
print("his right temple's edge: %d texels of his left one's (same height, as far from the edge)" % int((band > 0.5).sum()))
mx_, my_, mz_, ms_, m_dx, m_hair = MOUSTACHE_END
l1 = mat_util.blur(out @ LUM, 1)
box_yz = _box(pos[..., 1], (my_[0] - 0.004, my_[1] - 0.004, my_[2], my_[3])) * _box(pos[..., 2], mz_) * cov
m_r = _box(dxm, mx_) * _box(pos[..., 1], my_) * _box(pos[..., 2], mz_) * cov * smoothstep(l1, *ms_)
sy, sx_ = np.nonzero((box_yz > 0) & (dxm > mx_[2] - 0.002) & (dxm < mx_[3] + m_dx + 0.006) & (l1 < m_hair))
kd_s = KDTree(len(sy))
for i, (yy_, xx_) in enumerate(zip(sy, sx_)):
    kd_s.insert((dxm[yy_, xx_], pos[yy_, xx_, 1], pos[yy_, xx_, 2]), i)
kd_s.balance()
took = out.copy()
for yy_, xx_ in zip(*np.nonzero(m_r > 0)):
    j = kd_s.find((dxm[yy_, xx_] + m_dx, pos[yy_, xx_, 1], pos[yy_, xx_, 2]))[1]
    took[yy_, xx_] = out[sy[j], sx_[j]]
out = out + (took - out) * m_r[..., None]
print("his right moustache's top end: %d texels of its hair %d mm in" % (int((m_r > 0.5).sum()), round(m_dx * 1000)))
# 15. the beard's edge on the lower face: its red half tones to the skin's hue, the light kept
ez_, ex_, ey_, el_, er_, elip = BEARD_EDGE
adx_ = np.abs(pos[..., 0] - mid_x)
l3 = mat_util.blur(out @ LUM, 3)
gr_ = out[..., 1] / np.maximum(out[..., 0], 1e-4)
lip_zone = (1 - smoothstep(adx_, *elip[:2])) * smoothstep(pos[..., 2], *elip[2:])
be = (_box(pos[..., 2], ez_) * _box(adx_, ex_) * (1 - smoothstep(pos[..., 1], *ey_)) * _box(l3, el_)
      * smoothstep(SKIN_HUE[0] - gr_, *er_) * (1 - lip_zone) * cov)
hue_ = np.array(BEARD_EDGE_HUE, np.float32)
out = out + (np.clip(hue_ / float(hue_ @ LUM) * (out @ LUM)[..., None], 0, 1) - out) * be[..., None]
print("the beard's edge: %d texels to the skin's hue" % int((be > 0.5).sum()))
# 12. behind the ears: the hair's hue (the nape's skin its own), the light kept
bw_ = (smoothstep(pos[..., 1], *BACK) * cov)[..., None]
hue_back = (hair_ref / float(hair_ref @ LUM)) * hairw[..., None] + (skin_ch / float(skin_ch @ LUM)) * (1 - hairw[..., None])
out = out + (hue_back * (out @ LUM)[..., None] - out) * bw_
print('behind the ears: %d texels to the hair and skin hues' % int((bw_[..., 0] > 0.5).sum()))
out = out * (1 + PLAIN_GRAIN * grain * plain * (1 - ear))
out = np.clip(out / np.maximum(out.max(-1, keepdims=True), 1), 0, 1)
if os.environ.get('TOUCHUP_DEBUG'):
    out = rgb * 0.5 + np.concatenate([lines[..., None] + bk, ear + bk + lidk[..., None], np.clip((gain - 1) * 3, 0, 1) + chin_w], -1) * 0.5
if os.environ.get('TOUCHUP_GRID'):  # dz from each eyeball's middle every 2 mm (red: 0, yellow: +4 / +8 mm, cyan:
    # +12), dx every 5 mm (blue)
    for e in EYE.values():
        near_e = (np.abs(pos[..., 0] - e[0]) < 0.024) & (np.abs(pos[..., 2] - e[2]) < 0.02) & cov
        dzg, dxg = (pos[..., 2] - e[2]) * 1000, (pos[..., 0] - e[0]) * 1000
        for v in range(-8, 18, 2):
            ln = near_e & (np.abs(dzg - v) < 0.12)
            out[ln] = (1, 0, 0) if v == 0 else (1, 1, 0) if v in (4, 8) else (0, 1, 1) if v == 12 else (0.2, 0.2, 0.2)
        for v in range(-20, 25, 5):
            out[near_e & (np.abs(dxg - v) < 0.15)] = (0, 0, 1) if v else (1, 0, 1)
out[~cov] = rgb[~cov]
mat_util.save('_head_touchup', mat_util.pad(out, cov), OUT, 'sRGB')
print('plain skin %s (sRGB); touched up -> %s' % (np.round(plain_rgb * 255), OUT))
