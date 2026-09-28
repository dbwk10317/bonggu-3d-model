"""Author three editable pet behaviors on the existing Bonggu rig."""
import bpy, math, json, hashlib, sys
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix

OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'rigged/bonggu-v2-rigged.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene;rig=bpy.data.objects['Bonggu.Rig'];pet=bpy.data.objects['Bonggu.Body']
scene.render.fps=30;scene.render.resolution_x=1000;scene.render.resolution_y=900
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
demo=rig.animation_data.action;demo.use_fake_user=True
rig.animation_data.action=None
for track in list(rig.animation_data.nla_tracks):rig.animation_data.nla_tracks.remove(track)
base=np.array([v.co[:] for v in pet.data.vertices])
smile=np.array([v.co[:] for v in pet.data.shape_keys.key_blocks['Smile'].data])
edges=np.array([e.vertices[:] for e in pet.data.edges])
def smooth(v):
    v=max(0.,min(1.,v));return v*v*(3-2*v)
def hold(t,start,attack,release,end):
    return smooth((t-start)/(attack-start))*(1-smooth((t-release)/(end-release)))
def move(name,delta):
    rig.pose.bones[name].location=rig.data.bones[name].matrix_local.to_3x3().inverted()@Vector(delta)
def rotate(name,x=0,y=0,z=0):rig.pose.bones[name].rotation_euler=(x,y,z)
def reset():
    for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
    rig['Smile']=0.;rig['IK']=1.
def appendage(t,amount,frequency):
    for j in range(8):
        rotate(f'Tail.{j+1:02}',z=amount*(1 if j==0 else .28)*math.sin(math.tau*frequency*t-j*.38))
def paw_scrabble(t):
    ready=hold(t,.15,.6,3.35,3.9)
    burst=hold(t,.65,.83,1.53,1.78)+hold(t,1.95,2.13,3.13,3.4)
    swing=math.tau*4.4*t
    move('CTRL.Body',(.0018*math.sin(swing)*burst,-.005*ready,-.014*ready+.0012*math.sin(2*swing)*burst))
    rotate('Neck.01',x=.07*ready);rotate('Neck.02',x=.09*ready)
    rotate('Head',x=.13*ready+.014*math.sin(2*swing)*burst,z=.025*math.sin(swing)*burst)
    for side,offset,sign in [('L',0,1),('R',math.pi,-1)]:
        phase=swing+offset
        # Keep a paw on the surface through the backward scratch, then lift
        # it for the forward return. The opposite paw is half a cycle behind.
        u=(phase/math.tau)%1
        if u<.55:
            travel=-.019+.034*smooth(u/.55);height=0.
        else:
            v=(u-.55)/.45
            travel=.015-.034*smooth(v);height=.023*math.sin(math.pi*v)**2
        move('CTRL.ForePaw.'+side,(0,travel*burst,height*burst))
        for j in range(4):rotate(f'Ear.{j+1:02}.{side}',y=sign*.027*math.sin(swing-.35*j)*burst)
        for digit in range(1,5):
            for joint in [1,2]:rotate(f'Fore.Toe{digit}.{joint:02}.{side}',x=.045*max(0,math.sin(phase))*burst)
    appendage(t,.045*ready,1.1)
def sniff_around(t):
    ready=hold(t,.18,.9,3.95,4.65)
    sniff=hold(t,1.05,1.2,1.95,2.15)+hold(t,2.65,2.8,3.6,3.8)
    pulse=math.sin(math.tau*4.2*t)*sniff
    scan=.19*math.sin(math.tau*(t-.7)/4.2)*ready
    move('CTRL.Body',(0,-.005*ready,-.006*ready))
    rotate('Chest',x=.025*ready)
    rotate('Neck.01',x=.07*ready+.008*pulse)
    rotate('Neck.02',x=.09*ready+.012*pulse,y=.25*scan)
    rotate('Head',x=.19*ready+.025*pulse,y=scan,z=.025*math.sin(math.tau*t/3)*ready)
    for side,sign in [('L',1),('R',-1)]:
        for j in range(4):rotate(f'Ear.{j+1:02}.{side}',y=sign*.022*math.sin(math.tau*1.2*t-.4*j)*ready)
    appendage(t,.018*ready,.6)
