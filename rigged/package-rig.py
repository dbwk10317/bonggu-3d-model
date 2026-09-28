"""Demonstrate the editable rig and bake the same evaluated motion into GLB."""
import bpy,json,math,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
out=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(out/'bonggu-v2-rigged.blend'))
bpy.context.preferences.filepaths.save_version=0
rig=bpy.data.objects['Bonggu.Rig'];pet=bpy.data.objects['Bonggu.Body'];scene=bpy.context.scene
scene.name='RigDemo'
definition=json.loads((out/'rig-definition.json').read_text())
scene.render.fps=30;scene.frame_start=1;scene.frame_end=181
def move(name,delta):rig.pose.bones[name].location=rig.data.bones[name].matrix_local.to_3x3().inverted()@Vector(delta)
def envelope(t,a,b):return math.sin(math.pi*max(0,min(1,(t-a)/(b-a))))**2 if a<t<b else 0.
animated=['CTRL.Body','CTRL.ForePaw.L','CTRL.HindPaw.R','Spine.02','Spine.03','Neck.01','Neck.02','Head']
animated += [b.name for b in rig.pose.bones if b.name.startswith(('Tail.','Ear.','Fore.Toe'))]
checks={'min_z':1.,'max_ik_target_error':0.,'max_edge_stretch':1.}
base=np.array([v.co[:] for v in pet.data.vertices]);edges=np.array([e.vertices[:] for e in pet.data.edges])
length=np.linalg.norm(base[edges[:,0]]-base[edges[:,1]],axis=1)
usable=length>.0015
first=last=None
for f in range(1,182):
 scene.frame_set(f);t=(f-1)/180
 for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
 turn=envelope(t,.03,.46);paw=envelope(t,.25,.57);crouch=envelope(t,.59,.91)
 move('CTRL.Body',(0,0,-.018*crouch))
 move('CTRL.ForePaw.L',(0,-.012*paw,.028*paw))
 move('CTRL.HindPaw.R',(0,-.006*envelope(t,.82,1),.010*envelope(t,.82,1)))
 rig.pose.bones['Head'].rotation_euler.z=.23*math.sin(math.tau*t)*turn
 rig.pose.bones['Neck.02'].rotation_euler.y=.065*turn
 rig.pose.bones['Neck.01'].rotation_euler.x=.025*turn
 rig.pose.bones['Spine.02'].rotation_euler.x=.025*crouch
 rig.pose.bones['Spine.03'].rotation_euler.x=-.025*crouch
 fade=math.sin(math.pi*t)**2
 for j in range(8):rig.pose.bones[f'Tail.{j+1:02}'].rotation_euler.z=(.08 if j==0 else .023)*math.sin(math.tau*3*t-j*.42)*fade
 for side,s in [('L',1),('R',-1)]:
  for j in range(4):rig.pose.bones[f'Ear.{j+1:02}.{side}'].rotation_euler.y=s*.035*math.sin(math.tau*2*t-j*.5)*fade
 for pb in rig.pose.bones:
  if pb.name.startswith('Fore.Toe') and pb.name.endswith('.L'):pb.rotation_euler.x=.12*paw
 rig['Smile']=envelope(t,.08,.94);rig['IK']=1.
 for name in animated:
  pb=rig.pose.bones[name];pb.keyframe_insert('location',frame=f,group=name);pb.keyframe_insert('rotation_euler',frame=f,group=name)
 rig.keyframe_insert(data_path='["Smile"]',frame=f)
 bpy.context.view_layer.update()
 ev=pet.evaluated_get(bpy.context.evaluated_depsgraph_get());co=np.array([v.co[:] for v in ev.data.vertices]);assert np.isfinite(co).all()
 checks['min_z']=min(checks['min_z'],float(co[:,2].min()))
 # Exclude the intentional duplicate lip seam and tiny internal mouth pieces.
 checks['max_edge_stretch']=max(checks['max_edge_stretch'],float(np.max(np.linalg.norm(co[edges[:,0]][usable]-co[edges[:,1]][usable],axis=1)/length[usable])))
 for end in ['Fore','Hind']:
  for side in ['L','R']:
   target=f'CTRL.ForePaw.{side}' if end=='Fore' else f'MCH.Hock.{side}'
   e=(rig.pose.bones[f'{end}.Lower.{side}'].tail-rig.pose.bones[target].head).length
   checks['max_ik_target_error']=max(checks['max_ik_target_error'],e)
 if f==1:first=co.copy()
 if f==181:last=co.copy()
