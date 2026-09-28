"""Bonggu quadruped: editable FK/IK controls, localized skin weights, Smile preserved."""
import bpy,math,json,hashlib,numpy as np
from pathlib import Path
from mathutils import Vector,Matrix
OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'expressions/smile/refined/bonggu-v2-smile.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene
pet=next(o for o in scene.objects if o.type=='MESH');pet.name='Bonggu.Body'
pet.data.shape_keys.animation_data_clear();pet.data.shape_keys.key_blocks['Smile'].value=0
co=np.array([v.co[:] for v in pet.data.vertices]);original=co.copy()
smile_original=np.array([v.co[:] for v in pet.data.shape_keys.key_blocks['Smile'].data])
arm=bpy.data.armatures.new('Bonggu.Skeleton');rig=bpy.data.objects.new('Bonggu.Rig',arm);scene.collection.objects.link(rig)
rig.show_in_front=True;arm.display_type='OCTAHEDRAL'
collections={n:arm.collections.new(n) for n in ['Main controls','Paw IK','Bend direction','Spine and head','Legs','Toes','Ears','Tail','Mechanism']}
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
spec={}
def bone(name,a,b,parent=None,group='Spine and head',deform=True):
 eb=arm.edit_bones.new(name);eb.head=a;eb.tail=b;eb.use_deform=deform
 if parent:eb.parent=arm.edit_bones[parent]
 collections[group].assign(eb);spec[name]={'head':list(a),'tail':list(b),'parent':parent,'group':group,'deform':deform}
 return name
bone('CTRL.Root',(0,0,0),(0,0,.025),group='Main controls',deform=False)
bone('CTRL.Body',(0,.07,.155),(0,.07,.185),'CTRL.Root','Main controls',False)
core_points=[(0,.145,.150),(0,.119,.165),(0,.083,.165),(0,.042,.166),(0,.005,.167),(0,-.035,.176),(0,-.075,.185),(0,-.099,.213),(0,-.120,.239),(0,-.135,.289)]
core=['Pelvis','Spine.01','Spine.02','Spine.03','Spine.04','Chest','Neck.01','Neck.02','Head']
for i,n in enumerate(core):bone(n,core_points[i],core_points[i+1],'CTRL.Body' if i==0 else core[i-1])
limbs={};toe_specs={};ear_names={}
for side,s in [('L',1),('R',-1)]:
 ep=[(s*.043,-.117,.290),(s*.062,-.118,.274),(s*.078,-.116,.249),(s*.081,-.111,.224),(s*.073,-.107,.203)]
 ear_names[side]=[]
 for i in range(4):
  n=f'Ear.{i+1:02}.{side}';bone(n,ep[i],ep[i+1],'Head' if i==0 else ear_names[side][-1],'Ears');ear_names[side].append(n)
 for end in ['Fore','Hind']:
  if end=='Fore':
   bone('Scapula.'+side,(s*.036,-.057,.177),(s*.044,-.073,.144),'Chest','Legs')
   pts=[(s*.044,-.073,.144),(s*.043,-.053,.089),(s*.043,-.070,.028),(s*.044,-.085,.012)]
   names=[f'Fore.Upper.{side}',f'Fore.Lower.{side}',f'Fore.Paw.{side}'];parent='Scapula.'+side
   pole=(s*.044,.028,.088)
  else:
   pts=[(s*.049,.143,.153),(s*.051,.128,.101),(s*.052,.176,.054),(s*.056,.172,.021),(s*.057,.162,.011)]
   names=[f'Hind.Upper.{side}',f'Hind.Lower.{side}',f'Hind.Hock.{side}',f'Hind.Paw.{side}'];parent='Pelvis'
   pole=(s*.051,.060,.100)
  for j,n in enumerate(names):bone(n,pts[j],pts[j+1],parent if j==0 else names[j-1],'Legs')
  ctrl=f'CTRL.{end}Paw.{side}';bone(ctrl,pts[-2],pts[-1],'CTRL.Root','Paw IK',False)
  pole_name=f'CTRL.{end}Pole.{side}';bone(pole_name,pole,tuple(Vector(pole)+Vector((0,0,.015))),'CTRL.Root','Bend direction',False)
  target=ctrl
  if end=='Hind':target=bone('MCH.Hock.'+side,pts[2],pts[3],ctrl,'Mechanism',False)
  limbs[(end,side)]={'names':names,'points':[Vector(p) for p in pts],'target':target,'ctrl':ctrl,'pole':pole_name}
  toe_specs[(end,side)]=[]
  for digit,dx in enumerate([-.012,-.004,.004,.012],1):
   cx=pts[-1][0]+dx;y=pts[-1][1];z=.011
   p=[(cx,y+.004,z),(cx,y-.005,z-.001),(cx,y-.014,z-.003)]
   digit_names=[]
   for j in range(2):
    n=f'{end}.Toe{digit}.{j+1:02}.{side}';bone(n,p[j],p[j+1],names[-1] if j==0 else digit_names[0],'Toes');digit_names.append(n)
   toe_specs[(end,side)].append((cx,digit_names))
