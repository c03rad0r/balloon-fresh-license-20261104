from pathlib import Path
from PIL import Image,ImageDraw
O=Path(__file__).parent
out=Image.new('RGB',(1400,800),'#eeeeee');d=ImageDraw.Draw(out)
for i,label in enumerate(['baseline','candidate']):
 im=Image.open(O/(label+'-silk-crop.png')).convert('RGBA');out.paste(im,(i*700,60),im)
 d.text((i*700+20,15),label+' native F.SilkS + F.Mask | C10 reference only',fill='black')
 d.text((i*700+20,35),'Before: silk overlap' if i==0 else 'After: overlap removed; copper unchanged',fill='black')
 # Native SVG coordinate system is board mm, viewBox 6 38 8 8.
 x=i*700+(8.53-6)/8*700;y=60+((41.42 if i==0 else 41.20)-38)/8*700
 d.ellipse((x-38,y-75,x+38,y+75),outline='red',width=3)
d.text((20,775),'Diagnostic revision ONLY: 39 opens, 24 warnings remain. NOT FAB-READY.',fill='black')
out.save(O/'silk-before-after-annotated.png')
