"""Generate a crisp YVZTools logo and multi-resolution Windows icon."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
ROOT=Path(__file__).resolve().parent
S=1024
img=Image.new("RGBA",(S,S),(0,0,0,0))
d=ImageDraw.Draw(img)
pad,radius=38,210
for y in range(pad,S-pad):
    for x in range(pad,S-pad):
        cx=pad+radius if x<pad+radius else (S-pad-radius if x>=S-pad-radius else x)
        cy=pad+radius if y<pad+radius else (S-pad-radius if y>=S-pad-radius else y)
        if (x-cx)**2+(y-cy)**2>radius**2: continue
        t=max(0.0,min(1.0,(x+y*.42)/(S*1.42)))
        a,b=(8,20,54),(29,111,235)
        img.putpixel((x,y),tuple(round(a[i]*(1-t)+b[i]*t) for i in range(3))+(255,))
mask=img.getchannel("A")
glow=Image.new("RGBA",(S,S),(0,0,0,0))
ImageDraw.Draw(glow).ellipse((205,185,820,800),fill=(66,191,255,70))
img=Image.alpha_composite(img,glow.filter(ImageFilter.GaussianBlur(72)))
img.putalpha(mask)
mark=Image.new("RGBA",(S,S),(0,0,0,0))
md=ImageDraw.Draw(mark)
md.line([(300,285),(512,500),(724,285)],fill=(250,253,255,255),width=104,joint="curve")
md.line([(512,500),(512,748)],fill=(130,224,255,255),width=104)
md.line([(333,310),(512,492)],fill=(255,255,255,110),width=13)
img=Image.alpha_composite(img,mark)
ImageDraw.Draw(img).rounded_rectangle((pad,pad,S-pad,S-pad),radius=radius,outline=(142,220,255,235),width=12)
logo=img.resize((512,512),Image.Resampling.LANCZOS)
logo.save(ROOT/"yvztools_logo.png",optimize=True)
logo.save(ROOT/"yvztools.ico",format="ICO",sizes=[(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(128,128),(256,256)])
print("Generated high-resolution PNG and multi-size ICO.")
