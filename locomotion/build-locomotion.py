"""Everyday actions timed from Shih Tzu references (references.json). Run in Blender background; --probe renders key poses."""
import bpy, math, json, hashlib, sys
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion

OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'bonggu-v2-tail-rig.blend'
TEXTURE = OUT.parent / 'release' / 'bonggu-color-2k.png'
FPS = 30
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
rig = bpy.data.objects['Bonggu.Rig']; pet = bpy.data.objects['Bonggu.Body']
rig.animation_data_create(); rig.animation_data.action = None
for track in list(rig.animation_data.nla_tracks): rig.animation_data.nla_tracks.remove(track)
# The source still carries the old skeleton's RigDemo action; it does not belong in the runtime file.
for action in list(bpy.data.actions): bpy.data.actions.remove(action)
# The runtime model uses the approved 2K texture. The 4K master stays in release/.
old = next(im for im in bpy.data.images if im.size[0] > 2048)
new = bpy.data.images.load(str(TEXTURE)); new.colorspace_settings.name = old.colorspace_settings.name; new.alpha_mode = old.alpha_mode
old.user_remap(new); bpy.data.images.remove(old); new.name = 'Bonggu painted color 2K'
new.filepath = bpy.path.relpath(str(TEXTURE)); new.pack()
scene.render.fps = FPS
scene.render.resolution_x = 800; scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'

def smooth(v):
    v = max(0., min(1., v)); return v*v*(3-2*v)

def ramp(t, a, b): return smooth((t-a)/(b-a))

def hold(t, start, attack, release, end): return ramp(t, start, attack)*(1-ramp(t, release, end))

def settle(t, start, end, amount):
    """Landing bounce; zero with zero slope when it has died out."""
    u = min(1., max(0., (t-start)/(end-start))); return amount*math.sin(3*math.pi*u)*(1-u)**2

# Pose helpers add to the reset pose, so partial poses can be layered.
def move(name, delta):
    rig.pose.bones[name].location += rig.data.bones[name].matrix_local.to_3x3().inverted() @ Vector(delta)

def rotate(name, x=0, y=0, z=0):
    e = rig.pose.bones[name].rotation_euler; e.x += x; e.y += y; e.z += z

def reset():
    for pb in rig.pose.bones:
        if not pb.name.startswith(('MCH.Neck.', 'MCH.HeadGaze')): pb.matrix_basis = Matrix.Identity(4)
    rig['Smile'] = 0.; rig['IK'] = 1.

BREATH = 3.  # resting dogs breathe about 20 times a minute

def breathe(t, depth):
    # Widen the ribcage segment; Chest cancels it so the neck, head and forelegs keep their size.
    s = 1 + depth*(.5-.5*math.cos(math.tau*t/BREATH))
    rig.pose.bones['Spine.04'].scale = (s, 1, s); rig.pose.bones['Chest'].scale = (1/s, 1, 1/s)

def glance(t, when, yaw, tilt=0., pitch=0., turn=.22, dwell=1.):
    # Dogs turn the head quickly, then hold and look; they do not sweep like a camera.
    a = hold(t, when, when+turn, when+turn+dwell, when+2*turn+dwell+.1)
    rotate('CTRL.Look', x=pitch*a, y=yaw*a, z=tilt*a); rotate('CTRL.NeckBase', y=.2*yaw*a)

def sway(t, seconds):
    # Swells and fades over a loop; zero with zero slope at its start.
    return math.sin(math.pi*t/seconds)**2

tail_rest = {f'Tail.{i:02}': rig.data.bones[f'Tail.{i:02}'].matrix_local.to_quaternion() for i in range(1, 9)}
tail_low = {}
for name, direction in zip(tail_rest, [(0,.96,-.28),(0,.82,-.57),(0,.60,-.80),(0,.33,-.94),(0,.14,-.99),(0,.12,-.99),(0,.38,-.92),(0,.62,-.78)]):
    y = Vector(direction).normalized(); x = (Vector((1,0,0))-y*y.x).normalized()
    tail_low[name] = Matrix((x, y, x.cross(y))).transposed().to_quaternion()

