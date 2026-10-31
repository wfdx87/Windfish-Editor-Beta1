"""Script-owned, fixed-size RGB555 transition data and human-readable ASM export.

Generated blocks live at the end of the same allocation as their owner script.
Both directions reference one inclusive endpoint sequence. Refresh changes no
allocation sizes or pointers, so palette edits never require relinking code.
"""
MAGIC=b'CCPALFX1'
FOOTER=b'CCPALEND'
POOL=0x1DE800
POOL_END=0x1DF800

def palette(data,room):
    selected=data[0x842EF+room]
    if not 0<=selected<0x40:raise ValueError('Palette transition requires room palette IDs 00–3F.')
    if selected>=0x1F:at=0x1D2C00+(selected-0x1F)*80
    else:
        ptr=int.from_bytes(data[0x842B1+selected*2:0x842B3+selected*2],'little')
        if not 0x4000<=ptr<0x8000:raise ValueError('Invalid native room-palette pointer.')
        at=0x84000+ptr-0x4000
    raw=bytes(data[at:at+64])
    if len(raw)!=64:raise ValueError('Incomplete BG palette set.')
    return selected,raw

def frames(a,b,steps):
    """Round each 5-bit channel independently; include both exact endpoints."""
    result=[]
    for i in range(steps+1):
        out=bytearray()
        for at in range(0,64,2):
            s=int.from_bytes(a[at:at+2],'little')&0x7FFF;t=int.from_bytes(b[at:at+2],'little')&0x7FFF
            color=0
            for shift in (0,5,10):
                x=(s>>shift)&31;y=(t>>shift)&31
                v=(x*(steps-i)+y*i+steps//2)//steps
                color|=v<<shift
            out.extend(color.to_bytes(2,'little'))
        result.append(bytes(out))
    return result




def blocks(data):
    """Discover only registry-owned, terminal generated blocks; reject malformed data."""
    found=[];seen=set()
    for script in range(256):
        pointer=int.from_bytes(data[0x1DE000+script*2:0x1DE002+script*2],'little')
        size=int.from_bytes(data[0x1DE200+script*2:0x1DE202+script*2],'little')
        if not pointer or not size:continue
        start=0x1DC000+pointer-0x4000;end=start+size
        if not 0x6800<=pointer<pointer+size<=0x7800:raise ValueError('Invalid script allocation while reading palette effects.')
        if bytes(data[end-12:end-4])!=FOOTER:continue
        header=int.from_bytes(data[end-4:end-2],'little');length=int.from_bytes(data[end-2:end],'little')
        at=0x1DC000+header-0x4000
        if not start<=at<end-12 or length!=end-at or bytes(data[at:at+8])!=MAGIC or data[at+8]!=1 or not 1<=data[at+9]<=4 or int.from_bytes(data[at+10:at+12],'little')!=length:
            raise ValueError('Generated palette header/footer is damaged.')
        cursor=at+12;rows=[]
        for _ in range(data[at+9]):
            src,dst,n,period,sp,tp=data[cursor:cursor+6]
            ptr=int.from_bytes(data[cursor+6:cursor+8],'little');frame_start=cursor+28;frame_end=frame_start+(n+1)*64
            if src==dst or not 1<=n<=16 or not 1<=period<=60 or sp>=64 or tp>=64 or frame_end>end-12 or ptr!=0x4000+frame_start-0x1DC000:
                raise ValueError('Generated palette record is invalid.')
            fwd=bytes((0xA7,src,dst,sp,tp,n,period,0))+ptr.to_bytes(2,'little')
            rev=bytes((0xA7,dst,src,tp,sp,n,period,1))+ptr.to_bytes(2,'little')
            if bytes(data[cursor+8:cursor+18])!=fwd or bytes(data[cursor+18:cursor+28])!=rev:raise ValueError('Generated palette route descriptor is damaged.')
            rows.append((cursor,src,dst,n,period,frame_start));cursor=frame_end
        if cursor!=end-12:raise ValueError('Unexpected generated palette payload size.')
        if (at,end) not in seen:found.append((at,end,rows));seen.add((at,end))
    return found

def refresh(data):
    """Regenerate derived colors in place without changing script IDs or pointers."""
    records=blocks(data)
    original=data
    data=bytearray(data)
    for at,end,rows in records:
        for cursor,src,dst,n,period,frame_start in rows:
            sp,a=palette(data,src);tp,b=palette(data,dst)
            data[cursor+4:cursor+6]=bytes((sp,tp))
            data[cursor+11:cursor+13]=bytes((sp,tp))
            data[cursor+21:cursor+23]=bytes((tp,sp))
            data[frame_start:frame_start+(n+1)*64]=b''.join(frames(a,b,n))
    blocks(data)
    original[:]=data

NATIVE_SUPPORT={3027: b'\xfa\x01\xde\xea\x00!\xcd\xe3\x0b\xfa\x04\xde\xea\x00!\xc9\xfa\x02\xdeg\xfa\x03\xdeo\xe9', 9126: b'\xc9'}

def validate_native(data):
    for at,expected in NATIVE_SUPPORT.items():
        if bytes(data[at:at+len(expected)])!=expected:raise ValueError(f'Native palette dependency differs at {at:06X}.')