tail_points=[(0,.172,.205),(0,.184,.231),(-.006,.185,.260),(-.019,.175,.288),(-.027,.153,.309),(-.028,.129,.310),(-.027,.110,.292),(-.025,.110,.271),(-.022,.122,.252)]
tail=[]
for i in range(8):
 n=f'Tail.{i+1:02}';bone(n,tail_points[i],tail_points[i+1],'Pelvis' if i==0 else tail[-1],'Tail');tail.append(n)
bpy.ops.object.mode_set(mode='OBJECT')
collections['Mechanism'].is_visible=False
for pb in rig.pose.bones:pb.rotation_mode='XYZ';pb.ik_stretch=0
rig['IK']=1.;rig.id_properties_ui('IK').update(min=0,max=1,description='1: use paw IK targets. 0: directly rotate the leg bones (FK).')
rig['Smile']=0.;rig.id_properties_ui('Smile').update(min=0,max=1,description='Approved refined smile. 0 closed, 1 smiling.')
def property_driver(owner,path,prop):
 d=owner.driver_add(path).driver;d.type='AVERAGE';v=d.variables.new();v.name='control';v.type='SINGLE_PROP';v.targets[0].id=rig;v.targets[0].data_path='["'+prop+'"]'
property_driver(pet.data.shape_keys.key_blocks['Smile'],'value','Smile')
constraints=[]
for (end,side),limb in limbs.items():
 lower=rig.pose.bones[limb['names'][1]];c=lower.constraints.new('IK');c.name='Paw position';c.target=rig;c.subtarget=limb['target'];c.pole_target=rig;c.pole_subtarget=limb['pole'];c.chain_count=2;c.use_stretch=False
 property_driver(c,'influence','IK');constraints.append(c)
 for name,target in [(limb['names'][-1],limb['ctrl'])]+([(limb['names'][2],limb['target'])] if end=='Hind' else []):
  c2=rig.pose.bones[name].constraints.new('COPY_ROTATION');c2.name='Paw orientation';c2.target=rig;c2.subtarget=target;c2.owner_space='WORLD';c2.target_space='WORLD';property_driver(c2,'influence','IK')
 # Calibrate pole rotation against the measured rest knee, not a guessed roll.
 def error(angle):
  c.pole_angle=angle;bpy.context.view_layer.update()
  return (rig.pose.bones[limb['names'][0]].tail-limb['points'][1]).length
 choices=np.linspace(-math.pi,math.pi,73);best=min(choices,key=error)
 best=min(np.linspace(best-.09,best+.09,37),key=error);e=error(best)
 limb['pole_angle']=float(best);limb['rest_ik_error']=e
 assert e<.0004,(end,side,e)

# Paint anatomical masks, then softly share weights along each joint chain.
deform=[n for n,s in spec.items() if s['deform']];indices={n:i for i,n in enumerate(deform)}
W=np.zeros((len(co),len(deform)),dtype=np.float64)
def ramp(a,b,x):
 t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)
def chain_weights(names,points,radius):
 ds=[]
 for n in names:
  a=np.array(spec[n]['head']);b=np.array(spec[n]['tail']);v=b-a
  t=np.clip(((points-a)@v)/(v@v),0,1)
  ds.append(np.sum((points-(a+t[:,None]*v))**2,axis=1))
 ds=np.array(ds).T;ds-=ds.min(axis=1)[:,None]
 ws=np.exp(-ds/(2*radius**2));return ws/ws.sum(axis=1)[:,None]
