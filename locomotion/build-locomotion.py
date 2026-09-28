"""Editable everyday actions. Run in Blender background; --probe only renders poses."""
import bpy, math, json, hashlib, sys
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion

OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'bonggu-v2-tail-rig.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
rig = bpy.data.objects['Bonggu.Rig']; pet = bpy.data.objects['Bonggu.Body']
rig.animation_data_create();rig.animation_data.action = None
for track in rig.animation_data.nla_tracks: track.mute = True
scene.render.fps = 30
scene.render.resolution_x = 800; scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'

def smooth(v):
    v = max(0., min(1., v)); return v*v*(3-2*v)

def move(name, delta):
    rig.pose.bones[name].location = rig.data.bones[name].matrix_local.to_3x3().inverted() @ Vector(delta)

def rotate(name, x=0, y=0, z=0): rig.pose.bones[name].rotation_euler = (x,y,z)

def reset():
    for pb in rig.pose.bones:
        if not pb.name.startswith(('MCH.Neck.','MCH.HeadGaze')):pb.matrix_basis = Matrix.Identity(4)
    rig['Smile'] = 0.; rig['IK'] = 1.

def fold_hock(side, angle):
    rotate('CTRL.Hock.'+side,x=angle)

def sit(amount=1.):
    a = amount
    move('CTRL.Body', (0,-.020*a,-.112*a))
    rotate('Pelvis', x=-.50*a)
    rotate('Spine.02', x=-.05*a)
    rotate('CTRL.Look', x=.55*a)
    for side,sign in [('L',1),('R',-1)]:
        move('CTRL.HindPaw.'+side,(sign*.014*a,-.065*a,0))
        move('CTRL.HindPole.'+side,(sign*.025*a,-.035*a,-.025*a))
        fold_hock(side,-1.10*a)
        rotate('Tail.01', x=.30*a)

def lie(amount=1.):
    a=amount
    move('CTRL.Body',(0,-.005*a,-.081*a))
    rotate('Pelvis',x=-.04*a)
    rotate('CTRL.Look',x=.04*a)
    for side,sign in [('L',1),('R',-1)]:
        move('CTRL.ForePaw.'+side,(sign*.008*a,-.064*a,0))
        move('CTRL.ForePole.'+side,(sign*.008*a,.010*a,-.020*a))
        rotate('CTRL.Carpus.'+side,x=-.65*a)
        move('CTRL.HindPaw.'+side,(sign*.012*a,-.060*a,0))
        move('CTRL.HindPole.'+side,(sign*.04*a,-.035*a,-.050*a))
        fold_hock(side,-1.22*a)
    rotate('Tail.01',x=.25*a)

tail_rest={f'Tail.{i:02}':rig.data.bones[f'Tail.{i:02}'].matrix_local.to_quaternion() for i in range(1,9)}
tail_low={}
for name,direction in zip(tail_rest,[(0,.96,-.28),(0,.82,-.57),(0,.60,-.80),(0,.33,-.94),(0,.14,-.99),(0,.12,-.99),(0,.38,-.92),(0,.62,-.78)]):
    y=Vector(direction).normalized();x=(Vector((1,0,0))-y*y.x).normalized()
    tail_low[name]=Matrix((x,y,x.cross(y))).transposed().to_quaternion()

def tail(t, amount=.03, frequency=1., lowered=0.):
    bpy.context.view_layer.update()
    parent=rig.pose.bones['Pelvis'].matrix.to_quaternion()
    body_delta=parent@rig.data.bones['Pelvis'].matrix_local.to_quaternion().inverted()
    for j,(name,rest) in enumerate(tail_rest.items()):
        # A short traveling delay lets the tip follow the root without twisting the curl.
        angle=amount*(1+.12*j/7)*math.sin(math.tau*frequency*t-.10*j)
        target=body_delta@Quaternion((0,1,0),angle)@rest.slerp(tail_low[name],lowered)
        local_rest=rig.data.bones[name].parent.matrix_local.to_quaternion().inverted()@rest
        rig.pose.bones[name].rotation_euler=((parent@local_rest).inverted()@target).to_euler('XYZ')
        parent=target

def tail_wag(t, happy=False):
    duration=3.2 if happy else 4.
    envelope=smooth(t/.45)*(1-smooth((t-(duration-.45))/.45))
    tail(t,(.40 if happy else .23)*envelope,6/duration if happy else 3/duration)

