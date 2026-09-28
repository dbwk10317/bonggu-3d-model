"""Render native playback without rebuilding the rig or actions."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
out=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(out/'bonggu-v2-everyday.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Bonggu.Rig']
target=Vector((0,.015,.15));cam=scene.camera;cam.data.ortho_scale=.52
cam.location=target+Vector((.65,-1,.33));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x=800;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.fps=30
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
for clip in json.loads((out/'clips.json').read_text())['clips']:
    name=clip['name']
    target=Vector((0,.04,.15) if name.startswith('Tail') else (0,.015,.15))
    cam.data.ortho_scale=.60 if name.startswith('Tail') else .52
    cam.location=target+Vector((1,.4,.3) if name.startswith('Tail') else (.65,-1,.33))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    for track in rig.animation_data.nla_tracks:track.mute=track.name!=name
    scene.frame_start=1;scene.frame_end=round(clip['duration_seconds']*30)+1
    folder=out/'frames'/name;folder.mkdir(parents=True,exist_ok=True)
    scene.render.filepath=str(folder/'frame-');bpy.ops.render.render(animation=True)
    print('PREVIEW',name,flush=True)