def adjacent_weights(names,points):
 # Interpolate along neighboring bone centers. A core/limb transition now
 # needs four weights rather than abruptly dropping several Gaussian tails.
 centers=np.array([(np.array(spec[n]['head'])+np.array(spec[n]['tail']))/2 for n in names])
 distances=[];parameters=[]
 for a,b in zip(centers[:-1],centers[1:]):
  v=b-a;t=np.clip(((points-a)@v)/(v@v),0,1)
  distances.append(np.sum((points-(a+t[:,None]*v))**2,axis=1));parameters.append(t)
 selected=np.argmin(np.array(distances),axis=0);rows=np.arange(len(points))
 t=np.array(parameters)[selected,rows];t=t*t*(3-2*t)
 result=np.zeros((len(points),len(names)))
 result[rows,selected]=1-t;result[rows,selected+1]=t
 return result
def blend(names,weights,mask):
 global W
 W*=1-mask[:,None]
 for j,n in enumerate(names):W[:,indices[n]]+=mask*weights[:,j]
x,y,z=co.T;ax=np.abs(x)
cw=adjacent_weights(core,co)
for j,n in enumerate(core):W[:,indices[n]]=cw[:,j]
for (end,side),limb in limbs.items():
 s=1 if side=='L' else -1;side_mask=(x*s>0).astype(float)
 if end=='Fore':mask=(1-ramp(-.039,-.005,y))*(1-ramp(.082,.177,z))*ramp(.006,.021,ax)
 else:mask=ramp(.078,.133,y)*(1-ramp(.083,.161,z))*ramp(.007,.025,ax)
 names=(['Scapula.'+side] if end=='Fore' else [])+limb['names'];blend(names,adjacent_weights(names,co),mask*side_mask)
 # The source paws are continuous meshes: toe chains provide gentle curl,
 # not separation into newly modeled digits.
 names=[n for _,ns in toe_specs[(end,side)] for n in ns]
 tx=np.array([c for c,_ in toe_specs[(end,side)]])
 toe_x=np.exp(-((x[:,None]-tx)/.005)**2);toe_x/=np.maximum(toe_x.sum(axis=1)[:,None],1e-100)
 ball=limb['points'][-1].y
 tip=1-ramp(ball-.012,ball-.002,y)
 tw=np.stack([toe_x*(1-tip[:,None]),toe_x*tip[:,None]],axis=2).reshape(len(co),8)
 tm=(1-ramp(.018,.030,z))*(1-ramp(ball-.002,ball+.010,y))*mask*side_mask
 blend(names,tw,tm)
head=ramp(.185,.219,z)*(1-ramp(-.108,-.073,y));blend(['Head'],np.ones((len(co),1)),head)
for side,s in [('L',1),('R',-1)]:
 mask=ramp(.045,.071,ax)*ramp(.188,.208,z)*(1-ramp(-.066,-.040,y))*(x*s>0)
 blend(ear_names[side],chain_weights(ear_names[side],co,.016),mask)
tm=ramp(.202,.233,z)*ramp(.085,.112,y)
tw=chain_weights(tail,co,.013)
# The curled tip passes close to the rump. Its spatial proximity must not
# pull the tail root along with the last segments of the curl.
curl=ramp(.234,.263,z);tw*=curl[:,None];tw[:,0]+=1-curl
blend(tail,tw,tm)
# Keep all cavity/tongue/lip pieces attached rigidly to the same head transform.
mouth_ids={v for p in pet.data.polygons if p.material_index==1 for v in p.vertices}
for i in mouth_ids:W[i]=0;W[i,indices['Head']]=1
# A small adjacency smoothing pass avoids hard anatomical mask boundaries.
edges=np.array([e.vertices[:] for e in pet.data.edges]);degree=np.bincount(edges.ravel(),minlength=len(co))
for _ in range(3):
 neighbor=np.zeros_like(W);np.add.at(neighbor,edges[:,0],W[edges[:,1]]);np.add.at(neighbor,edges[:,1],W[edges[:,0]])
 valid=degree>0;W[valid]=.75*W[valid]+.25*neighbor[valid]/degree[valid,None]
for i in mouth_ids:W[i]=0;W[i,indices['Head']]=1
for vg in list(pet.vertex_groups):pet.vertex_groups.remove(vg)
groups=[pet.vertex_groups.new(name=n) for n in deform]
counts=np.zeros(len(deform),int)
for i,row in enumerate(W):
 chosen=np.argsort(row)[-4:];chosen=chosen[row[chosen]>1e-6];weights=row[chosen]/row[chosen].sum()
 for j,w in zip(chosen,weights):groups[j].add([i],float(w),'REPLACE');counts[j]+=1
