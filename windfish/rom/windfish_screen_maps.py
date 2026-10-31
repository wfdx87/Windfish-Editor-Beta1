"""Bounded edits to existing encoded screen maps; never overwrite neighbors."""
from windfish.rom.windfish_world_map import decode_frame

SPECS={
 'title':(0x2310A,0x93BF0,0x87DEE),
 'file':(0x22336,0x91F80,0x875B6),
 'save':(0x22A6D,0x92262,0x875B6),
 'copy':(0x22660,0x9217D,0x875B6),
 'erase':(0x22589,0x92115,0x875B6),
}


def stream_length(data,start):
    at=start
    while at<len(data):
        if data[at]==0:return at-start+1
        flags=data[at+2];at+=3+(1 if flags&64 else (flags&63)+1)
        if at-start>4096:break
    raise ValueError('Invalid screen command stream.')


# Separate from world-map border records at 23C00 and 93D00. Both use the
# original loader banks, so relocation needs pointer edits, no engine hooks.
RESERVED={('save',0):(0x80545,0x23D00),('file',1):(0x91C51,0x93E00)}
MAGIC=b'WFSCREEN01'


def location(data,kind,component):
    original=SPECS[kind][component]
    if (kind,component) not in RESERVED:return original
    pointer,reserved=RESERVED[(kind,component)]
    value=int.from_bytes(data[pointer:pointer+2],'little')
    at=(original//0x4000)*0x4000+value-0x4000
    if at==original:return original
    if at==reserved and bytes(data[reserved+496:reserved+506])==MAGIC:return at
    raise ValueError('Unsupported custom screen pointer.')


def cells(data,kind):
    tilemap,attrmap=(location(data,kind,c) for c in range(2))
    base=[(0xAE+((x^y)&1)) if kind=='save' else 0x7E for y in range(32) for x in range(32)]
    ids=decode_frame(data,tilemap,0x7E)
    # Save initializes a checkerboard before applying its partial commands.
    if kind=='save':
        written=command_positions(data,tilemap)
        ids=[ids[i] if i in written else base[i] for i in range(1024)]
    attrs=decode_frame(data,attrmap,5 if kind=='save' else 0)
    return tuple((ids[y*32+x],attrs[y*32+x]) for y in range(18) for x in range(20))


def command_positions(data,start):
    positions=set();at=start
    while data[at]:
        address=(data[at]<<8)|data[at+1];flags=data[at+2];count=(flags&63)+1;step=32 if flags&128 else 1
        positions.update(address-0x9800+i*step for i in range(count))
        at+=3+(1 if flags&64 else count)
    return positions


def _encode_axis(grid,default,vertical=False):
    """Shortest literal/repeat spans on each row or column, via dynamic programming."""
    lines,length=(20,18) if vertical else (18,20)
    mode=128 if vertical else 0;out=bytearray()
    for line in range(lines):
        indices=[i*20+line if vertical else line*20+i for i in range(length)]
        values=[grid[i] for i in indices];base=[default[i] for i in indices]
        dp=[None]*(length+1);dp[length]=b''
        for start in range(length-1,-1,-1):
            choices=[dp[start+1]] if values[start]==base[start] else []
            pos=indices[start];address=0x9800+pos//20*32+pos%20
            header=bytes((address>>8,address&255))
            for end in range(start+1,length+1):
                chunk=bytes(values[start:end])
                choices.append(header+bytes((mode+len(chunk)-1,))+chunk+dp[end])
                if len(set(chunk))==1:
                    choices.append(header+bytes((mode+64+len(chunk)-1,chunk[0]))+dp[end])
            dp[start]=min(choices,key=len)
        out.extend(dp[0])
    return bytes(out)+b'\0'


def encode(grid,default):return _encode_axis(grid,default)


def encode_columns(grid,default):return _encode_axis(grid,default,True)


def encode_runs(grid,default):
    """Pull out repeated horizontal/vertical strips before literal row packing."""
    remaining={i for i,(a,b) in enumerate(zip(grid,default)) if a!=b};out=bytearray();base=list(default)
    while remaining:
        best=None
        for i in sorted(remaining):
            x,y=i%20,i//20
            for step,limit,vertical in ((1,20-x,False),(20,18-y,True)):
                n=1
                while n<limit and grid[i+n*step]==grid[i]:n+=1
                count=sum(i+j*step in remaining for j in range(n))
                if count>=3 and (best is None or count>best[0]):best=(count,i,step,n,vertical)
        if best is None:break
        _,i,step,n,vertical=best;address=0x9800+i//20*32+i%20
        out.extend((address>>8,address&255,64|(128 if vertical else 0)|(n-1),grid[i]))
        for j in range(n):base[i+j*step]=grid[i];remaining.discard(i+j*step)
    return bytes(out)+min((encode(grid,base),encode_columns(grid,base)),key=len)


def encode_borders(grid,default):
    # Alternating decorative side borders compress well as two literal
    # columns, while labels and content compress better horizontally.
    base=list(default);out=bytearray()
    for x in (0,19):
        if all(grid[y*20+x]==base[y*20+x] for y in range(18)):continue
        address=0x9800+x;out.extend((address>>8,address&255,128+17))
        for y in range(18):out.append(grid[y*20+x]);base[y*20+x]=grid[y*20+x]
    return bytes(out)+min((encode(grid,base),encode_columns(grid,base),encode_runs(grid,base)),key=len)


def stamp_changes(data,kind,x,y,stamp):
    w,h,values,full=stamp
    before=cells(data,kind);after=list(before)
    for sy in range(min(h,18-y)):
        for sx in range(min(w,20-x)):
            at=(y+sy)*20+x+sx;tile,attr=values[sy*w+sx]
            after[at]=(tile,before[at][1] if kind=='save' else attr if full else (before[at][1]&0xF8)|(attr&7))
    result=[]
    for component in range(2):
        start=location(data,kind,component)
        written=command_positions(data,start)
        title_missing=kind=='title' and any(y*32+x not in written for y in range(18) for x in range(20))
        if all(a[component]==b[component] for a,b in zip(before,after)) and not title_missing:continue
        default=[(0xAE+((i%20^i//20)&1)) if kind=='save' else 0x7E for i in range(360)] if component==0 else [5 if kind=='save' else 0]*360
        # Explicit initialization is semantic, even when a cell equals the
        # preview default. Skipping those writes leaves intro/previous-screen
        # VRAM behind in game. Preserve every previously written destination.
        for pos in command_positions(data,start):
            cy,cx=divmod(pos,32)
            if cy<18 and cx<20:default[cy*20+cx]=-1
        if kind=='title':default=[-1]*360
        grid=[v[component] for v in after]
        raw=min((encode(grid,default),encode_columns(grid,default),encode_runs(grid,default),encode_borders(grid,default)),key=len)
        capacity=stream_length(data,start)
        original=CAPACITIES[(kind,component)]
        relocated=(kind,component) in RESERVED and start==RESERVED[(kind,component)][1]
        if not relocated and capacity>original:raise ValueError('Unsupported expanded screen layout.')
        limit=496 if relocated else original
        if len(raw)>limit and (kind,component) in RESERVED:
            pointer,reserved=RESERVED[(kind,component)]
            occupied=bytes(data[reserved:reserved+512])
            if len(occupied)!=512 or any(value not in (0,255) for value in occupied):
                raise ValueError('Reserved screen space is occupied by another modification.')
            start=reserved;limit=496;relocated=True
            word=0x4000+reserved%0x4000
            result.extend((pointer+i,data[pointer+i],value) for i,value in enumerate(word.to_bytes(2,'little')) if data[pointer+i]!=value)
        if len(raw)>limit:raise ValueError(f'This layout needs {len(raw)} bytes; its block holds {limit}. Try a smaller/repeated stamp.')
        raw=raw.ljust(limit,b'\0')
        if relocated:raw+=MAGIC+bytes(6)
        result.extend((start+i,data[start+i],value) for i,value in enumerate(raw) if data[start+i]!=value)
    return result

# Exact source stream allocations, validated against native and VWF fixtures.
CAPACITIES={('title', 0): 377, ('title', 1): 225, ('file', 0): 279, ('file', 1): 197, ('save', 0): 129, ('save', 1): 65, ('copy', 0):232, ('copy',1):104, ('erase',0):215, ('erase',1):104}
