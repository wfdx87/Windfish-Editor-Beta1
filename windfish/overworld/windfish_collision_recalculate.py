"""Rebuild ordinary collisions from drawn tiles with minimum-byte run coverage.

Maximal horizontal/vertical runs form a bipartite weighted vertex-cover problem.
A run costs three bytes, a single cell two. Minimum cut gives the exact optimum
for ordinary single/run records; overlapping runs of the same ID are harmless.
"""
from collections import deque
from windfish.rendering.windfish_overworld_render import direct_map
from windfish.overworld.windfish_collision_objects import (read_room_objects, placement_bytes, MACRO_TABLES,
                                       ALTERNATE_POINTERS)
from windfish.overworld.windfish_collision_definitions import SINGLE_ONLY, ENTRANCE_OBJECTS, PROGRESS_OBJECTS
from windfish.rom.windfish_collision_storage import enabled, replacement_changes


def minimum_records(tiles,single_only=None,encoder=None):
    """tiles maps (x,y) to ordinary object ID. Return optimal placement bytes."""
    encoder=placement_bytes if encoder is None else encoder
    single_only=SINGLE_ONLY if single_only is None else single_only
    result=[]
    for tile in sorted(set(tiles.values())):
        points={p for p,v in tiles.items() if v==tile}
        if tile in single_only:
            result.extend(encoder(x,y,tile) for x,y in sorted(points,key=lambda p:(p[1],p[0])))
            continue
        runs=[]; memberships=[{},{}]
        for axis in range(2):
            for x,y in sorted(points,key=lambda p:(p[1],p[0])):
                previous=(x-1,y) if axis==0 else (x,y-1)
                if previous in points: continue
                line=[];p=(x,y)
                while p in points:
                    line.append(p);p=(p[0]+1,p[1]) if axis==0 else (p[0],p[1]+1)
                if len(line)<2:continue
                node=len(runs)+2
                raw=encoder(x,y,tile,'Horizontal' if axis==0 else 'Vertical',len(line))
                runs.append((node,axis,raw))
                for point in line:memberships[axis][point]=node
        graph={}; candidates={}; sides={}
        def edge(a,b,c):
            graph.setdefault(a,{})[b]=graph.setdefault(a,{}).get(b,0)+c
            graph.setdefault(b,{}).setdefault(a,0)
        for node,side,raw in runs:
            candidates[node]=raw;sides[node]=side
            edge(0,node,3) if side==0 else edge(node,1,3)
        next_node=len(runs)+2
        for x,y in sorted(points,key=lambda p:(p[1],p[0])):
            left=memberships[0].get((x,y));right=memberships[1].get((x,y))
            if left is None and right is None:
                result.append(encoder(x,y,tile));continue
            if left is None or right is None:
                node=next_node;next_node+=1
                candidates[node]=encoder(x,y,tile)
                if left is None:
                    left=node;sides[node]=0;edge(0,node,2)
                else:
                    right=node;sides[node]=1;edge(node,1,2)
            edge(left,right,10000)
        # Edmonds–Karp on this tiny graph (at most 80 room cells).
        while True:
            parent={0:None};queue=deque([0])
            while queue and 1 not in parent:
                node=queue.popleft()
                for other,capacity in graph.get(node,{}).items():
                    if capacity>0 and other not in parent:
                        parent[other]=node;queue.append(other)
            if 1 not in parent:break
            amount=10000;node=1
            while parent[node] is not None:
                amount=min(amount,graph[parent[node]][node]);node=parent[node]
            node=1
            while parent[node] is not None:
                previous=parent[node];graph[previous][node]-=amount;graph[node][previous]+=amount;node=previous
        reachable={0};queue=deque([0])
        while queue:
            for other,capacity in graph.get(queue.popleft(),{}).items():
                if capacity>0 and other not in reachable:reachable.add(other);queue.append(other)
        result.extend(candidates[node] for node in sorted(candidates)
                      if (sides[node]==0 and node not in reachable) or (sides[node]==1 and node in reachable))
    return result


