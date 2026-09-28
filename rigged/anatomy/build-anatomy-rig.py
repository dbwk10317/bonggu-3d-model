"""Separate canine carpus/tarsus flexion, pad contact and toe-off controls.

This is an animation approximation fitted to the illustrated mesh, not a
subject-specific biomechanical reconstruction. Original appearance is immutable.
"""
import bpy, math, json, hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix

OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'bonggu-v2-rigged.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.filepaths.save_version=0
rig=bpy.data.objects['Bonggu.Rig'];pet=bpy.data.objects['Bonggu.Body'];scene=bpy.context.scene
rig.animation_data_clear()
for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
rig['Smile']=0.;rig['IK']=0.
original=np.array([v.co[:] for v in pet.data.vertices]);co=original.copy()
saved_weights={v.index:{pet.vertex_groups[g.group].name:g.weight for g in v.groups} for v in pet.data.vertices}
for pb in rig.pose.bones:
    for c in list(pb.constraints):pb.constraints.remove(c)
# Old constraints were removed; discard their now orphaned influence drivers.
if rig.animation_data:
    for fc in list(rig.animation_data.drivers):rig.animation_data.drivers.remove(fc)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT');arm=rig.data
controls=arm.collections.new('Carpus · hock · toe-off')
neck_controls=arm.collections.new('Neck · gaze')
mechanism=arm.collections['Mechanism'];legs=arm.collections['Legs']
def new(name,head,tail,parent,collection,deform=False):
    b=arm.edit_bones.new(name);b.head=head;b.tail=tail;b.parent=arm.edit_bones[parent]
    b.use_deform=deform;collection.assign(b);return b
def set_bone(name,head,tail,parent=None):
    b=arm.edit_bones[name];b.head=head;b.tail=tail
    if parent:b.parent=arm.edit_bones[parent]
    # Downward limb bones get local X along the anatomical hinge direction.
    b.align_roll(Vector((0,1,0)))
    return b
chains={}
# Five cervical regions separate lower-neck reach, upper rotation and skull nod.
# These are functional groups, not a claim to reproduce each of seven vertebrae.
neck_points=[(0,-.075,.185),(0,-.087,.199),(0,-.099,.213),(0,-.1095,.226),(0,-.116,.233),(0,-.120,.239)]
neck_names=[f'Neck.{i:02}' for i in range(1,6)]
for i,name in enumerate(neck_names):
    parent='Chest' if i==0 else neck_names[i-1]
    if name not in arm.edit_bones:new(name,neck_points[i],neck_points[i+1],parent,arm.collections['Spine and head'],True)
    else:
        b=arm.edit_bones[name];b.head=neck_points[i];b.tail=neck_points[i+1];b.parent=arm.edit_bones[parent]
    # Match the original neck's local X; preserve local FK as an additive layer.
    b=arm.edit_bones[name];b.roll=0
    # Vertical mechanism axes keep gaze yaw separate from neck-axis twist.
    # The deform segment still follows the anatomical slope of the neck.
    mch=new('MCH.'+name,b.head,b.head+Vector((0,0,.018)),parent,mechanism);mch.roll=0;b.parent=mch
head=arm.edit_bones['Head'];mch=new('MCH.HeadGaze',head.head,head.head+Vector((0,0,.018)),'Neck.05',mechanism);mch.roll=0;head.parent=mch
for name,point in [('CTRL.NeckBase',(0,-.075,.185)),('CTRL.Look',(0,-.145,.285))]:
    b=new(name,point,tuple(Vector(point)+Vector((0,0,.03))),'CTRL.Body',neck_controls)