def tail_low_idle(t):
    tail(t,.025*math.sin(math.pi*t/3)**2,1.,1.)

def idle(t):
    wave=math.sin(math.tau*t/3)
    move('CTRL.Body',(0,0,.001*wave))
    rotate('CTRL.NeckBase',x=.006*wave);rotate('CTRL.Look',y=.035*wave)
    tail(t,.02,1/3)

def gait(t, running=False):
    period=.6 if running else 1.2
    duty=.42 if running else .70
    span=.095 if running else .075
    phase=t/period
    bounce=math.cos(math.tau*2*(phase-.18))
    move('CTRL.Body',(.0015*math.sin(math.tau*phase),0,(-.019+.007*bounce) if running else (-.012+.002*bounce)))
    rotate('Spine.02',x=.014*math.sin(math.tau*2*phase) if running else .005*math.sin(math.tau*phase))
    rotate('CTRL.Look',x=-.012*math.sin(math.tau*2*phase),z=.01*math.sin(math.tau*phase))
    offsets={'Fore.L':0,'Fore.R':.5,'Hind.L':.5 if running else .25,'Hind.R':0 if running else .75}
    for leg,offset in offsets.items():
        u=(phase+offset)%1
        if u<duty:
            # Linear backwards motion cancels the app's constant forward speed.
            travel=span*(u/duty-.5);height=0.
            toeoff=smooth((u/duty-.68)/.32)
            fold=0.
        else:
            v=(u-duty)/(1-duty)
            travel=span*(.5-smooth(v))
            height=(.040 if running else .021)*math.sin(math.pi*v)**2
            toeoff=1-smooth(v/.22)
            fold=math.sin(math.pi*v)**2
        move('CTRL.'+leg.replace('.', 'Paw.',1),(0,travel,height))
        end,side=leg.split('.')
        rotate(f'CTRL.{end}ToeRoll.{side}',x=(.23 if running else .13)*toeoff)
        rotate(f'CTRL.{"Carpus" if end=="Fore" else "Hock"}.{side}',x=-(.42 if end=='Fore' else .30)*fold)
    for side,sign in [('L',1),('R',-1)]:
        for j in range(4):
            rotate(f'Ear.{j+1:02}.{side}',x=(.04 if running else .012)*math.sin(math.tau*2*phase-.4*j),y=sign*.018*math.sin(math.tau*phase-.3*j))
    tail(t,.035 if running else .022,1/period)
    rig['Smile']=.32 if running else 0.

def sit_idle(t):
    sit();wave=math.sin(math.tau*t/3)
    rotate('CTRL.Look',x=.55+.012*wave,y=.035*wave)

def lie_idle(t):
    lie();wave=math.sin(math.tau*t/3)
    rotate('CTRL.Look',x=.04+.012*wave,y=.035*wave)

def play_bow(t):
    a=smooth(t/.85)*(1-smooth((t-2.05)/.95))
    move('CTRL.Body',(0,0,-.004*a))
    rotate('Pelvis',x=.27*a)
    rotate('CTRL.Look',x=-.25*a)
    for side in ['L','R']:move('CTRL.ForePaw.'+side,(0,-.033*a,0))
    tail(t,.085*a,2.)

def hold(t,start,attack,release,end):return smooth((t-start)/(attack-start))*(1-smooth((t-release)/(end-release)))

def look_around(t):
    a=hold(t,.1,.6,3.4,4.)
    angle=.64*math.sin(math.tau*(t-.4)/3.2)*a
    rotate('CTRL.Look',y=angle,z=.025*math.sin(math.pi*t/2)*a)
    rotate('CTRL.NeckBase',y=.06*math.sin(math.tau*(t-.6)/3.2)*a)

def ground_sniff(t):
    a=hold(t,.15,.95,3.25,4.)
    sniff=hold(t,1.,1.2,3.0,3.3)
    pulse=math.sin(math.tau*3.4*t)*sniff
    move('CTRL.Body',(0,-.008*a,-.024*a))
    rotate('CTRL.NeckBase',x=.32*a+.008*pulse)
    rotate('CTRL.Look',x=.52*a+.025*pulse,y=.16*math.sin(math.tau*(t-1)/3)*a)
    for side in ['L','R']:move('CTRL.ForePaw.'+side,(0,-.012*a,0))
    tail(t,.018*a,.6)

