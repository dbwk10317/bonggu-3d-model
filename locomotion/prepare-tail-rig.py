"""Free the tail from the back and retain the approved face, body and painted palette."""
import bpy,bmesh,math,numpy as np,json,hashlib
from mathutils import Vector,Matrix,Quaternion
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from pathlib import Path
OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'rigged/anatomy/bonggu-v2-anatomy-rig.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.filepaths.save_version=0
rig=bpy.data.objects['Bonggu.Rig'];pet=bpy.data.objects['Bonggu.Body'];scene=bpy.context.scene
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=None
for p in rig.pose.bones:
 if not p.name.startswith(('MCH.Neck.','MCH.HeadGaze')):p.matrix_basis=Matrix.Identity(4)
original_keys={k.name:np.array([v.co[:] for v in k.data]) for k in pet.data.shape_keys.key_blocks}
pet.data.calc_loop_triangles()
sourceco=[v.co.copy() for v in pet.data.vertices];sourcefaces=[list(p.vertices) for p in pet.data.loop_triangles];sourceuv=[[Vector((*pet.data.uv_layers.active.data[i].uv,0)) for i in p.loops] for p in pet.data.loop_triangles]
bvh=BVHTree.FromPolygons(sourceco,sourcefaces,all_triangles=True)
def project_uv(point):
 hit,normal,idx,d=bvh.find_nearest(point)
 tri=sourcefaces[idx];uv=sourceuv[idx]
 return barycentric_transform(hit,*[sourceco[i] for i in tri],*uv).xy
image=next(n.image for n in pet.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE')
pixels=np.array(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
def color_at(point):
 u,v=project_uv(point);ix=min(image.size[0]-1,max(0,round(u*(image.size[0]-1))));iy=min(image.size[1]-1,max(0,round(v*(image.size[1]-1))))
 rgba=pixels[iy,ix].copy();rgba[:3]=np.where(rgba[:3]<=.04045,rgba[:3]/12.92,((rgba[:3]+.055)/1.055)**2.4);return tuple(rgba)
mat=bpy.data.materials.new('Bonggu.TailPaint');mat.use_nodes=True
nt=mat.node_tree;nt.nodes.clear();color=nt.nodes.new('ShaderNodeVertexColor');color.layer_name='TailPaint';o=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(color.outputs['Color'],o.inputs['Surface']);pet.data.materials.append(mat)
bm=bmesh.new();bm.from_mesh(pet.data);dw=bm.verts.layers.deform.active;uv=bm.loops.layers.uv.active;keys=list(bm.verts.layers.shape.values())
paint=bm.loops.layers.float_color.new('TailPaint')
for face in bm.faces:
 for l in face.loops:l[paint]=(1,1,1,1)
sel={v for v in bm.verts if v.co.y>.075 and v.co.z>.195}
geom=list(sel)+[e for e in bm.edges if any(v in sel for v in e.verts)]+[f for f in bm.faces if any(v in sel for v in f.verts)]
r=bmesh.ops.bisect_plane(bm,geom=geom,plane_co=(0,0,.278),plane_no=(0,.35,1),dist=1e-7)
cut=[e for e in r['geom_cut'] if isinstance(e,bmesh.types.BMEdge)];bmesh.ops.split_edges(bm,edges=cut)
seed=max(bm.verts,key=lambda v:v.co.z if v.co.y>.07 else -1);tail={seed};stack=[seed]
while stack:
 v=stack.pop()
 for e in v.link_edges:
  w=e.other_vert(v)
  if w not in tail:tail.add(w);stack.append(w)
assert len(tail)<6000
bmesh.ops.delete(bm,geom=list(tail),context='VERTS')
ti=[pet.vertex_groups[f'Tail.{i:02}'].index for i in range(1,9)];pelvis=pet.vertex_groups['Pelvis'].index
# The back stays on the torso. The new tail attaches through an overlapping root.
for v in bm.verts:
 weights=v[dw]
 for i in ti:
  if i in weights:del weights[i]
 total=sum(weights.values())
 if total<1e-8:weights[pelvis]=1
 else:
  for i in list(weights.keys()):weights[i]/=total
boundary=[e for e in bm.edges if e.is_boundary and all(abs(v.co.z+.35*v.co.y-.278)<2e-6 for v in e.verts)]
# Fill the small back opening, with a rounded surface following the rump.
filled=bmesh.ops.holes_fill(bm,edges=boundary,sides=0)['faces']
for f in list(filled):
 ring=list(f.verts);point=sum((v.co for v in ring),Vector())/len(ring)
 center=bm.verts.new(point);center[dw][pelvis]=1
 for v in ring+[center]:
  original=v.co.z;target=.241-2.1*(v.co.y-.065)**2-3*v.co.x*v.co.x
  v.co.z=target
  for layer in keys:v[layer]=v.co
 bm.faces.remove(f)
 for a,b in zip(ring,ring[1:]+ring[:1]):
  face=bm.faces.new((a,b,center));face.material_index=2;face.smooth=True
  for l in face.loops:l[paint]=color_at(l.vert.co)
# Flatten only the former tip-to-back contact into the nearby back surface.
for v in bm.verts:
 if .085<v.co.y<.168 and v.co.z>.220:
  ceiling=.241-2.1*(v.co.y-.065)**2-3*v.co.x*v.co.x
  if v.co.z>ceiling:
   delta=ceiling-v.co.z;v.co.z+=delta
   for layer in keys:v[layer].z+=delta
# Build a smooth curled plume matching the reference silhouette. UVs are projected from the old painted tail.
points=[rig.data.bones['Tail.01'].head_local.copy()]+[rig.data.bones[f'Tail.{i:02}'].tail_local.copy() for i in range(1,9)]
rx=[.011,.014,.020,.028,.032,.030,.023,.015,.003]
rz=[.014,.020,.028,.034,.035,.032,.026,.016,.003]
rings=[];steps=40;sides=32
for step in range(steps+1):
 t=step/steps*8;k=min(7,int(t));u=t-k
 # Catmull-Rom centerline gives a smooth silhouette through the existing bones.
 p0=points[max(0,k-1)];p1=points[k];p2=points[k+1];p3=points[min(8,k+2)]
 c=.5*((2*p1)+(-p0+p2)*u+(2*p0-5*p1+4*p2-p3)*u*u+(-p0+3*p1-3*p2+p3)*u*u*u)
 tangent=(-p0+p2)+(4*p0-10*p1+8*p2-2*p3)*u+(-3*p0+9*p1-9*p2+3*p3)*u*u
 tangent.normalize();axis=Vector((1,0,0));side=(axis-tangent*axis.dot(tangent)).normalized();up=tangent.cross(side).normalized()
 width=rx[k]*(1-u)+rx[k+1]*u;depth=rz[k]*(1-u)+rz[k+1]*u
 ring=[]
 for j in range(sides):
  a=math.tau*j/sides
  fur=1+.035*math.sin(5*a+.5*t)*math.sin(math.pi*min(1,t/2))
  c2=c+side*(math.cos(a)*width*fur)+up*(math.sin(a)*depth*fur)
  v=bm.verts.new(c2)
  for layer in keys:v[layer]=c2
  q=max(0.,min(7.,t-.5));index=min(6,int(q));fraction=q-index
  if q>=7:index=6;fraction=1
  weights=np.exp(-((np.arange(8)-q)/.55)**2/2)
  if t<.8:weights[:]=0;weights[0]=1
  keep=np.argsort(weights)[-4:];weights/=weights[keep].sum()
  for n in keep:v[dw][ti[n]]=float(weights[n])
  ring.append(v)
 rings.append(ring)
for one,two in zip(rings[:-1],rings[1:]):
 for j in range(sides):
  f=bm.faces.new((one[j],one[(j+1)%sides],two[(j+1)%sides],two[j]));f.smooth=True
  f.material_index=2
  for l in f.loops:l[paint]=color_at(l.vert.co)
for ring in [rings[0],rings[-1]]:
 f=bm.faces.new(ring);f.smooth=True
 f.material_index=2
 for l in f.loops:l[paint]=color_at(l.vert.co)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3]);bm.to_mesh(pet.data);bm.free();pet.data.update()