def tail(t, amount=0., frequency=1., lowered=0., lift=0.):
    bpy.context.view_layer.update()
    parent = rig.pose.bones['Pelvis'].matrix.to_quaternion()
    body_delta = parent @ rig.data.bones['Pelvis'].matrix_local.to_quaternion().inverted() @ Quaternion((1,0,0), lift)
    for j, (name, rest) in enumerate(tail_rest.items()):
        # A traveling delay lets the tip follow the root without twisting the curl.
        angle = amount*(1+.12*j/7)*math.sin(math.tau*frequency*t-.18*j)
        target = body_delta @ Quaternion((0,1,0), angle) @ rest.slerp(tail_low[name], lowered)
        local_rest = rig.data.bones[name].parent.matrix_local.to_quaternion().inverted() @ rest
        rig.pose.bones[name].rotation_euler = ((parent @ local_rest).inverted() @ target).to_euler('XYZ')
        parent = target

def sit(hip=1., leg=1., front=1.):
    # Stand-to-sit: the hip flexes first, then stifle and hock fold, while the forelegs stay upright.
    move('CTRL.Body', (0, -.020*hip, -.112*hip))
    rotate('Pelvis', x=-.50*hip)
    rotate('Spine.02', x=-.05*front)
    rotate('CTRL.Look', x=.55*hip)
    for side, sign in [('L', 1), ('R', -1)]:
        # Paws forward and slightly out keep the folded hock beside the thigh rather than inside it.
        move('CTRL.HindPaw.'+side, (sign*.024*leg, -.072*leg, 0))
        move('CTRL.HindPole.'+side, (sign*.025*leg, -.035*leg, -.025*leg))
        rotate('CTRL.Hock.'+side, x=-.95*leg)
        move('CTRL.ForePaw.'+side, (0, .012*front, 0))

def lie(front=1., rear=1.):
    # Front first: the elbows reach the floor while the rear is still up, then the rear folds under.
    pitch = .20*front - .20*rear
    move('CTRL.Body', (0, -.006*front, -.046*front - .040*rear))
    rotate('CTRL.Body', x=pitch)
    rotate('CTRL.Look', x=-pitch + .04*rear)
    rotate('Pelvis', x=-.04*rear)
    for side, sign in [('L', 1), ('R', -1)]:
        move('CTRL.ForePaw.'+side, (sign*.008*front, -.064*front, 0))
        move('CTRL.ForePole.'+side, (sign*.008*front, .010*front, -.020*front))
        rotate('CTRL.Carpus.'+side, x=-.65*front)
        move('CTRL.HindPaw.'+side, (sign*.012*rear, -.060*rear, 0))
        move('CTRL.HindPole.'+side, (sign*.04*rear, -.035*rear, -.050*rear))
        rotate('CTRL.Hock.'+side, x=-1.22*rear)

# period s, duty factor, stance travel m, paw lift m, body height m, footfall phase offsets
GAITS = {
    'walk': (16/FPS, .64, .090, .022, -.010, {'Fore.L': 0, 'Fore.R': .5, 'Hind.L': .25, 'Hind.R': .75}),
    'trot': (10/FPS, .45, .100, .034, -.015, {'Fore.L': 0, 'Fore.R': .5, 'Hind.L': .5, 'Hind.R': 0}),
}

def forward_speed(kind):
    period, duty, span, *_ = GAITS[kind]; return span/(duty*period)

