"""Validate portable animation semantics and rendered GLB playback."""
import bpy,struct,json,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
out=Path(__file__).resolve().parent
manifest=json.loads((out/'clips.json').read_text(encoding='utf-8'));expected={c['name']:c for c in manifest['clips']}
state_loop={'stand':'Idle','walk':'Walk','run':'Run','sit':'SitIdle','lie':'LieIdle','tail-low':'TailLowIdle','sleep':'SleepIdle','held':'Dangle'}
def sha(x):return hashlib.sha256(x).hexdigest()
def ah(x):return sha(np.array(x,dtype=np.float32).tobytes())
def fingerprint():
    pet=bpy.data.objects['Bonggu.Body']
    return {'positions':ah([v.co[:] for v in pet.data.vertices]),'faces':sha(json.dumps([list(p.vertices) for p in pet.data.polygons]).encode()),'uv':ah([v.uv[:] for v in pet.data.uv_layers.active.data]),'material_indices':sha(bytes(p.material_index for p in pet.data.polygons)),
     'shape_keys':{k.name:ah([v.co[:] for v in k.data]) for k in pet.data.shape_keys.key_blocks},'textures':sorted(sha(im.packed_file.data) for im in bpy.data.images if im.packed_file),
     'tail_paint':ah([c.color[:] for c in pet.data.color_attributes['TailPaint'].data])}