def tree_records(tiles):
    """Minimum cost cover using compatible base trees, strips and ordinary runs.

Tree records precede ordinary records. Candidates never paint a different tile,
so covers can overlap without changing the result. Base trees have disjoint
25/26/27/28 quadrants; their strips retain the engine's two-cell stride.
    """
    from functools import lru_cache
    anchors={(x,y) for x,y in tiles if all(tiles.get((x+dx,y+dy))==t
             for dx,dy,t in ((0,0,0x25),(1,0,0x26),(0,1,0x27),(1,1,0x28)))}
    if not anchors:return minimum_records(tiles)
    other=minimum_records({p:t for p,t in tiles.items() if t not in (0x25,0x26,0x27,0x28)})
    tiles={p:t for p,t in tiles.items() if t in (0x25,0x26,0x27,0x28)}
    points=sorted(tiles,key=lambda p:(p[1],p[0]));bits={p:1<<i for i,p in enumerate(points)}
    candidates={}
    def add(raw,cells):
        mask=sum(bits[p] for p in set(cells))
        old=candidates.get(mask)
        if old is None or len(raw)<len(old):candidates[mask]=raw
    for x,y in points:
        tile=tiles[x,y];add(placement_bytes(x,y,tile),[(x,y)])
        if tile in SINGLE_ONLY:continue
        for dx,dy,direction in ((1,0,'Horizontal'),(0,1,'Vertical')):
            cells=[(x,y)];xx,yy=x+dx,y+dy
            while tiles.get((xx,yy))==tile:
                cells.append((xx,yy));add(placement_bytes(x,y,tile,direction,len(cells)),cells)
                xx+=dx;yy+=dy
    for x,y in sorted(anchors):
        cells=[(x+dx,y+dy) for dx in range(2) for dy in range(2)]
        add(placement_bytes(x,y,0xF5),cells)
        for dx,dy,direction in ((2,0,'Horizontal'),(0,2,'Vertical')):
            line=list(cells);xx,yy=x+dx,y+dy;length=1
            while (xx,yy) in anchors:
                line.extend((xx+a,yy+b) for a in range(2) for b in range(2));length+=1
                add(placement_bytes(x,y,0xF5,direction,length),line);xx+=dx;yy+=dy
    options=list(candidates.items());full=(1<<len(points))-1
    by_bit=[[j for j,(mask,raw) in enumerate(options) if mask>>i&1] for i in range(len(points))]
    def lower(remaining):
        n=remaining.bit_count()
        if not n:return 0
        return min((n*len(raw)+(mask&remaining).bit_count()-1)//(mask&remaining).bit_count()
                   for mask,raw in options if mask&remaining)
    @lru_cache(None)
    def solve(remaining,used=0):
        if not remaining:return (0,())
        # A greedy complete cover supplies an incumbent before branching.
        rest=remaining;chosen=[];cost=0;tree_used=used
        while rest:
            mask,raw=min((item for item in options if item[0]&rest and (item[1][-1]!=0xF5 or not item[0]&tree_used)),
                         key=lambda item:len(item[1])/(item[0]&rest).bit_count())
            rest&=~mask;chosen.append(raw);cost+=len(raw)
            if raw[-1]==0xF5:tree_used|=mask
        best=(cost,tuple(chosen));bound=lower(remaining)
        if best[0]==bound:return best
        i=min((i for i in range(len(points)) if remaining>>i&1),key=lambda i:len(by_bit[i]))
        for j in sorted(by_bit[i],key=lambda j:len(options[j][1])/((options[j][0]&remaining).bit_count())):
            mask,raw=options[j];rest=remaining&~mask
            if raw[-1]==0xF5 and mask&used:continue
            if len(raw)+lower(rest)>=best[0]:continue
            cost,records=solve(rest,used|mask if raw[-1]==0xF5 else used);candidate=(cost+len(raw),(raw,)+records)
            if candidate[0]<best[0]:best=candidate
            if best[0]==bound:break
        return best
    records=list(solve(full)[1])
    # Trees first: ordinary overlaps must not alter their overlap-sensitive base.
    return sorted(records,key=lambda raw:(raw[-1]!=0xF5,raw[-2],raw))+other


def entrance_order(data,stream):
    result=[]
    for entry in stream.entries:
        if entry.kind!='object':continue
        pos,obj=entry.raw[-2:]
        if obj in ENTRANCE_OBJECTS:
            if len(entry.raw)!=2:raise ValueError('Entrance runs need manual review before recalculating.')
            result.append((pos&15,pos>>4))
        elif obj in MACRO_TABLES:
            at=0x90000+MACRO_TABLES[obj]-0x4000
            offsets=[]
            while data[at]!=255:offsets.append(data[at]);at+=1
            for i,delta in enumerate(offsets):
                if data[at+1+i] in (0xE1,0xE2,0xE3):
                    target=(pos+delta)&255;result.append((target&15,target>>4))
    return result