def look_up(t):
    a=hold(t,.1,1.05,2.5,3.6)
    rotate('CTRL.NeckBase',x=-.12*a)
    rotate('CTRL.Look',x=-.57*a,y=.045*math.sin(math.tau*t/3.6)*a)
    move('CTRL.Body',(0,.002*a,-.003*a))

CLIPS=[
    ('Idle',3.,idle,'서서 쉬기',True,'stand','stand',0.),
    ('Walk',1.2,lambda t:gait(t),'걷기',True,'walk','walk',.075/(.70*1.2)),
    ('Run',.6,lambda t:gait(t,True),'가볍게 달리기',True,'run','run',.095/(.42*.6)),
    ('SitDown',1.4,lambda t:sit(smooth(t/1.4)),'앉기',False,'stand','sit',0.),
    ('SitIdle',3.,sit_idle,'앉아서 쉬기',True,'sit','sit',0.),
    ('SitUp',1.2,lambda t:sit(1-smooth(t/1.2)),'앉았다 일어나기',False,'sit','stand',0.),
    ('LieDown',1.6,lambda t:lie(smooth(t/1.6)),'엎드리기',False,'stand','lie',0.),
    ('LieIdle',3.,lie_idle,'엎드려 쉬기',True,'lie','lie',0.),
    ('LieUp',1.4,lambda t:lie(1-smooth(t/1.4)),'엎드렸다 일어나기',False,'lie','stand',0.),
    ('PlayBow',3.,play_bow,'놀자고 앞몸 낮추기',True,'stand','stand',0.),
    ('LookAround',4.,look_around,'고개 돌려 좌우 보기',True,'stand','stand',0.),
    ('GroundSniff',4.,ground_sniff,'고개 숙여 킁킁',True,'stand','stand',0.),
    ('LookUp',3.6,look_up,'하늘 올려다보기',True,'stand','stand',0.),
    ('TailWagSoft',4.,tail_wag,'꼬리 살랑살랑',True,'stand','stand',0.),
    ('TailWagHappy',3.2,lambda t:tail_wag(t,True),'반갑게 꼬리 흔들기',True,'stand','stand',0.),
    ('TailLower',1.4,lambda t:tail(t,0.,lowered=smooth(t/1.4)),'꼬리 천천히 내리기',False,'stand','tail-low',0.),
    ('TailLowIdle',3.,tail_low_idle,'꼬리 내린 채 쉬기',True,'tail-low','tail-low',0.),
    ('TailRaise',1.4,lambda t:tail(t,0.,lowered=1-smooth(t/1.4)),'꼬리 다시 올리기',False,'tail-low','stand',0.),
]

def evaluated():
    bpy.context.view_layer.update()
    return np.array([v.co[:] for v in pet.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices])

def render(name, side=False):
    target=Vector((0,.015,.15)); cam=scene.camera
    cam.data.ortho_scale=.52
    cam.location=target+Vector((1,-.03,.12) if side else (.65,-1,.33))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)

if '--probe' in sys.argv:
    for name,pose in [('sit',sit),('lie',lie)]:
        reset();pose();co=evaluated()
        print('POSE',name,'minz',co[:,2].min(),flush=True)
        for n in ['Pelvis','Chest','Head','Fore.Upper.L','Fore.Lower.L','Hind.Upper.L','Hind.Lower.L']:
            pb=rig.pose.bones[n]; print(n,tuple(pb.head),tuple(pb.tail),flush=True)
        render('probe-'+name);render('probe-'+name+'-side',True)
    raise SystemExit