for side,s in [('L',1),('R',-1)]:
    for end in ['Fore','Hind']:
        if end=='Fore':
            points=[(s*.044,-.073,.144),(s*.044,-.048,.101),(s*.044,-.072,.048),(s*.044,-.085,.014),(s*.044,-.094,.010)]
            names=[f'Fore.Upper.{side}',f'Fore.Lower.{side}',f'Fore.Metacarpus.{side}',f'Fore.Paw.{side}']
            new(names[2],points[2],points[3],names[1],legs,True)
            parent='Scapula.'+side; joint='Carpus';target='MCH.Carpus.'+side
            foot=co[(co[:,0]*s>0)&(co[:,1]<-.02)&(co[:,2]<.016)]
            toe=(s*.044,float(foot[:,1].min()),float(foot[:,2].min()))
        else:
            points=[(s*.052,.143,.153),(s*.052,.114,.101),(s*.056,.176,.054),(s*.056,.172,.021),(s*.057,.162,.011)]
            names=[f'Hind.Upper.{side}',f'Hind.Lower.{side}',f'Hind.Hock.{side}',f'Hind.Paw.{side}']
            parent='Pelvis';joint='Hock';target='MCH.Hock.'+side
            foot=co[(co[:,0]*s>0)&(co[:,1]>.05)&(co[:,2]<.016)]
            toe=(s*.057,float(foot[:,1].min()),float(foot[:,2].min()))
        for i,n in enumerate(names):set_bone(n,points[i],points[i+1],parent if i==0 else names[i-1])
        ctrl=f'CTRL.{end}Paw.{side}'
        roll=f'CTRL.{end}ToeRoll.{side}'
        new(roll,toe,tuple(Vector(toe)+Vector((0,0,.022))),ctrl,controls)
        ball=points[3]
        fold=f'CTRL.{joint}.{side}'
        new(fold,ball,tuple(Vector(ball)+Vector((0,0,.025))),roll,controls)
        if target in arm.edit_bones:
            b=set_bone(target,points[2],points[3],fold)
        else:b=new(target,points[2],points[3],fold,mechanism)
        b.align_roll(Vector((0,1,0)))
        pad=f'MCH.{end}Pad.{side}'
        b=new(pad,points[3],points[4],roll,mechanism);b.align_roll(Vector((0,1,0)))
        chains[end+'.'+side]={'bones':names,'points':points,'control':ctrl,'roll':roll,'fold':fold,'target':target,'pad':pad,'pole':f'CTRL.{end}Pole.{side}'}
bpy.ops.object.mode_set(mode='OBJECT')

def drive(owner,path):
    d=owner.driver_add(path).driver;d.type='AVERAGE'
    var=d.variables.new();var.name='ik';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='["IK"]'

for key,chain in chains.items():
    end,side=key.split('.')
    lower=rig.pose.bones[chain['bones'][1]]
    c=lower.constraints.new('IK');c.name='Anatomical limb IK';c.target=rig;c.subtarget=chain['target']
    c.pole_target=rig;c.pole_subtarget=chain['pole'];c.chain_count=2;c.use_stretch=False;drive(c,'influence')
    rig['IK']=1.
    desired=Vector(chain['points'][1])
    def error(angle):
        c.pole_angle=angle;bpy.context.view_layer.update()
        return (rig.pose.bones[chain['bones'][0]].tail-desired).length
    best=min(np.linspace(-math.pi,math.pi,145),key=error)
    best=min(np.linspace(best-.05,best+.05,101),key=error);chain['pole_angle']=float(best)
    assert error(best)<.00015,(key,error(best))
    # Hinge the elbow/stifle; shoulder/hip retain the small out-of-plane freedom.
    lower.lock_ik_y=True;lower.lock_ik_z=True
    lower.use_ik_limit_x=True
    lower.ik_min_x=-2.15 if end=='Fore' else -.9
    lower.ik_max_x=.75 if end=='Fore' else 2.1
    for name,target in [(chain['bones'][2],chain['target']),(chain['bones'][3],chain['pad'])]:
        c=rig.pose.bones[name].constraints.new('COPY_ROTATION');c.name='Independent distal orientation'
        c.target=rig;c.subtarget=target;c.owner_space='WORLD';c.target_space='WORLD';drive(c,'influence')
    for name,limits in [(chain['fold'],(-1.4,1.1)),(chain['roll'],(-.25,.75))]:
        pb=rig.pose.bones[name];pb.rotation_mode='XYZ';pb.lock_location=(True,True,True);pb.lock_scale=(True,True,True);pb.lock_rotation=(False,True,True)
        con=pb.constraints.new('LIMIT_ROTATION');con.name='Animation working range'
        con.owner_space='LOCAL';con.use_limit_x=con.use_limit_y=con.use_limit_z=True;con.min_x,con.max_x=limits
        # Working bounds for this stylized rig, not measured biological limits.
        chain.setdefault('control_limits',{})[name]=limits
        pb.custom_shape=bpy.data.objects.get('Ring control');pb.use_custom_shape_bone_size=False;pb.custom_shape_scale_xyz=(.014,.014,.014)
        rig.data.bones[name].color.palette='THEME04' if side=='L' else 'THEME03'
    rig.pose.bones[chain['fold']]['purpose']='Rotate X: fold carpus/tarsus while the pad stays planted.'
    rig.pose.bones[chain['roll']]['purpose']='Rotate X positive: push off around the toe contact point.'