def gait(t, kind):
    period, duty, span, lift, height, offsets = GAITS[kind]; trot = kind == 'trot'
    phase = t/period
    # Level topline: a small dip at each mid-stance, twice per stride.
    move('CTRL.Body', (0, 0, height - (.0025 if trot else .0012)*math.cos(2*math.tau*(phase - duty/2))))
    # Pelvis and shoulders roll and yaw with their limb pair, in opposition.
    hind = math.sin(math.tau*(phase + offsets['Hind.L'])); fore = math.sin(math.tau*(phase + offsets['Fore.L']))
    rotate('Pelvis', y=(.012 if trot else .028)*hind, z=(.02 if trot else .035)*hind)
    rotate('Chest', z=-(.015 if trot else .03)*fore)
    rotate('Spine.02', x=(.012 if trot else .004)*math.cos(2*math.tau*phase))
    # Naturally high head carriage with a small nod after each forefoot strike.
    rotate('CTRL.NeckBase', x=-.05)
    rotate('CTRL.Look', x=-.03 + (.02 if trot else .012)*math.cos(2*math.tau*(phase - duty/2 - .08)), y=.012*fore)
    for leg, offset in offsets.items():
        u = (phase + offset) % 1
        if u < duty:
            # Linear backwards motion cancels the app's constant forward speed.
            s = u/duty; travel = span*(s - .5); up = 0.; toeoff = smooth((s-.7)/.3); fold = 0.
        else:
            v = (u-duty)/(1-duty)
            travel = span*(.5 - smooth(v)); up = lift*math.sin(math.pi*v**.75)**2
            toeoff = 1 - smooth(v/.2); fold = math.sin(math.pi*min(1., v*1.15))**2
        end, side = leg.split('.')
        move(f'CTRL.{end}Paw.{side}', (0, travel, up))
        rotate(f'CTRL.{end}ToeRoll.{side}', x=(.25 if trot else .15)*toeoff)
        rotate(f'CTRL.{"Carpus" if end == "Fore" else "Hock"}.{side}', x=-(.5 if end == 'Fore' else .32)*fold)
    tail(t, .05 if trot else .04, 1/period)

def idle(t):
    breathe(t, .02)
    move('CTRL.Body', (.0015*math.sin(math.tau*t/6), 0, 0))
    glance(t, 1.1, .30, tilt=.04)
    glance(t, 3.7, -.20, pitch=.05)
    tail(t, .03*sway(t, 6), .5)

def sit_idle(t):
    sit(); breathe(t, .022)
    glance(t, .9, -.25, tilt=-.05)
    glance(t, 3.4, .18)
    tail(t, .025*sway(t, 6), .5, lift=.30)

def lie_idle(t):
    lie(); breathe(t, .03)
    glance(t, 1.3, .35, tilt=.06)
    glance(t, 3.9, -.15, pitch=-.08)
    tail(t, .02*sway(t, 6), .5, lift=.25)

def sit_down(t):
    hip = ramp(t, 0, .7); sit(hip, ramp(t, .12, .85), ramp(t, .25, .95))
    move('CTRL.Body', (0, 0, settle(t, .7, 1.2, -.003)))
    tail(t, lift=.30*hip)

def sit_up(t):
    lean = hold(t, 0, .15, .3, .6)
    move('CTRL.Body', (0, -.006*lean, 0)); rotate('CTRL.Look', x=.05*lean)
    hip = 1-ramp(t, .1, .65); sit(hip, 1-ramp(t, .18, .8), 1-ramp(t, .05, .6))
    tail(t, lift=.30*hip)

def lie_down(t):
    nose = hold(t, 0, .3, .65, 1.15)
    rotate('CTRL.Look', x=.35*nose); rotate('CTRL.NeckBase', x=.12*nose)
    rear = ramp(t, .4, 1.1); lie(ramp(t, .1, .7), rear)
    move('CTRL.Body', (0, 0, settle(t, 1.0, 1.4, -.002)))
    tail(t, lift=.25*rear)

def lie_up(t):
    rotate('CTRL.Look', x=-.1*hold(t, 0, .2, .5, .9))
    rear = 1-ramp(t, .25, .9); lie(1-ramp(t, 0, .5), rear)
    tail(t, lift=.25*rear)

