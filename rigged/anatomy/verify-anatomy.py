"""Native rig checks and a diagnostic movie, followed by a portable GLB export."""
import bpy, json, math, hashlib, sys
import numpy as np
from pathlib import Path
from mathutils import Matrix,Vector

OUT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'bonggu-v2-anatomy-rig.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Bonggu.Rig'];pet=bpy.data.objects['Bonggu.Body']
definition=json.loads((OUT/'rig-definition.json').read_text())
source_report=json.loads((OUT.parent/'validation.json').read_text())
def sha(x):return hashlib.sha256(x).hexdigest()
def ah(x):return sha(np.array(x,dtype=np.float32).tobytes())
fingerprint={'positions':ah([v.co[:] for v in pet.data.vertices]),'faces':sha(json.dumps([list(p.vertices) for p in pet.data.polygons]).encode()),'uv':ah([v.uv[:] for v in pet.data.uv_layers.active.data]),'material_indices':sha(bytes(p.material_index for p in pet.data.polygons)),
 'shape_keys':{k.name:ah([v.co[:] for v in k.data]) for k in pet.data.shape_keys.key_blocks},'textures':sorted(sha(im.packed_file.data) for im in bpy.data.images if im.packed_file)}
assert fingerprint==source_report['source_preserved']
assert sha((OUT.parent/'bonggu-v2-rigged.blend').read_bytes())==definition['source_sha256']
assert all(abs(sum(g.weight for g in v.groups)-1)<1e-5 and len(v.groups)<=4 for v in pet.data.vertices)
def reset():
    for pb in rig.pose.bones:
        if not pb.name.startswith(('MCH.Neck.','MCH.HeadGaze')):pb.matrix_basis=Matrix.Identity(4)
    rig['IK']=1.;rig['Smile']=0.;bpy.context.view_layer.update()
def move(name,delta):rig.pose.bones[name].location=rig.data.bones[name].matrix_local.to_3x3().inverted()@Vector(delta)
def evaluate():
    bpy.context.view_layer.update()
    return np.array([v.co[:] for v in pet.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices])
checks={}
for key,c in definition['chains'].items():
    reset();pad0=rig.pose.bones[c['bones'][3]].matrix.copy();distal0=rig.pose.bones[c['bones'][2]].matrix.copy()
    rig.pose.bones[c['fold']].rotation_euler.x=-.35
    # Give the shoulder/hip enough reach while the distal joint folds.
    move('CTRL.Body',(0,0,-.012));v=evaluate()
    pad=rig.pose.bones[c['bones'][3]].matrix;distal=rig.pose.bones[c['bones'][2]].matrix
    pad_error=(pad.translation-pad0.translation).length
    angle=distal.to_quaternion().rotation_difference(distal0.to_quaternion()).angle
    assert pad_error<.00015,(key,pad_error)
    assert .34<angle<.36,(key,angle)
    assert np.isfinite(v).all()
    checks[key]={'independent_distal_rotation_deg':math.degrees(angle),'planted_pad_error_m':pad_error}
neck_checks={}
for axis,label in [(0,'nod'),(1,'yaw'),(2,'tilt')]:
    reset();original=rig.pose.bones['Head'].matrix.to_3x3().copy()
    rig.pose.bones['CTRL.Look'].rotation_euler[axis]=.5
    evaluate();delta=rig.pose.bones['Head'].matrix.to_3x3()@original.inverted()
    angles=delta.to_euler('XYZ')
    expected=0 if axis==0 else 2 if axis==1 else 1
    assert abs(abs(angles[expected])-.5)<.002,(label,list(angles))
    assert all(abs(angles[i])<.002 for i in range(3) if i!=expected),(label,list(angles))
    neck_checks[label]={'head_world_euler_degrees':[math.degrees(x) for x in angles]}
reset()
scene.render.fps=30;scene.frame_start=1;scene.frame_end=241
rig.animation_data_create();rig.animation_data.action=bpy.data.actions.new('JointStudy');rig.animation_data.action.use_fake_user=True
minz=1.;ikerror=0.
def envelope(t,a,b):return math.sin(math.pi*max(0,min(1,(t-a)/(b-a))))**2 if a<t<b else 0.
for frame in range(1,242):
    scene.frame_set(frame);reset();t=(frame-1)/30
    fore=envelope(t,.2,2.4);hind=envelope(t,2.6,4.8);push=envelope(t,5.0,6.3);crouch=envelope(t,6.4,7.9)
    move('CTRL.Body',(0,0,-.012*max(fore,hind)-.025*crouch))
    move('CTRL.ForePaw.L',(0,-.015*fore,.030*fore))
    rig.pose.bones['CTRL.Carpus.L'].rotation_euler.x=-.55*fore
    move('CTRL.HindPaw.L',(0,-.018*hind,.030*hind))
    rig.pose.bones['CTRL.Hock.L'].rotation_euler.x=-.55*hind
    for end in ['Fore','Hind']:
        rig.pose.bones[f'CTRL.{end}ToeRoll.L'].rotation_euler.x=.22*push
    v=evaluate();minz=min(minz,float(v[:,2].min()))
    for c in definition['chains'].values():
        ikerror=max(ikerror,(rig.pose.bones[c['bones'][1]].tail-rig.pose.bones[c['target']].head).length)
    for pb in rig.pose.bones:
        if pb.name.startswith(('MCH.Neck.','MCH.HeadGaze')):continue
        pb.keyframe_insert('location',frame=frame,group=pb.name);pb.keyframe_insert('rotation_euler',frame=frame,group=pb.name)
    for prop in ['IK','Smile']:rig.keyframe_insert(data_path='["'+prop+'"]',frame=frame)
