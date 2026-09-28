"""Check preserved source, skin weights and rendered GLB playback after reimport."""
import bpy, json, hashlib, struct, numpy as np
from pathlib import Path

out = Path(__file__).resolve().parent
source = out.parent/'expressions/smile/refined/bonggu-v2-smile.blend'
report = {}
def sha(data): return hashlib.sha256(data).hexdigest()
def fingerprint(pet):
    def array_hash(values): return sha(np.array(values, dtype=np.float32).tobytes())
    return {
        'positions': array_hash([v.co[:] for v in pet.data.vertices]),
        'faces': sha(json.dumps([list(p.vertices) for p in pet.data.polygons]).encode()),
        'uv': array_hash([v.uv[:] for v in pet.data.uv_layers.active.data]),
        'material_indices': sha(bytes(p.material_index for p in pet.data.polygons)),
        'shape_keys': {k.name: array_hash([v.co[:] for v in k.data]) for k in pet.data.shape_keys.key_blocks},
        'textures': sorted(sha(im.packed_file.data) for im in bpy.data.images if im.packed_file),
    }
bpy.ops.wm.open_mainfile(filepath=str(source))
original = fingerprint(next(o for o in bpy.context.scene.objects if o.type=='MESH'))
bpy.ops.wm.open_mainfile(filepath=str(out/'bonggu-v2-rigged.blend'))
pet = bpy.data.objects['Bonggu.Body']; rig = bpy.data.objects['Bonggu.Rig']; scene = bpy.context.scene
assert fingerprint(pet) == original, 'Source geometry, UV, Smile or texture changed'
report['source_preserved'] = original
report['source_sha256'] = sha(source.read_bytes())
assert report['source_sha256'] == json.loads((out/'rig-definition.json').read_text())['source_sha256']
report['bones'] = len(rig.data.bones)
report['deform_bones'] = sum(b.use_deform for b in rig.data.bones)
report['max_influences'] = max(len(v.groups) for v in pet.data.vertices)
report['max_weight_sum_error'] = max(abs(sum(g.weight for g in v.groups)-1) for v in pet.data.vertices)
assert report['max_influences'] <= 4 and report['max_weight_sum_error'] < 1e-6

# Compare edge strain against the same smile pose before skin deformation.
edges = np.array([e.vertices[:] for e in pet.data.edges])
base = np.array([v.co[:] for v in pet.data.shape_keys.key_blocks['Basis'].data])
smile = np.array([v.co[:] for v in pet.data.shape_keys.key_blocks['Smile'].data])
report['skin_edge_strain'] = {}
for frame in [1, 55, 91, 136]:
    scene.frame_set(frame); bpy.context.view_layer.update()
    before = base + pet.data.shape_keys.key_blocks['Smile'].value*(smile-base)
    after = np.array([v.co[:] for v in pet.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices])
    a = np.linalg.norm(before[edges[:,0]]-before[edges[:,1]], axis=1)
    b = np.linalg.norm(after[edges[:,0]]-after[edges[:,1]], axis=1)
    ratio = b[a>.0015]/a[a>.0015]
    report['skin_edge_strain'][str(frame)] = {'max':float(ratio.max()), 'p99':float(np.quantile(ratio,.99))}

raw = (out/'bonggu-v2-rigged.glb').read_bytes()
size, kind = struct.unpack_from('<II',raw,12)
gltf = json.loads(raw[20:20+size]); binary = raw[28+size:]
def accessor(index):
    a = gltf['accessors'][index]; v = gltf['bufferViews'][a['bufferView']]
    types = {5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}
    count = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
    return np.frombuffer(binary,dtype=types[a['componentType']],count=a['count']*count,
                         offset=v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(a['count'],count)
assert [len(s['joints']) for s in gltf['skins']] == [73]
assert len(gltf['meshes']) == 1 and len(gltf['materials']) == 2
assert all('KHR_materials_unlit' in m.get('extensions',{}) for m in gltf['materials'])
assert all('bufferView' in im for im in gltf['images'])
assert gltf['meshes'][0]['extras']['targetNames'] == ['Smile']
triangles = 0
for p in gltf['meshes'][0]['primitives']:
    assert 'JOINTS_0' in p['attributes'] and 'WEIGHTS_0' in p['attributes']
    assert 'JOINTS_1' not in p['attributes']
    assert len(p['targets']) == 1
    weights = accessor(p['attributes']['WEIGHTS_0'])
    assert np.max(np.abs(weights.sum(axis=1)-1)) < 1e-5
    triangles += gltf['accessors'][p['indices']]['count']//3
animation = gltf['animations'][0]
wc = [c for c in animation['channels'] if c['target']['path']=='weights']
assert len(wc)==1
values = accessor(animation['samplers'][wc[0]['sampler']]['output'])
assert float(values.max())>.99 and float(values.min())==0
report['glb'] = {'bytes':len(raw),'skin_joints':73,'triangles':triangles,
    'unlit_materials':2,'smile_range':[float(values.min()),float(values.max())],
    'animation_name':animation['name'],'animation_channels':len(animation['channels'])}

scene.render.resolution_x=1000;scene.render.resolution_y=900
for frame in [1,55,91,136]:
    scene.frame_set(frame)
    scene.render.filepath=str(out/f'verify-source-{frame:03}.png')
    bpy.ops.render.render(write_still=True)
for obj in list(bpy.data.objects):
    if obj.type in {'MESH','ARMATURE'}: bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(out/'bonggu-v2-rigged.glb'))
scene.render.resolution_x=1000;scene.render.resolution_y=900
report['reimport_renders'] = {}
for frame in [1,55,91,136]:
    scene.frame_set(frame);bpy.context.view_layer.update()
    dest = out/f'verify-import-{frame:03}.png'
    scene.render.filepath=str(dest);bpy.ops.render.render(write_still=True)
    images = [bpy.data.images.load(str(p),check_existing=False) for p in [out/f'verify-source-{frame:03}.png',dest]]
    pixels = [np.array(im.pixels[:]).reshape(-1,4)[:,:3] for im in images]
    error = np.abs(pixels[0]-pixels[1])
    metrics = {'mean_absolute_pixel_error':float(error.mean()),'p99':float(np.quantile(error,.99))}
    report['reimport_renders'][str(frame)] = metrics
    print('REIMPORT_FRAME',frame,metrics,flush=True)
    for im in images:bpy.data.images.remove(im)
    assert metrics['mean_absolute_pixel_error']<.005,metrics
manifest = json.loads((out.parent/'release/manifest.json').read_text())
for name, entry in manifest['files'].items():
    assert sha((out.parent/'release'/name).read_bytes()) == entry['sha256'], name
report['release_unchanged'] = True
report['release_files_checked'] = len(manifest['files'])
report['output_hashes'] = {n:sha((out/n).read_bytes()) for n in ['bonggu-v2-rigged.blend','bonggu-v2-rigged.glb']}
(out/'validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print('RIG_VALIDATED',json.dumps({k:v for k,v in report.items() if k not in ['source_preserved','release_manifest']}),flush=True)
