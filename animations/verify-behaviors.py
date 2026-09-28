"""Validate clip packaging and actual playback after GLB reimport."""
import bpy,json,hashlib,struct
from pathlib import Path
import numpy as np

out=Path(__file__).resolve().parent
expected={'RigDemo':6.,'PawScrabble':4.,'SniffAround':4.8,'GentleHowl':5.}
def sha(data):return hashlib.sha256(data).hexdigest()
source=out.parent/'rigged/bonggu-v2-rigged.blend'
assert sha(source.read_bytes())==json.loads((out/'motion-checks.json').read_text())['source_sha256']
source_report=json.loads((out.parent/'rigged/validation.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(out/'bonggu-v2-behaviors.blend'))
pet=bpy.data.objects['Bonggu.Body'];rig=bpy.data.objects['Bonggu.Rig'];scene=bpy.context.scene
def ah(values):return sha(np.array(values,dtype=np.float32).tobytes())
fingerprint={'positions':ah([v.co[:] for v in pet.data.vertices]),
 'faces':sha(json.dumps([list(p.vertices) for p in pet.data.polygons]).encode()),
 'uv':ah([v.uv[:] for v in pet.data.uv_layers.active.data]),
 'material_indices':sha(bytes(p.material_index for p in pet.data.polygons)),
 'shape_keys':{k.name:ah([v.co[:] for v in k.data]) for k in pet.data.shape_keys.key_blocks},
 'textures':sorted(sha(im.packed_file.data) for im in bpy.data.images if im.packed_file)}
assert fingerprint==source_report['source_preserved'],'Appearance changed'
assert len(rig.data.bones)==85
assert {t.name for t in rig.animation_data.nla_tracks}==set(expected)
raw=(out/'bonggu-v2-behaviors.glb').read_bytes();size=struct.unpack_from('<I',raw,12)[0]
j=json.loads(raw[20:20+size]);binary=raw[28+size:]
def accessor(index):
 a=j['accessors'][index];v=j['bufferViews'][a['bufferView']]
 dtype={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]
 count={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
 return np.frombuffer(binary,dtype=dtype,count=a['count']*count,offset=v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(a['count'],count)
assert {a['name'] for a in j['animations']}==set(expected)
assert [len(s['joints']) for s in j['skins']]==[73]
assert len(j['meshes'])==1 and len(j['materials'])==2
assert all('KHR_materials_unlit' in m.get('extensions',{}) for m in j['materials'])
assert all('bufferView' in im for im in j['images'])
assert j['meshes'][0]['extras']['targetNames']==['Smile']
report={'bytes':len(raw),'source_rig_unchanged':True,'source_appearance_unchanged':True,'skin_joints':73,'clips':{}}
for animation in j['animations']:
 name=animation['name'];samples=animation['samplers']
 start=min(float(accessor(s['input']).min()) for s in samples)
 end=max(float(accessor(s['input']).max()) for s in samples)
 assert abs(start)<1e-6 and abs(end-expected[name])<1e-5,(name,start,end)
 assert all(np.isfinite(accessor(s['output'])).all() for s in samples)
 weights=[c for c in animation['channels'] if c['target']['path']=='weights'];assert len(weights)==1
 values=accessor(samples[weights[0]['sampler']]['output'])
 r=[float(values.min()),float(values.max())]
 if name in ['PawScrabble','SniffAround']:assert r==[0.,0.],r
 if name=='GentleHowl':assert .7<r[1]<.85 and r[0]==0.,r
 # Every complete clip returns to its initial pose, including the mouth.
 for s in samples:
  x=accessor(s['output']);assert np.max(np.abs(x[0]-x[-1]))<1e-4,name
 report['clips'][name]={'duration':end,'channels':len(animation['channels']),'smile_range':r,'loop_closed':True}
for obj in list(bpy.data.objects):
 if obj.type in {'MESH','ARMATURE'}:bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(out/'bonggu-v2-behaviors.glb'))
scene.render.fps=30;scene.render.resolution_x=1000;scene.render.resolution_y=900
bindings=[]
for ob in scene.objects:
 if ob.animation_data:bindings.append(ob.animation_data)
 if ob.type=='MESH' and ob.data.shape_keys and ob.data.shape_keys.animation_data:
  bindings.append(ob.data.shape_keys.animation_data)
for binding in bindings:binding.action=None
report['reimport_renders']={}
for name,frames in [('PawScrabble',[36,78]),('SniffAround',[91,94]),('GentleHowl',[76,98])]:
 for binding in bindings:
  for track in binding.nla_tracks:track.mute=track.name!=name
 for frame in frames:
  scene.frame_set(frame);bpy.context.view_layer.update()
  dest=out/f'verified-{name}-{frame:03}.png';scene.render.filepath=str(dest)
  bpy.ops.render.render(write_still=True)
  ims=[bpy.data.images.load(str(path),check_existing=False) for path in [out/f'{name}-{frame:03}.png',dest]]
  a,b=[np.array(im.pixels[:]).reshape(-1,4)[:,:3] for im in ims]
  error=float(np.abs(a-b).mean());assert error<.005,(name,frame,error)
  report['reimport_renders'][f'{name}:{frame}']=error
  for im in ims:bpy.data.images.remove(im)
manifest=json.loads((out.parent/'release/manifest.json').read_text())
for name,entry in manifest['files'].items():assert sha((out.parent/'release'/name).read_bytes())==entry['sha256']
report['approved_release_unchanged']=True
report['sha256']={name:sha((out/name).read_bytes()) for name in ['bonggu-v2-behaviors.blend','bonggu-v2-behaviors.glb']}
(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('BEHAVIORS_VALIDATED',json.dumps(report),flush=True)
