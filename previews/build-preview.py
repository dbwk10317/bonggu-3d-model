"""Join existing action samples into one captioned video. Python 3 + Pillow + FFmpeg."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).resolve().parent
root = out.parent
cache = out / '.cache'
cache.mkdir(exist_ok=True)
ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
if not ffmpeg or not ffprobe:
    raise SystemExit('Install ffmpeg and ffprobe and add them to PATH.')
fonts = [os.environ.get('BONGGU_FONT', ''), '/System/Library/Fonts/AppleSDGothicNeo.ttc',
         str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/malgun.ttf')]
font_path = next((p for p in fonts if p and Path(p).is_file()), None)
if not font_path:
    raise SystemExit('Set BONGGU_FONT to a Korean TTF/OTF/TTC font.')
large = ImageFont.truetype(font_path, 25)
small = ImageFont.truetype(font_path, 15)

clips = []
for folder in ['locomotion', 'animations']:
    manifest = json.loads((root / folder / 'clips.json').read_text(encoding='utf-8'))
    clips.extend((folder, clip) for clip in manifest['clips'])

frame_start = 0
chapters = [';FFMETADATA1', 'title=Bonggu - Action samples']
segments = []
for number, (folder, clip) in enumerate(clips, 1):
    name = clip['name']
    repeats = {'Walk': 6, 'Run': 9}.get(name, 1)
    frames = round(clip['duration_seconds'] * 30) * repeats
    source = root / folder / clip['preview']
    assert source.is_file(), source
    header = Image.new('RGB', (800, 110), 'white')
    draw = ImageDraw.Draw(header)
    draw.text((24, 12), 'BONGGU  /  MOTION SAMPLES', font=small, fill='#a47754')
    draw.text((24, 39), clip['label'], font=large, fill='#392f29')
    group = '현재 리그' if folder == 'locomotion' else '이전 리그 · 참고 동작'
    draw.text((24, 78), group, font=small, fill='#847972')
    draw.text((776, 18), f'{number:02} / {len(clips):02}', font=small, fill='#847972', anchor='ra')
    draw.text((776, 78), name, font=small, fill='#847972', anchor='ra')
    draw.line((24, 107, 776, 107), fill='#eee7e0')
    card = cache / f'{number:02}.png'
    header.save(card)
    segment = cache / f'{number:02}.mp4'
    # Current clips have a 62px caption strip; legacy clips contain only the 800x720 render.
    crop = 'crop=800:720:0:62,' if folder == 'locomotion' else ''
    filters = f'[0:v]{crop}setsar=1,pad=800:830:0:110:white[pet];[pet][1:v]overlay=0:0'
    subprocess.run([ffmpeg, '-y', '-v', 'error', '-stream_loop', str(repeats - 1), '-i', str(source),
                    '-i', str(card), '-filter_complex', filters, '-frames:v', str(frames), '-r', '30',
                    '-an', '-map_metadata', '-1', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', str(segment)], check=True)
    segments.append(segment)
    chapters.extend(['[CHAPTER]', 'TIMEBASE=1/30', f'START={frame_start}',
                     f'END={frame_start + frames}', f'title={clip["label"]} ({name})'])
    frame_start += frames

listing, metadata = cache / 'concat.txt', cache / 'chapters.txt'
listing.write_text(''.join(f"file '{p.name}'\n" for p in segments), encoding='utf-8')
metadata.write_text('\n'.join(chapters) + '\n', encoding='utf-8')
video = out / 'bonggu-actions-preview.mp4'
subprocess.run([ffmpeg, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                '-i', str(metadata), '-map', '0:v:0', '-map_metadata', '1', '-map_chapters', '1',
                '-c:v', 'copy', '-movflags', '+faststart', str(video)], check=True)
report = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0',
                    '-show_streams', '-show_chapters', '-of', 'json', str(video)], text=True, encoding='utf-8'))
stream = report['streams'][0]
assert (stream['width'], stream['height'], stream['r_frame_rate']) == (800, 830, '30/1')
assert int(stream['nb_frames']) == frame_start
assert abs(float(stream['duration']) - frame_start / 30) < .001
assert len(report['chapters']) == len(clips)
print(f'{video.name}: {len(clips)} actions, {frame_start / 30:.1f}s, {video.stat().st_size / 1048576:.2f} MiB')