base=np.array([v.co[:] for v in pet.data.vertices])
smile=np.array([v.co[:] for v in pet.data.shape_keys.key_blocks['Smile'].data])
edges=np.array([e.vertices[:] for e in pet.data.edges])
report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'clips':{}}
endpoints={}; manifest=[]
for name,seconds,pose,label,loop,entry,exit_state,speed in CLIPS:
    action=bpy.data.actions.new(name);action.use_fake_user=True
    rig.animation_data.action=action
    count=round(seconds*30)+1
    first=None;previous=None
    check={'frames':count,'min_z':1.,'max_ik_error':0.,'max_p99_edge_stretch':1.,'max_frame_displacement':0.}
    for frame in range(1,count+1):
        scene.frame_set(frame);reset();pose((frame-1)/30)
        co=evaluated();assert np.isfinite(co).all()
        check['min_z']=min(check['min_z'],float(co[:,2].min()))
        before=base+(smile-base)*rig['Smile']
        lengths=np.linalg.norm(before[edges[:,0]]-before[edges[:,1]],axis=1)
        strain=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1)[lengths>.0015]/lengths[lengths>.0015]
        check['max_p99_edge_stretch']=max(check['max_p99_edge_stretch'],float(np.quantile(strain,.99)))
        for end in ['Fore','Hind']:
            for side in ['L','R']:
                target=f'MCH.Carpus.{side}' if end=='Fore' else f'MCH.Hock.{side}'
                error=(rig.pose.bones[f'{end}.Lower.{side}'].tail-rig.pose.bones[target].head).length
                check['max_ik_error']=max(check['max_ik_error'],error)
        if first is None:first=co.copy()
        if previous is not None:check['max_frame_displacement']=max(check['max_frame_displacement'],float(np.linalg.norm(co-previous,axis=1).max()))
        previous=co.copy()
        for pb in rig.pose.bones:
            if pb.name.startswith(('MCH.Neck.','MCH.HeadGaze')):continue
            pb.keyframe_insert('location',frame=frame,group=pb.name)
            pb.keyframe_insert('rotation_euler',frame=frame,group=pb.name)
        for prop in ['Smile','IK']:rig.keyframe_insert(data_path='["'+prop+'"]',frame=frame)
    check['endpoint_difference']=float(np.max(np.abs(first-co)))
    endpoints[name]=(first,co)
    print('CLIP_CHECK',name,json.dumps(check),flush=True)
    assert check['min_z']>-.0015,(name,check)
    assert check['max_ik_error']<.001,(name,check)
    if loop:assert check['endpoint_difference']<1e-5,(name,check)
    report['clips'][name]=check
    rig.animation_data.action=None
    track=rig.animation_data.nla_tracks.new();track.name=name
    strip=track.strips.new(name,1,action);strip.extrapolation='NOTHING';strip.blend_type='REPLACE';track.mute=True
    manifest.append({'name':name,'label':label,'duration_seconds':seconds,'loop':loop,'entry_state':entry,'exit_state':exit_state,'forward_speed_mps':speed})

for left,right in [('SitDown','SitIdle'),('SitIdle','SitUp'),('LieDown','LieIdle'),('LieIdle','LieUp'),('TailLower','TailLowIdle'),('TailLowIdle','TailRaise')]:
    error=float(np.abs(endpoints[left][1]-endpoints[right][0]).max())
    assert error<1e-5,(left,right,error)
report['transition_endpoints_match']=True
scene.name='BongguEveryday';scene.frame_start=1;scene.frame_end=91
for track in rig.animation_data.nla_tracks:track.mute=track.name!='Idle'
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);pet.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bonggu-v2-everyday.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'bonggu-v2-everyday.glb'),export_format='GLB',use_selection=True,export_apply=False,
    export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_skins=True,
    export_morph=True,export_morph_animation=True,export_def_bones=True,export_anim_slide_to_zero=True,
    export_optimize_animation_size=True)
(OUT/'motion-checks.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT/'clips.json').write_text(json.dumps({'model':'bonggu-v2-everyday.glb','blender':'bonggu-v2-everyday.blend','fps':30,'forward_axis':'-Y in Blender; +Z in glTF','units':'metres','root_motion':False,'clips':manifest,'previous_behaviors':'../animations/bonggu-v2-behaviors.glb','locomotion_blend_seconds':.18},ensure_ascii=False,indent=2)+'\n')
print('EXPORTED',flush=True)

if '--preview' in sys.argv:
    for name,seconds,pose,*_ in CLIPS:
        for track in rig.animation_data.nla_tracks:track.mute=track.name!=name
        for f in sorted(set([1,round(seconds*15)+1,round(seconds*30)+1])):
            scene.frame_set(f);render(f'{name}-{f:03}');render(f'{name}-{f:03}-side',True)
    print('STILLS_DONE',flush=True)