def play_bow(t):
    bow = ramp(t, .05, .32)*(1-ramp(t, 1.45, 1.8))
    lie(.9*bow, 0)
    move('CTRL.Body', (0, 0, settle(t, .32, 1.0, -.003) + settle(t, 1.8, 2.4, .003)))
    tail(t, .30*hold(t, .2, .4, 2.4, 2.9), 3.5)

def look_around(t):
    yaw = .55*ramp(t, .3, .6) - 1.0*ramp(t, 1.65, 2.05) + .45*ramp(t, 3.2, 3.55)
    tilt = .06*hold(t, .55, .8, 1.4, 1.65) - .05*hold(t, 2.1, 2.35, 2.9, 3.15)
    rotate('CTRL.Look', x=.015*math.sin(math.tau*1.1*t)*hold(t, .3, .6, 3.2, 3.55), y=yaw, z=tilt)
    rotate('CTRL.NeckBase', y=.15*yaw)
    move('CTRL.Body', (.002*yaw, 0, 0))

def ground_sniff(t):
    a = hold(t, .15, .7, 3.2, 3.85)
    # Sniffing comes in bouts at about 5 Hz.
    pulse = math.sin(math.tau*5*t)*(hold(t, .9, 1., 1.7, 1.8) + hold(t, 2.1, 2.2, 2.95, 3.05))
    move('CTRL.Body', (0, -.008*a, -.022*a))
    rotate('CTRL.NeckBase', x=.30*a + .006*pulse)
    rotate('CTRL.Look', x=.50*a + .02*pulse, y=.16*math.sin(math.tau*(t-.7)/2.5)*a)
    for side in ['L', 'R']: move('CTRL.ForePaw.'+side, (0, -.012*a, 0))
    tail(t, .02*a, .8)

def look_up(t):
    a = hold(t, .15, .5, 2.6, 3.2)
    rotate('CTRL.NeckBase', x=-.12*a)
    rotate('CTRL.Look', x=-.55*a, y=.05*math.sin(math.tau*t/3.6)*a, z=.05*hold(t, 1., 1.3, 2.1, 2.4))
    move('CTRL.Body', (0, .002*a, -.003*a))

def tail_wag_soft(t):
    env = hold(t, 0, .35, 3.6, 4.)
    tail(t, .22*env, 2.25)
    rotate('Pelvis', z=-.012*math.sin(math.tau*2.25*t)*env)
    rotate('CTRL.Look', z=.03*hold(t, .8, 1.1, 2.8, 3.1))

def tail_wag_happy(t):
    # A greeting wags the whole rear, with the head a little lowered.
    env = hold(t, 0, .25, 2.9, 3.2); wag = math.sin(math.tau*3.5*t)*env
    tail(t, .38*env, 3.5)
    rotate('Pelvis', z=-.035*wag); move('CTRL.Body', (.0015*wag, 0, 0))
    rotate('CTRL.Look', x=.08*env)

def tail_lower(t):
    tail(t, lowered=ramp(t, 0, 1.4)); rotate('CTRL.Look', x=.06*ramp(t, .2, 1.2))

def tail_low_idle(t):
    breathe(t, .02); rotate('CTRL.Look', x=.06)
    glance(t, 2., .2)
    tail(t, .025*sway(t, 6), .5, lowered=1.)

def tail_raise(t):
    tail(t, lowered=1-ramp(t, 0, 1.2)); rotate('CTRL.Look', x=.06*(1-ramp(t, 0, .9)))