# Exact preservation check away from the edited tail/back contact region.
protected=(original_keys['Basis'][:,1]<=.075)|(original_keys['Basis'][:,2]<=.195)
for k in pet.data.shape_keys.key_blocks:
 original=original_keys[k.name][protected]
 actual=np.array([v.co[:] for v in k.data]);mask=(actual[:,1]<=.075)|(actual[:,2]<=.195)
 def rows(x):return sorted(tuple(round(float(c),7) for c in row) for row in x)
 assert rows(actual[mask])==rows(original),k.name
for v in pet.data.vertices:
 assert len(v.groups)<=4 and abs(sum(g.weight for g in v.groups)-1)<1e-5,(v.index,[(g.group,g.weight) for g in v.groups])
for attr in list(pet.data.color_attributes):
 if attr.name!='TailPaint':pet.data.color_attributes.remove(attr)
pet.data.color_attributes.active_color=pet.data.color_attributes['TailPaint']
scene.frame_set(1);bpy.context.view_layer.update()
pet.data.calc_loop_triangles()
report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'protected_vertices_unchanged':int(protected.sum()),'triangles':len(pet.data.loop_triangles),'native_bones':len(rig.data.bones),'skin_joints':sum(b.use_deform for b in rig.data.bones),'max_influences':4,'changes':'Rebuilt the welded tail plume as a deformable curved surface, closed and smoothed the back contact, transferred source paint to linear vertex colors. Face and body outside the tail contact region are unchanged.','texture_sha256':sorted(hashlib.sha256(im.packed_file.data).hexdigest() for im in bpy.data.images if im.packed_file)}
(OUT/'tail-rig-checks.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bonggu-v2-tail-rig.blend'))
print('TAIL_RIG_READY',json.dumps(report),flush=True)