def recalculate_changes(data,room,alternate,capacities,allowed=None):
    alternate=bool(alternate and room in ALTERNATE_POINTERS)
    stream=read_room_objects(data,room,alternate)
    from windfish.rom import windfish_shared_map16 as shared
    graphics=shared.cells(data,room,alternate)
    from windfish.overworld.windfish_collision_objects import expanded_cells
    physical,_=expanded_cells(data,room,alternate)
    # Preserve records owning Page-1 cells exactly, including script markers,
    # macros and overlapping placements. Do not turn Page-1 behavior into objects.
    page1={i for i,t in enumerate(graphics) if t>=256}
    protected=set()
    preserved=[]
    from windfish.overworld.windfish_collision_catalog import preset_tiles
    def footprint_cells(data,obj,direction,length):
        count=1 if direction=='Single' or obj in SINGLE_ONLY else length
        stride=2 if obj==0xF5 else 1
        return [(x+(n*stride if direction=='Horizontal' else 0),
                 y+(n*stride if direction=='Vertical' else 0),tile)
                for n in range(count) for x,y,tile in preset_tiles(data,obj)]
    for index,entry in enumerate(stream.entries):
        if entry.kind!='object':continue
        pos,obj=entry.raw[-2:]
        direction=('Vertical' if entry.raw[0]&64 else 'Horizontal') if len(entry.raw)==3 else 'Single'
        length=entry.raw[0]&15 if len(entry.raw)==3 else 1
        footprint={(pos&15)+x+10*((pos>>4)+y) for x,y,t in footprint_cells(data,obj,direction,length)
                   if 0<=(pos&15)+x<10 and 0<=(pos>>4)+y<8}
        if footprint&page1:
            if obj<0xF5 and obj not in ENTRANCE_OBJECTS|PROGRESS_OBJECTS:
                # Split ordinary runs at page boundaries. Page-0 cells remain
                # eligible even when a manual run also covers Page-1 cells.
                keep=footprint&page1
                protected.update(keep)
                preserved.extend(minimum_records({(i%10,i//10):obj for i in keep}))
            else:
                # Macros/registrations cannot be split without changing native
                # behavior. Preserve their complete footprint and record.
                protected.update(footprint)
                preserved.append(entry.raw)
    tiles={}
    for i,tile in enumerate(graphics):
        if i in protected or tile>=256:continue
        if allowed is not None and tile not in allowed:continue
        if tile>=0xF5:continue
        tiles[(i%10,i//10)]=tile
    # Include protected entrances in registration ordering and warp checks.
    for i in protected:
        if physical[i] in ENTRANCE_OBJECTS:
            tiles[i%10,i//10]=physical[i]
    entrances={p:v for p,v in tiles.items() if v in ENTRANCE_OBJECTS}
    old_order=entrance_order(data,stream)
    if len(set(old_order))!=len(old_order):raise ValueError('Overlapping entrance registrations need manual review.')
    surviving=[p for p in old_order if p in entrances]
    if surviving!=old_order[:len(surviving)]:
        raise ValueError('Recalculating would shift a surviving entrance to another warp. Adjust entrances manually first.')
    order=surviving+sorted(set(entrances)-set(surviving),key=lambda p:(p[1],p[0]))
    warps=[e.raw for e in stream.entries if e.kind=='warp']
    if len(order)>min(4,len(warps)):
        raise ValueError(f'{len(order)} entrances need matching warp records; this layout has {len(warps)}.')
    ordinary={p:v for p,v in tiles.items() if p not in entrances}
    pack=tree_records if allowed is None or 0xF5 in allowed else minimum_records
    # Preserved entrance objects must stay in the native registration order.
    # Refuse a mixed order we cannot reproduce without moving warp bindings.
    preserved_order=[]
    for raw in preserved:
        if raw[-1] in ENTRANCE_OBJECTS:
            preserved_order.append((raw[-2]&15,raw[-2]>>4))
        elif raw[-1] in MACRO_TABLES:
            # entrance_order understands registration-bearing macro records.
            from dataclasses import replace
            preserved_order.extend(entrance_order(data,replace(stream,entries=(next(e for e in stream.entries if e.raw==raw),))))
    generated_order=[p for p in order if p[1]*10+p[0] not in protected]
    if preserved_order+generated_order!=order:
        raise ValueError('Recalculating would reorder a manually placed Page-1 entrance; adjust entrances manually.')
    records=preserved+pack(ordinary)+[placement_bytes(x,y,entrances[(x,y)]) for x,y in generated_order]
    payload=bytes((stream.header[0],1))+b''.join(records)+b''.join(warps)+b'\xFE'
    if enabled(data):
        changes=replacement_changes(data,room,alternate,payload)
    else:
        original=capacities.get((room,alternate))
        if original is None or original.start!=stream.start:raise ValueError('Room storage changed; reopen the ROM.')
        if stream.start+len(payload)>original.end:raise ValueError('Compressed collisions exceed verified room space. Enable expanded collision storage.')
        for key,other in capacities.items():
            if key!=(room,alternate) and stream.start<other.end and other.start<original.end:
                raise ValueError('Room storage is shared. Enable expanded collision storage first.')
        changes=[(stream.start+i,data[stream.start+i],b) for i,b in enumerate(payload) if data[stream.start+i]!=b]
    return changes, (stream.end-stream.start,len(payload),len(records))
