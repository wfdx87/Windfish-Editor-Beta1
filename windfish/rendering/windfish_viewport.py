"""Compose only intersecting room rectangles, without full-world bitmaps."""
from PIL import Image


def compose(cols,rows,box,fetch,background='#202028'):
    left,top,right,bottom=box
    image=Image.new('RGB',(max(1,right-left),max(1,bottom-top)),background)
    for y in range(max(0,top//128),min(rows,(bottom+127)//128)):
        for x in range(max(0,left//160),min(cols,(right+159)//160)):
            part=fetch(y*cols+x)
            if part is not None:image.paste(part,(x*160-left,y*128-top))
    return image