CLIPS = [  # name, seconds, pose, label, loop, entry, exit, forward speed, smile
    ('Idle', 6., idle, '서서 쉬기', True, 'stand', 'stand', 0., 0.),
    ('Walk', 16/FPS, lambda t: gait(t, 'walk'), '걷기', True, 'walk', 'walk', forward_speed('walk'), 0.),
    ('Run', 10/FPS, lambda t: gait(t, 'trot'), '가볍게 달리기', True, 'run', 'run', forward_speed('trot'), .32),
    ('SitDown', 1.2, sit_down, '앉기', False, 'stand', 'sit', 0., 0.),
    ('SitIdle', 6., sit_idle, '앉아서 쉬기', True, 'sit', 'sit', 0., 0.),
    ('SitUp', .9, sit_up, '앉았다 일어나기', False, 'sit', 'stand', 0., 0.),
    ('LieDown', 1.4, lie_down, '엎드리기', False, 'stand', 'lie', 0., 0.),
    ('LieIdle', 6., lie_idle, '엎드려 쉬기', True, 'lie', 'lie', 0., 0.),
    ('LieUp', 1.2, lie_up, '엎드렸다 일어나기', False, 'lie', 'stand', 0., 0.),
    ('PlayBow', 3., play_bow, '놀자고 앞몸 낮추기', True, 'stand', 'stand', 0., .4),
    ('LookAround', 4., look_around, '고개 돌려 좌우 보기', True, 'stand', 'stand', 0., 0.),
    ('GroundSniff', 4., ground_sniff, '고개 숙여 킁킁', True, 'stand', 'stand', 0., 0.),
    ('LookUp', 3.6, look_up, '하늘 올려다보기', True, 'stand', 'stand', 0., 0.),
    ('TailWagSoft', 4., tail_wag_soft, '꼬리 살랑살랑', True, 'stand', 'stand', 0., 0.),
    ('TailWagHappy', 3.2, tail_wag_happy, '반갑게 꼬리 흔들기', True, 'stand', 'stand', 0., .45),
    ('TailLower', 1.4, tail_lower, '꼬리 천천히 내리기', False, 'stand', 'tail-low', 0., 0.),
    ('TailLowIdle', 6., tail_low_idle, '꼬리 내린 채 쉬기', True, 'tail-low', 'tail-low', 0., 0.),
    ('TailRaise', 1.2, tail_raise, '꼬리 다시 올리기', False, 'tail-low', 'stand', 0., 0.),
]
STATE_LOOP = {'stand': 'Idle', 'walk': 'Walk', 'run': 'Run', 'sit': 'SitIdle', 'lie': 'LieIdle', 'tail-low': 'TailLowIdle'}

# Ears and tail lag behind the head and body as damped springs, driven only by body motion
# so authored tail wags keep their shape. Hz, damping ratio, share per bone, max radians.
CHAINS = {
    'Ear.L': ([f'Ear.{i:02}.L' for i in range(1, 5)], 3.0, .2, [.4, .3, .2, .1], .45),
    'Ear.R': ([f'Ear.{i:02}.R' for i in range(1, 5)], 3.0, .2, [.4, .3, .2, .1], .45),
    'Tail': ([f'Tail.{i:02}' for i in range(1, 9)], 3.5, .3, [.2, .18, .15, .13, .11, .09, .08, .06], .3),
}
driver_rest = {'Ear.L': 'Head', 'Ear.R': 'Head', 'Tail': 'Pelvis'}
chain_tip = {k: rig.data.bones[names[-1]].tail_local.copy() for k, (names, *_) in CHAINS.items()}

def rigid_tips(pose, count):
    tips = {k: np.zeros((count, 3)) for k in CHAINS}
    for f in range(count):
        reset(); pose(f/FPS); bpy.context.view_layer.update()
        for k in CHAINS:
            driver = driver_rest[k]
            delta = rig.pose.bones[driver].matrix @ rig.data.bones[driver].matrix_local.inverted()
            tips[k][f] = delta @ chain_tip[k]
    return tips