assert np.all(counts>0),[n for n,c in zip(deform,counts) if c==0]
pet.parent=rig;mod=pet.modifiers.new('Bonggu skin','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=False

# Readable native control shapes, kept out of all model exports and renders.
shapes=bpy.data.collections.new('Rig control shapes');scene.collection.children.link(shapes);shapes.hide_render=True
def circle_shape(name,radius):
 vs=[(radius*math.cos(j*math.tau/32),0,radius*math.sin(j*math.tau/32)) for j in range(32)]
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[(j,(j+1)%32) for j in range(32)],[])
 ob=bpy.data.objects.new(name,me);shapes.objects.link(ob);ob.hide_render=True;ob.hide_set(True);return ob
ring=circle_shape('Ring control',1)
for n,s in spec.items():
 b=arm.bones[n]
 if not s['deform'] and s['group']!='Mechanism':
  pb=rig.pose.bones[n];pb.custom_shape=ring;pb.use_custom_shape_bone_size=False
  size=.11 if n=='CTRL.Root' else .043 if n=='CTRL.Body' else .025 if 'Paw' in n else .012
  pb.custom_shape_scale_xyz=(size,size,size)
  b.color.palette='THEME04' if n.endswith('.L') else 'THEME03' if n.endswith('.R') else 'THEME02'

def move(name,delta):rig.pose.bones[name].location=arm.bones[name].matrix_local.to_3x3().inverted()@Vector(delta)
def reset():
 for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
 rig['Smile']=0.;rig['IK']=1.;bpy.context.view_layer.update()
def pose(name):
 reset()
 if name=='head-turn':rig.pose.bones['Head'].rotation_euler.z=.30;rig.pose.bones['Neck.02'].rotation_euler.y=.08;rig['Smile']=1.
 if name=='paw-lift':move('CTRL.ForePaw.L',(0,-.012,.025));rig.pose.bones['Fore.Paw.L'].rotation_euler.x=.1
 if name=='crouch':move('CTRL.Body',(0,0,-.020))
 if name=='tail-wag':
  for j,n in enumerate(tail):rig.pose.bones[n].rotation_euler.z=.12*math.cos(j*.45)
 if name=='ears':
  for side,s in [('L',1),('R',-1)]:
   for j,n in enumerate(ear_names[side]):rig.pose.bones[n].rotation_euler.y=s*.09
 if name=='toe-curl':
  move('CTRL.ForePaw.L',(0,-.010,.020))
  for _,ns in toe_specs[('Fore','L')]:
   for n in ns:rig.pose.bones[n].rotation_euler.x=.16
 bpy.context.view_layer.update()

scene.render.resolution_x=1000;scene.render.resolution_y=900;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
cam=scene.camera;target=Vector((0,.018,.165));cam.data.ortho_scale=.52
cam.location=target+Vector((.65,-1,.33));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
checks={}
for name in ['rest','head-turn','paw-lift','crouch','tail-wag','ears','toe-curl']:
 pose(name);scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 ev=pet.evaluated_get(bpy.context.evaluated_depsgraph_get());coords=np.array([v.co[:] for v in ev.data.vertices])
 assert np.isfinite(coords).all()
 checks[name]={'min_z':float(coords[:,2].min()),'max_displacement':float(np.linalg.norm(coords-co,axis=1).max())}
reset()
assert np.array_equal(original,np.array([v.co[:] for v in pet.data.vertices]))
assert np.array_equal(smile_original,np.array([v.co[:] for v in pet.data.shape_keys.key_blocks['Smile'].data]))
rig['usage']='Pose Mode: move CTRL.*Paw; move CTRL.Body for body height; IK=0 for FK. Smile controls the preserved expression.'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.shading.type='MATERIAL';area.spaces.active.region_3d.view_distance=.65;area.spaces.active.region_3d.view_location=(0,.02,.16)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);pet.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bonggu-v2-rigged.blend'))
report={'source':str(SOURCE.relative_to(OUT.parent)),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'bones':len(spec),'deform_bones':len(deform),'max_vertex_influences':max(len(v.groups) for v in pet.data.vertices),'weighted_vertices_per_bone':dict(zip(deform,counts.tolist())),'rest_ik_errors':{'.'.join(k):v['rest_ik_error'] for k,v in limbs.items()},'pose_checks':checks,'mesh_coordinates_unchanged':True,'smile_coordinates_unchanged':True,'skeleton':spec}
(OUT/'rig-definition.json').write_text(json.dumps(report,indent=2)+'\n')
print('RIG_BUILT',json.dumps({k:v for k,v in report.items() if k not in ['skeleton','weighted_vertices_per_bone']}),flush=True)