assert checks['min_z']>-.001,checks
assert checks['max_ik_target_error']<.0005,checks
checks['loop_error']=float(np.max(np.abs(first-last)));assert checks['loop_error']<1e-5
rig.animation_data.action.name='RigDemo'
rig.animation_data.action.use_fake_user=True
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);pet.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'bonggu-v2-rigged.blend'))
bpy.ops.export_scene.gltf(filepath=str(out/'bonggu-v2-rigged.glb'),export_format='GLB',use_selection=True,export_apply=False,
 export_animations=True,export_animation_mode='SCENE',export_anim_scene_split_object=False,export_nla_strips_merged_animation_name='RigDemo',
 export_force_sampling=True,export_skins=True,export_morph=True,export_morph_animation=True,export_def_bones=True,export_anim_slide_to_zero=True)
(out/'animation-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print('EXPORTED',json.dumps(checks),flush=True)
scene.render.resolution_x=1000;scene.render.resolution_y=900
for f in [1,55,91,136]:
 scene.frame_set(f);scene.render.filepath=str(out/f'verify-source-{f:03}.png');bpy.ops.render.render(write_still=True)
scene.frame_set(91);scene.render.filepath=str(out/'rig-preview.png');bpy.ops.render.render(write_still=True)
scene.render.resolution_x=800;scene.render.resolution_y=720
frames=out/'preview-frames';frames.mkdir(exist_ok=True);scene.render.filepath=str(frames/'rig-')
bpy.ops.render.render(animation=True)
print('PREVIEW_DONE',flush=True)

# Render a translucent anatomical placement diagram from the actual bone data.
scene.frame_set(1);rig.animation_data_clear()
for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
rig['Smile']=0.;rig['IK']=0.;bpy.context.view_layer.update()
ghost=bpy.data.materials.new('Diagram ghost');ghost.use_nodes=True;nt=ghost.node_tree;nt.nodes.clear()
transparent=nt.nodes.new('ShaderNodeBsdfTransparent');emit=nt.nodes.new('ShaderNodeEmission');emit.inputs[0].default_value=(.45,.39,.32,1)
mix=nt.nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.09;nt.links.new(transparent.outputs[0],mix.inputs[1]);nt.links.new(emit.outputs[0],mix.inputs[2])
output=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(mix.outputs[0],output.inputs['Surface']);ghost.surface_render_method='DITHERED'
pet.data.materials.clear();pet.data.materials.append(ghost)
for p in pet.data.polygons:p.material_index=0
colors={'Spine and head':(.05,.29,.34),'Legs':(.20,.23,.55),'Toes':(.40,.16,.40),'Ears':(.65,.30,.055),'Tail':(.08,.42,.23)}
mats={}
for group,color in colors.items():
 m=bpy.data.materials.new(group);m.use_nodes=True;n=m.node_tree.nodes;n.clear();e=n.new('ShaderNodeEmission');e.inputs[0].default_value=(*color,1);o=n.new('ShaderNodeOutputMaterial');m.node_tree.links.new(e.outputs[0],o.inputs[0]);mats[group]=m
for n,sp in definition['skeleton'].items():
 if not sp['deform']:continue
 a=Vector(sp['head']);b=Vector(sp['tail']);length=(b-a).length;r=min(.0035,length*.12)
 bpy.ops.mesh.primitive_cone_add(vertices=6,radius1=r,radius2=.0005,depth=length,location=(a+b)/2)
 ob=bpy.context.object;ob.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();ob.data.materials.append(mats[sp['group']])
 bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=min(.0022,length*.10),location=a)
 bpy.context.object.data.materials.append(mats[sp['group']])
scene.render.resolution_x=1400;scene.render.resolution_y=1050
target=Vector((0,.015,.16));cam=scene.camera;cam.data.ortho_scale=.57
cam.location=target+Vector((1,-.55,.3));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(out/'bone-layout.png');bpy.ops.render.render(write_still=True)