def gentle_howl(t):
    lift=hold(t,.25,1.3,3.8,4.8)
    voice=hold(t,1.05,1.4,3.6,4.0)
    breath=math.sin(math.tau*2.2*t)*voice
    move('CTRL.Body',(0,.002*lift,-.007*lift+.0014*breath))
    rotate('Chest',x=-.025*lift-.007*breath)
    rotate('Neck.01',x=-.13*lift)
    rotate('Neck.02',x=-.18*lift-.006*breath)
    rotate('Head',x=-.30*lift-.012*breath,z=.035*math.sin(math.tau*t/4.2)*lift)
    rig['Smile']=(.70+.075*math.sin(math.tau*2.2*t+.2))*voice
    for side,sign in [('L',1),('R',-1)]:
        for j in range(4):rotate(f'Ear.{j+1:02}.{side}',x=.022*lift,y=sign*.018*math.sin(math.tau*t-j*.4)*voice)
    appendage(t,.020*lift,.65)

clips=[('PawScrabble',4.0,paw_scrabble,36),('SniffAround',4.8,sniff_around,91),('GentleHowl',5.0,gentle_howl,76)]
report={'source':str(SOURCE.relative_to(OUT.parent)),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'fps':30,'clips':{}}
actions=[]
for name,seconds,pose,keyframe in clips:
    reset();action=bpy.data.actions.new(name);action.use_fake_user=True
    rig.animation_data.action=action
    scene.frame_start=1;scene.frame_end=round(seconds*30)+1
    check={'duration':seconds,'frames':scene.frame_end,'min_z':1.,'max_ik_error':0.,'max_edge_stretch':1.,'max_p99_edge_stretch':1.}
    first=None
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame);reset();pose((frame-1)/30)
        for pb in rig.pose.bones:
            pb.keyframe_insert('location',frame=frame,group=pb.name)
            pb.keyframe_insert('rotation_euler',frame=frame,group=pb.name)
        for prop in ['Smile','IK']:rig.keyframe_insert(data_path='["'+prop+'"]',frame=frame)
        bpy.context.view_layer.update()
        co=np.array([v.co[:] for v in pet.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices])
        assert np.isfinite(co).all()
        check['min_z']=min(check['min_z'],float(co[:,2].min()))
        before=base+(smile-base)*rig['Smile']
        a=np.linalg.norm(before[edges[:,0]]-before[edges[:,1]],axis=1)
        b=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1);strain=b[a>.0015]/a[a>.0015]
        check['max_edge_stretch']=max(check['max_edge_stretch'],float(strain.max()))
        check['max_p99_edge_stretch']=max(check['max_p99_edge_stretch'],float(np.quantile(strain,.99)))
        for end in ['Fore','Hind']:
            for side in ['L','R']:
                target=f'CTRL.ForePaw.{side}' if end=='Fore' else f'MCH.Hock.{side}'
                error=(rig.pose.bones[f'{end}.Lower.{side}'].tail-rig.pose.bones[target].head).length
                check['max_ik_error']=max(check['max_ik_error'],error)
        if first is None:first=co.copy()
    check['loop_error']=float(np.max(np.abs(first-co)))
    assert check['min_z']>-.0015,check
    assert check['max_ik_error']<.001,check
    assert check['loop_error']<1e-5,check
    report['clips'][name]=check;actions.append(action)
    for frame in [keyframe,round(seconds*30*.65)]:
        scene.frame_set(frame);scene.render.filepath=str(OUT/f'{name}-{frame:03}.png')
        bpy.ops.render.render(write_still=True)
    print('CLIP_DONE',name,json.dumps(check),flush=True)

# Native NLA tracks preserve independently selectable clips and driver sampling.
rig.animation_data.action=None
for action in [demo]+actions:
    track=rig.animation_data.nla_tracks.new();track.name=action.name
    strip=track.strips.new(action.name,1,action);strip.extrapolation='NOTHING';strip.blend_type='REPLACE'
    track.mute=action.name!='PawScrabble'
scene.frame_start=1;scene.frame_end=181;scene.frame_set(1);reset();bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);pet.select_set(True);bpy.context.view_layer.objects.active=rig
scene.name='BongguBehaviors'
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bonggu-v2-behaviors.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'bonggu-v2-behaviors.glb'),export_format='GLB',use_selection=True,export_apply=False,
    export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_skins=True,
    export_morph=True,export_morph_animation=True,export_def_bones=True,export_anim_slide_to_zero=True,
    export_optimize_animation_size=True)
(OUT/'motion-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('BEHAVIORS_EXPORTED',flush=True)

if '--preview' in sys.argv:
    scene.render.resolution_x=800;scene.render.resolution_y=720
    for name,seconds,pose,keyframe in clips:
        for track in rig.animation_data.nla_tracks:track.mute=track.name!=name
        scene.frame_end=round(seconds*30)+1
        folder=OUT/'frames'/name;folder.mkdir(parents=True,exist_ok=True)
        scene.render.filepath=str(folder/'frame-');bpy.ops.render.render(animation=True)
        print('PREVIEW_DONE',name,flush=True)
