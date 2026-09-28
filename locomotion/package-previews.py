"""Encode rendered clips, caption cards and review sequences. Run with Python 3."""
import json,subprocess,os,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

out=Path(__file__).resolve().parent
manifest=json.loads((out/'clips.json').read_text())
ff=shutil.which('ffmpeg');probe=shutil.which('ffprobe')
if not ff or not probe:
    raise SystemExit('Install ffmpeg and ffprobe and add them to PATH.')
def run(args):subprocess.run([ff,'-y','-v','error',*args],check=True)
font_paths=[os.environ.get('BONGGU_FONT',''),'/System/Library/Fonts/AppleSDGothicNeo.ttc',str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/malgun.ttf')]
font_path=next((p for p in font_paths if p and Path(p).is_file()),None)
if not font_path:
    raise SystemExit('Set BONGGU_FONT to a Korean font file (TTF/OTF/TTC).')
font=ImageFont.truetype(font_path,23,index=0)
small=ImageFont.truetype(font_path,15,index=0)
cards=out/'frames'/'captions';cards.mkdir(parents=True,exist_ok=True)
report={}
for clip in manifest['clips']:
    name=clip['name'];count=round(clip['duration_seconds']*30)
    frames=out/'frames'/name
    assert len(list(frames.glob('frame-*.png')))>=count+1,name
    card=Image.new('RGBA',(800,62),(255,255,255,255));draw=ImageDraw.Draw(card)
    draw.text((23,10),clip['label'],font=font,fill=(57,47,41,255))
    draw.text((780,17),name,font=small,fill=(132,121,114,255),anchor='ra')
    card_path=cards/(name+'.png');card.save(card_path)
    dest=out/(name+'.mp4')
    run(['-framerate','30','-i',str(frames/'frame-%04d.png'),'-i',str(card_path),'-filter_complex','[0:v]pad=iw:ih+62:0:62:white[canvas];[canvas][1:v]overlay=0:0',
         '-frames:v',str(count),'-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)])
    clip['preview']=dest.name
    data=json.loads(subprocess.check_output([probe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,duration','-of','json',str(dest)]))['streams'][0]
    assert int(data['nb_frames'])==count and data['width']==800 and data['height']==782,(name,data)
    report[dest.name]=data

def sequence(name,clips):
    listing=out/'frames'/(name+'.txt')
    listing.write_text(''.join("file '../"+c+".mp4'\n" for c in clips),encoding='utf-8')
    dest=out/(name+'.mp4')
    run(['-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(dest)])
    return dest.name

manifest['neck_preview']=sequence('neck-movements',['LookAround','GroundSniff','LookUp'])
manifest['preview']=sequence('everyday-preview',['Idle']+['Walk']*3+['Run']*6+['SitDown','SitIdle','SitUp','LieDown','LieIdle','LieUp','PlayBow','LookAround','GroundSniff','LookUp'])
manifest['sit_preview']=sequence('sit-sequence',['SitDown','SitIdle','SitUp'])
manifest['lie_preview']=sequence('lie-sequence',['LieDown','LieIdle','LieUp'])
manifest['tail_preview']=sequence('tail-movements',['TailWagSoft','TailWagHappy','TailLower','TailLowIdle','TailRaise'])
(out/'clips.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(out/'preview-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('PREVIEWS_PACKAGED')