pitch=[.10,.15,.20,.10,.35,.10]
yaw=[.05,.10,.15,.50,.05,.15]
roll=[.05,.10,.15,.20,.20,.30]
base_factors=[.6,.3,.1,0,0,0]
for i,name in enumerate(['MCH.'+n for n in neck_names]+['MCH.HeadGaze']):
    pb=rig.pose.bones[name];pb.rotation_mode='XYZ'
    for axis,weights in enumerate([pitch,yaw,roll]):
        d=pb.driver_add('rotation_euler',axis).driver;d.type='SCRIPTED'
        for variable,ctrl in [('look','CTRL.Look'),('base','CTRL.NeckBase')]:
            v=d.variables.new();v.name=variable;v.type='SINGLE_PROP';v.targets[0].id=rig
            v.targets[0].data_path=f'pose.bones["{ctrl}"].rotation_euler[{axis}]'
        d.expression=f'{weights[i]}*look+{base_factors[i]}*base'
for name in ['CTRL.NeckBase','CTRL.Look']:
    pb=rig.pose.bones[name];pb.rotation_mode='XYZ';pb.lock_location=(True,True,True);pb.lock_scale=(True,True,True)
    pb.custom_shape=bpy.data.objects.get('Ring control');pb.use_custom_shape_bone_size=False;pb.custom_shape_scale_xyz=(.025,.025,.025)
    rig.data.bones[name].color.palette='THEME02'
    pb['purpose']='X nod/down/up, Y left/right, Z tilt. Distributed over cervical chain. Local Neck / Head FK remains additive.'

# Repaint only limb influences. Face, body masks, ears, tail and source UV stay.
deform=[b.name for b in rig.data.bones if b.use_deform];index={n:i for i,n in enumerate(deform)}
W=np.zeros((len(co),len(deform)))
for i,row in saved_weights.items():
    for n,w in row.items():W[i,index[n]]=w
def adjacent(names):
    centers=np.array([(rig.data.bones[n].head_local+rig.data.bones[n].tail_local)/2 for n in names])
    ds=[];ts=[]
    for a,b in zip(centers[:-1],centers[1:]):
        v=b-a;t=np.clip((co-a)@v/(v@v),0,1);ts.append(t);ds.append(np.sum((co-a-t[:,None]*v)**2,axis=1))
    pick=np.argmin(ds,axis=0);rows=np.arange(len(co));t=np.array(ts)[pick,rows];t=t*t*(3-2*t)
    w=np.zeros((len(co),len(names)));w[rows,pick]=1-t;w[rows,pick+1]=t
    return w
for key,chain in chains.items():
    names=chain['bones'];ids=[index[n] for n in names];amount=W[:,ids].sum(axis=1)
    W[:,ids]=adjacent(names)*amount[:,None]