bpy.ops.wm.open_mainfile(filepath=str(out/'bonggu-v2-tail-rig.blend'))
source_fingerprint=fingerprint()
bpy.ops.wm.open_mainfile(filepath=str(out/'bonggu-v2-everyday.blend'))
pet=bpy.data.objects['Bonggu.Body'];rig=bpy.data.objects['Bonggu.Rig'];scene=bpy.context.scene
everyday=fingerprint()
# Geometry, UV, Smile and paint are unchanged; only the body texture is swapped for the approved 2K copy.
assert {k:v for k,v in everyday.items() if k!='textures'}=={k:v for k,v in source_fingerprint.items() if k!='textures'}
release=out.parent/'release';m=json.loads((release/'manifest.json').read_text())
texture_2k=m['files']['bonggu-color-2k.png']['sha256'];texture_4k=m['files']['bonggu-color-4k.png']['sha256']
assert everyday['textures']==sorted([t for t in source_fingerprint['textures'] if t!=texture_4k]+[texture_2k])
tail_checks=json.loads((out/'tail-rig-checks.json').read_text())
assert tail_checks['protected_vertices_unchanged']>=17668
assert tail_checks['hip_weight_smoothing']['appearance_unchanged'] and pet['hip_weight_smoothing']==tail_checks['hip_weight_smoothing']['iterations']
assert tail_checks['texture_sha256']==source_fingerprint['textures']
assert len(rig.data.bones)==112
assert {t.name for t in rig.animation_data.nla_tracks}==set(expected)
assert [a.name for a in bpy.data.actions if a.name not in expected]==[]
checks=json.loads((out/'motion-checks.json').read_text())
assert checks['source_sha256']==sha((out/'bonggu-v2-tail-rig.blend').read_bytes())
assert checks['clips']['SitIdle']['rump_min_z']<.004 and checks['clips']['LieIdle']['ventral_min_z']<.004
raw=(out/'bonggu-v2-everyday.glb').read_bytes();length=struct.unpack_from('<I',raw,12)[0]
j=json.loads(raw[20:20+length]);binary=raw[28+length:]
def accessor(i):
    a=j['accessors'][i];v=j['bufferViews'][a['bufferView']]
    dtype={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]
    columns={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
    return np.frombuffer(binary,dtype=dtype,count=a['count']*columns,offset=v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(a['count'],columns)
assert {a['name'] for a in j['animations']}==set(expected)
assert len(j['meshes'])==1 and len(j['materials'])==3
assert [len(s['joints']) for s in j['skins']]==[78]
assert all('KHR_materials_unlit' in m.get('extensions',{}) for m in j['materials'])
assert all('bufferView' in im for im in j['images'])
def image_size(im):
    v=j['bufferViews'][im['bufferView']];return struct.unpack('>II',binary[v.get('byteOffset',0)+16:v.get('byteOffset',0)+24])
assert max(max(image_size(im)) for im in j['images'])<=2048,[image_size(im) for im in j['images']]
triangles=sum(j['accessors'][p['indices']]['count']//3 for p in j['meshes'][0]['primitives']);assert triangles==tail_checks['triangles']
assert any('COLOR_0' in p['attributes'] for p in j['meshes'][0]['primitives'])
# At most four bone influences per vertex, and the face morphs belong to the app, not the clips.
assert all('JOINTS_1' not in p['attributes'] for p in j['meshes'][0]['primitives'])
assert j['meshes'][0]['extras']['targetNames']==['Smile','Yawn','EyesClosed']
assert all(set(c.get('morphs',{}))<={'Yawn','EyesClosed'} for c in manifest['clips'])
assert not any(c['target']['path']=='weights' for a in j['animations'] for c in a['channels'])
report={'prepared_rig_appearance_preserved':True,'tail_topology_updated':True,'protected_vertices_unchanged':tail_checks['protected_vertices_unchanged'],'native_bones':112,'skin_joints':78,'triangles':triangles,
    'max_texture_size':max(max(image_size(im)) for im in j['images']),'morph_targets':j['meshes'][0]['extras']['targetNames'],'morph_animation':False,'bytes':len(raw),'clips':{}}
ends={}
for animation in j['animations']:
    name=animation['name'];spec=expected[name];samples=animation['samplers']
    start=min(float(accessor(s['input']).min()) for s in samples);end=max(float(accessor(s['input']).max()) for s in samples)
    assert abs(start)<1e-6 and abs(end-spec['duration_seconds'])<1e-5,(name,start,end)
    assert all(np.isfinite(accessor(s['output'])).all() for s in samples)
    ends[name]={}
    for c in animation['channels']:
        key=(c['target']['node'],c['target']['path']);values=accessor(samples[c['sampler']]['output']);ends[name][key]=(values[0],values[-1])
        if spec['loop']:
            error=np.max(np.abs(values[0]-values[-1]))
            if key[1]=='rotation':error=min(error,np.max(np.abs(values[0]+values[-1])))
            assert error<1e-4,(name,key,error)
    report['clips'][name]={'duration':round(end,5),'channels':len(animation['channels']),'loop':spec['loop'],'smile':spec['smile']}
# Each clip starts on its entry loop's first frame and ends on its exit loop's first frame.
for name,spec in expected.items():
    for state,side in [(spec['entry_state'],0),(spec['exit_state'],1)]:
        loop=state_loop[state]
        for key in ends[name]:
            x,y=ends[name][key][side],ends[loop][key][0];error=np.max(np.abs(x-y))
            if key[1]=='rotation':error=min(error,np.max(np.abs(x+y)))
            assert error<1e-4,(name,loop,key,error)
report['transition_endpoints_match']=True
# Compare native and reimported images at a quarter, half and three quarters of each clip.
def aim_camera(name):
    # Held up, Bonggu is about twice as tall as standing.
    held=expected[name]['entry_state']=='held';target=Vector((0,.015,.30 if held else .15));cam=scene.camera;cam.data.ortho_scale=.72 if held else .52
    cam.location=target+Vector((.65,-1,.33));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x=800;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.fps=30
samples={name:sorted({round(c['duration_seconds']*30*q)+1 for q in (.25,.5,.75)}) for name,c in expected.items()}
native={}
for name,frames in samples.items():
    for track in rig.animation_data.nla_tracks:track.mute=track.name!=name
    aim_camera(name)
    for frame in frames:
        scene.frame_set(frame);scene.render.filepath=str(out/f'check-{name}-{frame:03}.png');bpy.ops.render.render(write_still=True)
        image=bpy.data.images.load(scene.render.filepath,check_existing=False);native[name,frame]=np.array(image.pixels[:]);bpy.data.images.remove(image)
for ob in list(bpy.data.objects):
    if ob.type in {'MESH','ARMATURE'}:bpy.data.objects.remove(ob,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(out/'bonggu-v2-everyday.glb'))
bindings=[ob.animation_data for ob in scene.objects if ob.animation_data]
for binding in bindings:binding.action=None
face_keys=[ob.data.shape_keys.key_blocks for ob in scene.objects if ob.type=='MESH' and ob.data.shape_keys]
errors=[]
for name,frames in samples.items():
    for binding in bindings:
        for track in binding.nla_tracks:track.mute=track.name!=name
    # The app applies clips.json smile and morph curves; do the same for the reimported mesh.
    for keys in face_keys:keys['Smile'].value=expected[name]['smile']
    aim_camera(name)
    for frame in frames:
        for keys in face_keys:
            for k in ['Yawn','EyesClosed']:
                curve=np.array(expected[name].get('morphs',{}).get(k,[[0,0]]));keys[k].value=float(np.interp((frame-1)/30,curve[:,0],curve[:,1]))
        scene.frame_set(frame);scene.render.filepath=str(out/f'verified-{name}-{frame:03}.png');bpy.ops.render.render(write_still=True)
        image=bpy.data.images.load(scene.render.filepath,check_existing=False);actual=np.array(image.pixels[:]);bpy.data.images.remove(image)
        error=float(np.abs(native[name,frame]-actual).mean());assert error<.005,(name,frame,error)
        errors.append(error)
# Rounded so a rerun on another machine does not rewrite this file.
report['reimport_render_checks']=len(errors);report['reimport_render_max_error']=round(max(errors),4)
for name,entry in m['files'].items():assert sha((release/name).read_bytes())==entry['sha256']
report['approved_release_unchanged']=True
report['sha256']={name:sha((out/name).read_bytes()) for name in ['bonggu-v2-everyday.blend','bonggu-v2-everyday.glb']}
(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('ALL_VALIDATED',json.dumps(report),flush=True)
