import base64,json,math,os,re,subprocess,sys,io,concurrent.futures as cf
from PIL import Image,ImageDraw
import os; T=os.environ.get('UC_WORK', 'work') + '/'  # holds rend/ from render_prototype.py and bbox_gt.json
MODEL=sys.argv[1]; COND=sys.argv[2]
gt=json.load(open(T+'bbox_gt.json'))
def b64(im):
    b=io.BytesIO(); im.save(b,'PNG'); return base64.b64encode(b.getvalue()).decode()
def call(im,text):
    c=[{"type":"image","source":{"type":"base64","media_type":"image/png","data":b64(im)}},{"type":"text","text":text}]
    env={k:v for k,v in os.environ.items() if k!='ANTHROPIC_API_KEY'}
    for _ in range(3):
        r=subprocess.run(['claude','-p','--model',MODEL,'--input-format','stream-json','--output-format','stream-json','--verbose','--setting-sources','','--no-session-persistence','--tools',''],input=json.dumps({"type":"user","message":{"role":"user","content":c}})+'\n',capture_output=True,text=True,timeout=200,env=env,cwd='/tmp')
        for l in r.stdout.splitlines():
            if l.startswith('{') and '"type":"result"' in l.replace(' ',''):
                o=json.loads(l); m=re.findall(r'\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]',o.get('result') or '')
                if m: return [float(x) for x in m[-1]],o.get('total_cost_usd',0)
    return None,0
def rulers(im,step=100):
    im=im.copy().convert('RGB');d=ImageDraw.Draw(im,'RGBA')
    for x in range(step,im.width,step):
        d.line([(x,0),(x,im.height)],fill=(255,0,90,70),width=1); d.text((x+2,1),str(x),fill=(200,0,70,255))
    for y in range(step,im.height,step):
        d.line([(0,y),(im.width,y)],fill=(255,0,90,70),width=1); d.text((1,y+1),str(y),fill=(200,0,70,255))
    return im
def iou(a,b):
    ix=max(0,min(a[2],b[2])-max(a[0],b[0]));iy=max(0,min(a[3],b[3])-max(a[1],b[1]));i=ix*iy
    u=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i
    return i/u if u>0 else 0
ASK='This image is {w}x{h} pixels. Return the tight bounding box of the UI element containing the text "{t}" (a {tag}), as [x1, y1, x2, y2] in absolute pixel coordinates of this image, origin top-left. Reply with only that array.'
def one(g):
    im=Image.open(T+f"rend/{g['shot']}.png").convert('RGB')
    cost=0
    view=rulers(im) if 'rulers' in COND else im
    extra=' Red ruler lines with labels mark every 100 pixels; use them to read coordinates. Ignore them otherwise.' if 'rulers' in COND else ''
    b,c=call(view,ASK.format(w=im.width,h=im.height,t=g['text'],tag=g['tag'])+extra); cost+=c
    if not b: return dict(g,pred=None,iou=0,cost=cost)
    if 'refine' in COND:
        # crop around the first guess with generous margin, ask again on an upscaled crop
        m=120
        x1,y1,x2,y2=max(0,b[0]-m),max(0,b[1]-m),min(im.width,b[2]+m),min(im.height,b[3]+m)
        if x2>x1 and y2>y1:
            cr=im.crop((int(x1),int(y1),int(x2),int(y2)));sc=2
            cr2=cr.resize((cr.width*sc,cr.height*sc),Image.LANCZOS)
            v=rulers(cr2) if 'rulers' in COND else cr2
            b2,c=call(v,ASK.format(w=cr2.width,h=cr2.height,t=g['text'],tag=g['tag'])+extra);cost+=c
            if b2: b=[int(x1)+b2[0]/sc,int(y1)+b2[1]/sc,int(x1)+b2[2]/sc,int(y1)+b2[3]/sc]
    return dict(g,pred=b,iou=iou(b,g['box']),cost=cost)
with cf.ThreadPoolExecutor(3) as ex: res=list(ex.map(one,gt))
s=sorted(r['iou'] for r in res)
hit=lambda t:sum(r['iou']>=t for r in res)/len(res)
cen=sum(1 for r in res if r['pred'] and r['box'][0]<=(r['pred'][0]+r['pred'][2])/2<=r['box'][2] and r['box'][1]<=(r['pred'][1]+r['pred'][3])/2<=r['box'][3])/len(res)
print(f"{COND} {MODEL} n={len(res)} meanIoU={sum(s)/len(s):.3f} medianIoU={s[len(s)//2]:.3f} IoU>=.5={hit(.5):.2f} IoU>=.75={hit(.75):.2f} center_inside={cen:.2f} cost=${sum(r['cost'] for r in res):.2f}")
json.dump(res,open(T+f'bbox_{COND}_{MODEL}.json','w'))