assert minz>-.0015,minz
assert ikerror<.001,ikerror
action=rig.animation_data.action;rig.animation_data.action=None
track=rig.animation_data.nla_tracks.new();track.name='JointStudy';strip=track.strips.new('JointStudy',1,action);strip.extrapolation='NOTHING'
scene.frame_set(1)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bonggu-v2-anatomy-study.blend'))
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);pet.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'bonggu-v2-anatomy-study.glb'),export_format='GLB',use_selection=True,export_apply=False,export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_skins=True,export_morph=True,export_morph_animation=True,export_def_bones=True,export_anim_slide_to_zero=True,export_optimize_animation_size=True)
report={'appearance_preserved':fingerprint,'max_vertex_influences':max(len(v.groups) for v in pet.data.vertices),'independent_joint_checks':checks,'gaze_axis_checks':neck_checks,'diagnostic_min_z_m':minz,'diagnostic_max_ik_error_m':ikerror,'source_preserved':True,'bones':len(rig.data.bones),'deform_bones':sum(b.use_deform for b in rig.data.bones)}
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('RIG_CHECKED',json.dumps({k:v for k,v in report.items() if k!='appearance_preserved'}),flush=True)
target=Vector((0,.01,.15));cam=scene.camera;cam.data.ortho_scale=.53
cam.location=target+Vector((1,-.20,.12));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x=800;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
for f in [1,40,112,171,215]:
    scene.frame_set(f);scene.render.filepath=str(OUT/f'joint-{f:03}.png');bpy.ops.render.render(write_still=True)
if '--preview' in sys.argv:
    folder=OUT/'frames';folder.mkdir(exist_ok=True)
    scene.render.filepath=str(folder/'joint-');bpy.ops.render.render(animation=True)

# Actual joint overlay, sampled from this rig. Thin cones distinguish segments.
scene.frame_set(1)
ghost=bpy.data.materials.new('Joint diagram ghost');ghost.use_nodes=True;n=ghost.node_tree.nodes;n.clear()
tr=n.new('ShaderNodeBsdfTransparent');em=n.new('ShaderNodeEmission');em.inputs[0].default_value=(.48,.43,.38,1)
mix=n.new('ShaderNodeMixShader');mix.inputs[0].default_value=.10;out=n.new('ShaderNodeOutputMaterial')
ghost.node_tree.links.new(tr.outputs[0],mix.inputs[1]);ghost.node_tree.links.new(em.outputs[0],mix.inputs[2]);ghost.node_tree.links.new(mix.outputs[0],out.inputs['Surface']);ghost.surface_render_method='DITHERED'
pet.data.materials.clear();pet.data.materials.append(ghost)
for p in pet.data.polygons:p.material_index=0
palette=[(.12,.30,.43),(.25,.48,.65),(.83,.38,.12),(.22,.55,.34)]
materials=[]
for i,color in enumerate(palette):
    m=bpy.data.materials.new('Segment '+str(i));m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();e=nt.nodes.new('ShaderNodeEmission');e.inputs[0].default_value=(*color,1);o=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs[0],o.inputs[0]);materials.append(m)
diagram_chains=[c['bones'] for key,c in definition['chains'].items() if key.endswith('.L')]
diagram_chains.append(definition['neck']['bones']+['Head'])
for names in diagram_chains:
    for i,name in enumerate(names):
        material=materials[i%4]
        pb=rig.pose.bones[name];a=pb.head.copy();b=pb.tail.copy()
        bpy.ops.mesh.primitive_cone_add(vertices=10,radius1=.0027,radius2=.0010,depth=(b-a).length,location=(a+b)/2)
        ob=bpy.context.object;ob.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();ob.data.materials.append(material)
        for point in [a,b]:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.0035,location=point);bpy.context.object.data.materials.append(material)
scene.render.resolution_x=1200;scene.render.resolution_y=850
cam.data.ortho_scale=.60
scene.render.filepath=str(OUT/'joint-layout.png');bpy.ops.render.render(write_still=True)
print('STUDY_COMPLETE',flush=True)