def spring(x, hz, zeta, periodic, start):
    """Lag of a damped follower behind the rigid tip path x; periodic paths repeat frame 0 at the end."""
    w = math.tau*hz; sub = 8; h = 1/(FPS*sub)
    xs = x[:-1] if periodic else x; m = len(xs)
    if periodic: acc = (np.roll(xs, -1, 0) - 2*xs + np.roll(xs, 1, 0))*FPS*FPS
    else:
        pad = np.vstack([xs[:1], xs, xs[-1:]]); acc = (pad[2:] - 2*pad[1:-1] + pad[:-2])*FPS*FPS
    e, v = (start[0].copy(), start[1].copy()) if start else (np.zeros(3), np.zeros(3))
    cycles = 6 if periodic else 1; out = np.zeros((m, 3)); state = None
    for c in range(cycles):
        for i in range(m):
            if c == cycles-1:
                out[i] = e
                if i == 0: state = (e.copy(), v.copy())
            a0 = acc[i]; a1 = acc[(i+1) % m] if periodic else acc[min(i+1, m-1)]
            for k in range(sub):
                a = a0 + (a1-a0)*k/sub; v += (-w*w*e - 2*zeta*w*v - a)*h; e += v*h
    return (np.vstack([out, out[:1]]) if periodic else out), state

def apply_secondary(lags):
    bpy.context.view_layer.update()
    for k, (names, hz, zeta, share, limit) in CHAINS.items():
        root = rig.pose.bones[names[0]].head; a = rig.pose.bones[names[-1]].tail - root
        axis = a.cross(a + Vector(lags[k])); s = axis.length
        if s < 1e-12: continue
        angle = min(limit, math.atan2(s, a.dot(a + Vector(lags[k])))); axis /= s
        # Every bone turns about the same armature axis, so pre-offset matrices stay valid.
        for name, part in zip(names, share):
            pb = rig.pose.bones[name]
            local = (pb.matrix_basis.to_3x3() @ pb.matrix.to_3x3().inverted() @ axis).normalized()
            pb.rotation_euler = (Quaternion(local, angle*part) @ pb.matrix_basis.to_quaternion()).to_euler('XYZ', pb.rotation_euler)

def evaluated():
    bpy.context.view_layer.update()
    return np.array([v.co[:] for v in pet.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices])