ids=[index[n] for n in neck_names];amount=W[:,ids].sum(axis=1)
W[:,ids]=adjacent(neck_names)*amount[:,None]
edges=np.array([e.vertices[:] for e in pet.data.edges]);degree=np.bincount(edges.ravel(),minlength=len(co))
limb_names={n for c in chains.values() for n in c['bones']};mask=np.array([any(n in limb_names for n in row) for row in saved_weights.values()])
for _ in range(4):
    neighborhood=np.zeros_like(W);np.add.at(neighborhood,edges[:,0],W[edges[:,1]]);np.add.at(neighborhood,edges[:,1],W[edges[:,0]])
    valid=(degree>0)&mask;W[valid]=.75*W[valid]+.25*neighborhood[valid]/degree[valid,None]
for vg in list(pet.vertex_groups):pet.vertex_groups.remove(vg)
groups=[pet.vertex_groups.new(name=n) for n in deform]
for i,row in enumerate(W):
    chosen=np.argsort(row)[-4:];chosen=chosen[row[chosen]>1e-7];weights=row[chosen]/row[chosen].sum()
    for j,w in zip(chosen,weights):groups[j].add([i],float(w),'REPLACE')
for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4);pb.ik_stretch=0
rig['IK']=1.;rig['Smile']=0.
rig['usage']='Paw translates leg; CTRL.Carpus / Hock X folds distal joint; CTRL.*ToeRoll X positive pushes off. CTRL.Look X nod, Y turn, Z tilt; CTRL.NeckBase reaches lower neck. IK=0 for FK. Smile preserved.'
for b in rig.data.bones:
    if b.name.startswith('MCH.'):b.hide=True
bpy.context.view_layer.update()
rest=np.array([v.co[:] for v in pet.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices])
assert np.max(np.abs(rest-original))<.0002,np.max(np.abs(rest-original))
assert np.array_equal(original,np.array([v.co[:] for v in pet.data.vertices]))
report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'native_bones':len(arm.bones),'deform_bones':len(deform),'rest_max_error_m':float(np.abs(rest-original).max()),'chains':chains,'neck':{'bones':neck_names,'points':neck_points,'gaze_pitch_weights':pitch,'gaze_yaw_weights':yaw,'gaze_tilt_weights':roll,'base_weights':base_factors},
 'references':[
 {'url':'https://vetmed.illinois.edu/imaging_anatomy/canine/forelimb/carpus_foot/ex02/ex02.html','use':'Separate carpus, metacarpus and digital anatomy.'},
 {'url':'https://vetmed.illinois.edu/demo-sa-orthopedics/orthopedic-exam-forelimb/','use':'Forelimb joint flexion and extension; do not equate passive clinical ROM with gait.'},
 {'url':'https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2020.00150/full','use':'Coupled hip, stifle and tarsal motion across stance and swing. Not subject-specific motion data.'},
 {'url':'https://www.frontiersin.org/journals/veterinary-science/articles/10.3389/fvets.2021.709967/full','use':'Upper cervical nod, axial rotation and coupled lateral motion; use as qualitative guidance, not a Shih Tzu numerical limit.'},
 {'url':'https://docs.blender.org/manual/id/5.1/addons/rigging/rigify/rig_types/limbs.html','use':'Four/five-link paw-chain and distinct front/rear IK design reference. This file extends the existing rig, not a Rigify-generated skeleton.'}],
 'limitations':['Joint centers are fitted to the stylized mesh; no radiographs of Bonggu.','Working rotation bounds are animator safeguards, not veterinary joint ROM.','Continuous source toes support gentle curl, not separated digit splaying.']}
(OUT/'rig-definition.json').write_text(json.dumps(report,indent=2)+'\n')
scene.frame_start=1;scene.frame_end=180;scene.frame_set(1)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bonggu-v2-anatomy-rig.blend'))
print('ANATOMY_RIG_BUILT',json.dumps({k:v for k,v in report.items() if k not in ['chains','references','limitations']}),flush=True)