def render(name, side=False):
    target = Vector((0, .015, .15)); cam = scene.camera
    cam.data.ortho_scale = .52
    cam.location = target + Vector((1, -.03, .12) if side else (.65, -1, .33))
    cam.rotation_euler = (target-cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(OUT/'frames'/(name+'.png')); bpy.ops.render.render(write_still=True)

base = np.array([v.co[:] for v in pet.data.vertices])
smile = np.array([v.co[:] for v in pet.data.shape_keys.key_blocks['Smile'].data])
edges = np.array([e.vertices[:] for e in pet.data.edges])
def weight(names):
    ids = {pet.vertex_groups[n].index for n in names}
    return np.array([sum(g.weight for g in v.groups if g.group in ids) for v in pet.data.vertices])
# Floor contact regions in the rest pose: the rump for sitting, the chest and belly for lying.
rump = (weight(['Pelvis']) > .5) & (base[:, 2] < .14) & (base[:, 1] > .12)
ventral = (weight(['Spine.01', 'Spine.02', 'Spine.03', 'Spine.04', 'Chest']) > .6) & (base[:, 2] < .115)

def ik_error():
    error = 0.
    for end in ['Fore', 'Hind']:
        for side in ['L', 'R']:
            target = f'MCH.Carpus.{side}' if end == 'Fore' else f'MCH.Hock.{side}'
            error = max(error, (rig.pose.bones[f'{end}.Lower.{side}'].tail-rig.pose.bones[target].head).length)
    return error

if '--probe' in sys.argv:
    probes = [('sit', lambda: sit()), ('lie', lambda: lie()), ('lie-front', lambda: lie(1, 0)), ('bow', lambda: lie(.9, 0)),
              ('walk', lambda: gait(.1, 'walk')), ('trot', lambda: gait(.1, 'trot'))]
    for name, pose in probes:
        reset(); pose(); co = evaluated()
        lengths = np.linalg.norm(base[edges[:, 0]]-base[edges[:, 1]], axis=1); ok = lengths > .0015
        strain = np.linalg.norm(co[edges[:, 0]]-co[edges[:, 1]], axis=1)[ok]/lengths[ok]
        print('POSE', name, 'minz %.4f rump %.4f ventral %.4f ik %.6f p99 %.3f max %.3f' % (co[:, 2].min(), co[rump, 2].min(), co[ventral, 2].min(),
              ik_error(), np.quantile(strain, .99), strain.max()), flush=True)
        render('probe-'+name); render('probe-'+name+'-side', True)
    raise SystemExit

report = {'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'clips': {}}
# Periodic state loops first: every other clip starts and ends on their secondary-motion state.
order = sorted(CLIPS, key=lambda c: c[0] != STATE_LOOP[c[5]] or c[5] != c[6])
steady = {}; lags = {}
for name, seconds, pose, label, loop, entry, exit_state, speed, _ in order:
    count = round(seconds*FPS)+1; periodic = name == STATE_LOOP[entry] and entry == exit_state
    tips = rigid_tips(pose, count); lags[name] = {}
    for k, (names, hz, zeta, *_) in CHAINS.items():
        start = None if periodic else steady[STATE_LOOP[entry]][k]
        lag, state = spring(tips[k], hz, zeta, periodic, start)
        if periodic: steady[name] = {**steady.get(name, {}), k: state}
        else:
            # Ease into the exit loop's secondary state so the next clip starts seamlessly.
            target = steady[STATE_LOOP[exit_state]][k][0]
            for f in range(count):
                w = ramp(f/FPS, seconds-.35, seconds); lag[f] = lag[f]*(1-w) + target*w
        lags[name][k] = lag

endpoints = {}; manifest = []
for name, seconds, pose, label, loop, entry, exit_state, speed, smile_weight in CLIPS:
    action = bpy.data.actions.new(name); action.use_fake_user = True
    rig.animation_data.action = action
    count = round(seconds*FPS)+1; periodic = name == STATE_LOOP[entry] and entry == exit_state
    first = None; previous = None
    check = {'frames': count, 'min_z': 1., 'max_ik_error': 0., 'max_p99_edge_stretch': 1., 'max_frame_displacement': 0.}
    for frame in range(1, count+1):
        t = (frame-1)/FPS
        scene.frame_set(frame); reset(); pose(t)
        apply_secondary({k: lags[name][k][frame-1] for k in CHAINS})
        # The app eases toward clips.json smile; the native preview mimics that inside non-state clips.
        rig['Smile'] = smile_weight*(1 if periodic else hold(t, 0, .25, seconds-.25, seconds))
        co = evaluated(); assert np.isfinite(co).all()
        check['min_z'] = min(check['min_z'], float(co[:, 2].min()))
        before = base+(smile-base)*rig['Smile']
        lengths = np.linalg.norm(before[edges[:, 0]]-before[edges[:, 1]], axis=1)
        strain = np.linalg.norm(co[edges[:, 0]]-co[edges[:, 1]], axis=1)[lengths > .0015]/lengths[lengths > .0015]
        check['max_p99_edge_stretch'] = max(check['max_p99_edge_stretch'], float(np.quantile(strain, .99)))
        check['max_ik_error'] = max(check['max_ik_error'], ik_error())
        if first is None:
            first = co.copy(); check['rump_min_z'] = float(co[rump, 2].min()); check['ventral_min_z'] = float(co[ventral, 2].min())
        if previous is not None: check['max_frame_displacement'] = max(check['max_frame_displacement'], float(np.linalg.norm(co-previous, axis=1).max()))
        previous = co.copy()
        for pb in rig.pose.bones:
            if pb.name.startswith(('MCH.Neck.', 'MCH.HeadGaze')): continue
            pb.keyframe_insert('location', frame=frame, group=pb.name)
            pb.keyframe_insert('rotation_euler', frame=frame, group=pb.name)
            if pb.name in ('Spine.04', 'Chest'): pb.keyframe_insert('scale', frame=frame, group=pb.name)
        for prop in ['Smile', 'IK']: rig.keyframe_insert(data_path='["'+prop+'"]', frame=frame)
    check['endpoint_difference'] = float(np.max(np.abs(first-co)))
    endpoints[name] = (first, co)
    print('CLIP_CHECK', name, json.dumps(check), flush=True)
    assert check['min_z'] > -.0015, (name, check)
    assert check['max_ik_error'] < .001, (name, check)
    if loop: assert check['endpoint_difference'] < 1e-5, (name, check)
    report['clips'][name] = check
    rig.animation_data.action = None
    track = rig.animation_data.nla_tracks.new(); track.name = name
    strip = track.strips.new(name, 1, action); strip.extrapolation = 'NOTHING'; strip.blend_type = 'REPLACE'; track.mute = True
    manifest.append({'name': name, 'label': label, 'duration_seconds': seconds, 'loop': loop, 'entry_state': entry, 'exit_state': exit_state,
                     'forward_speed_mps': speed, 'smile': smile_weight, 'preview': name+'.mp4'})

# Every clip begins on its entry loop's first frame and ends on its exit loop's first frame.
for name, seconds, pose, label, loop, entry, exit_state, *_ in CLIPS:
    for state, end in [(entry, 0), (exit_state, 1)]:
        error = float(np.abs(endpoints[name][end]-endpoints[STATE_LOOP[state]][0]).max())
        assert error < 1e-5, (name, state, error)
report['transition_endpoints_match'] = True
assert report['clips']['SitIdle']['rump_min_z'] < .004, report['clips']['SitIdle']
assert report['clips']['LieIdle']['ventral_min_z'] < .004, report['clips']['LieIdle']
scene.name = 'BongguEveryday'; scene.frame_start = 1; scene.frame_end = round(6*FPS)+1
for track in rig.animation_data.nla_tracks: track.mute = track.name != 'Idle'
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True); pet.select_set(True); bpy.context.view_layer.objects.active = rig
bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bonggu-v2-everyday.blend'))
# Smile is not exported as animation: the app owns the morph and applies each clip's smile value.
bpy.ops.export_scene.gltf(filepath=str(OUT/'bonggu-v2-everyday.glb'), export_format='GLB', use_selection=True, export_apply=False,
    export_animations=True, export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_skins=True,
    export_morph=True, export_morph_animation=False, export_def_bones=True, export_anim_slide_to_zero=True,
    export_optimize_animation_size=True)
(OUT/'motion-checks.json').write_text(json.dumps(report, indent=2)+'\n')
(OUT/'clips.json').write_text(json.dumps({'model': 'bonggu-v2-everyday.glb', 'blender': 'bonggu-v2-everyday.blend', 'fps': FPS,
    'forward_axis': '-Y in Blender; +Z in glTF', 'units': 'metres', 'root_motion': False, 'morph_animation': False, 'clips': manifest,
    'previous_behaviors': '../animations/bonggu-v2-behaviors.glb', 'locomotion_blend_seconds': .18, 'references': 'references.json',
    'neck_preview': 'neck-movements.mp4', 'preview': 'everyday-preview.mp4', 'sit_preview': 'sit-sequence.mp4',
    'lie_preview': 'lie-sequence.mp4', 'tail_preview': 'tail-movements.mp4'}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('EXPORTED', flush=True)

if '--preview' in sys.argv:
    for name, seconds, *_ in CLIPS:
        for track in rig.animation_data.nla_tracks: track.mute = track.name != name
        for f in sorted(set([1, round(seconds*FPS/2)+1, round(seconds*FPS)+1])):
            scene.frame_set(f); render(f'{name}-{f:03}'); render(f'{name}-{f:03}-side', True)
    print('STILLS_DONE', flush=True)
