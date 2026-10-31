"""Bounded, content-aware map rendering caches. No ROM mutation or hooks."""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
from PIL import Image


def compose_room(sheet,cells):
    image=Image.new('RGB',(160,128))
    for i,tile in enumerate(cells):
        image.paste(sheet.crop((tile%16*16,tile//16*16,tile%16*16+16,tile//16*16+16)),(i%10*16,i//10*16))
    return image


def remember(cache,key,value,limit):
    cache[key]=value;cache.move_to_end(key)
    while len(cache)>limit:cache.popitem(last=False)
    return value


@dataclass
class Entry:
    revision: bytes
    signature: tuple
    result: tuple


class OverworldRenderCache:
    def __init__(self):
        self.data=None;self.entries=OrderedDict();self.sheets=OrderedDict()
        self.entry_limit=48

    def reserve_visible(self,room_count):
        """Keep a viewport working set plus a small panning margin.

        At 1x a maximized window can show more than 48 rooms. A smaller LRU
        repeatedly evicts rooms needed later in the same redraw, even when
        nothing changed. Native-resolution entries remain bounded to one world.
        """
        self.entry_limit=max(48,min(256,int(room_count)+16))
        while len(self.entries)>self.entry_limit:self.entries.popitem(last=False)

    def advance_map_revision(self,data,before,after,affected):
        """Only a known map-placement transaction may bypass sheet validation.

        Retag unchanged rooms that were current before the edit. Changed rooms
        retain their old signature, so get() recomposes them from the same sheet.
        Already-stale entries remain stale and still take the validation path.
        """
        if self.data is not data:return
        for key,entry in self.entries.items():
            if key not in affected and entry.revision==before:entry.revision=after

    def get(self,data,revision,room,special=False):
        import windfish.rendering.windfish_overworld_render as r
        from windfish.rom.windfish_room_tiles import definition_offset,is_custom
        if data is not self.data:self.data=data;self.entries.clear();self.sheets.clear()
        special=bool(special and room in r.SPECIAL_MAP);key=(room,special);old=self.entries.get(key)
        if old is not None and old.revision==revision:self.entries.move_to_end(key);return old.result
        palid,palat,colors=r.palette(data,room);sog,anim,gfx=r.graphics(data,room,special);attrat,attrs=r.attributes(data,room)
        custom=is_custom(data,room);at=definition_offset(data,room)
        from windfish.rom.windfish_vram_bank1 import background_data
        sheet_key=(background_data(data,room),tuple(colors),bytes(gfx),bytes(attrs),bytes(data[at:at+1024]),custom,bytes(data[0xB0800:0xB1000]) if custom else b'')
        from windfish.rom import windfish_shared_map16 as shared
        if shared.enabled(data):
            from windfish.rom.windfish_room_map16 import offsets
            page_at,page_attr=offsets(data,room)
            sheet_key+=(bytes(data[page_at:page_at+1024]),bytes(data[page_attr:page_attr+1024]),bytes(data[0xB0800:0xB1000]))
        mapat,_=r.direct_map(data,room,special);cells=shared.cells(data,room,special);signature=(sheet_key,tuple(cells))
        info={'palette_id':palid,'palette_offset':palat,'sog':sog,'animation':anim,'attributes_offset':attrat,'map_offset':mapat}
        if old is not None and old.signature==signature:image,sheet,_=old.result
        else:
            sheet=old.result[1] if old is not None and old.signature[0]==sheet_key else self.sheets.get(sheet_key)
            if sheet is None:image,sheet,_=r.render(data,room,special=special,scale=1)
            else:image=compose_room(sheet,cells)
            remember(self.sheets,sheet_key,sheet,16)
        result=(image,sheet,info);remember(self.entries,key,Entry(revision,signature,result),self.entry_limit)
        return result


class DungeonRenderCache:
    def __init__(self):self.data=None;self.entries=OrderedDict();self.sheets=OrderedDict()
    def get(self,data,revision,context,room,sideview,templates,doors,inherited=0):
        import windfish.rendering.windfish_dungeon_render as r
        import windfish.dungeon.windfish_dungeon_visuals as v
        if data is not self.data:self.data=data;self.entries.clear();self.sheets.clear()
        key=(context,room,inherited,sideview);old=self.entries.get(key)
        if old is not None and old.revision==revision:self.entries.move_to_end(key);return old.result
        record=r.read_room(data,context,room);cells=r.layout(data,record,templates,doors);cells=v.apply_to_cells(data,context,room,cells)
        raw,selector,warnings=r.graphics(data,record,sideview,inherited)
        mapping=r.chunk(data,r.COLOR_FORMATION if context==255 else r.FORMATION,1024)
        sheet_key=(bytes(raw),bytes(r.attributes(data,context,room)),mapping,r.palette(data,context,sideview,room))
        signature=(sheet_key,bytes(cells))
        if old is not None and old.signature==signature:image=old.result[0]
        else:
            sheet=self.sheets.get(sheet_key)
            if sheet is None:sheet,_=r.tile_sheet(data,context,room,sideview,inherited)
            remember(self.sheets,sheet_key,sheet,16);image=compose_room(sheet,cells)
        result=(image,record,warnings);remember(self.entries,key,Entry(revision,signature,result),48)
        return result


class OverworldRenderCacheMixin:
    def _visual_revision(self):
        if getattr(self,'_visual_cache',None) is None:self._visual_cache=OverworldRenderCache()
        revision=hashlib.sha256(self.data).digest()
        if self._visual_cache.data is not None and self._visual_cache.data is not self.data:
            self.atlas_default=None;self.atlas_alt=None;self._tile_sheets.clear();self._room_image_cache.clear()
            self._atlas_parts_default={};self._atlas_parts_alt={};self._atlas_revision_default=None;self._atlas_revision_alt=None
        return revision
    def cached_room_render(self,room,special=False,scale=1,*,revision=None):
        if not isinstance(scale,int) or scale<1:raise ValueError('Invalid room scale.')
        image,sheet,info=self._visual_cache_result(room,special,revision)
        if scale!=1:image=image.resize((160*scale,128*scale),Image.Resampling.NEAREST)
        return image,sheet,info
    def _visual_cache_result(self,room,special=False,revision=None):
        # A synchronous viewport redraw supplies one content revision for all
        # its rooms. Individual callers still verify current bytes themselves.
        if revision is None:revision=self._visual_revision()
        return self._visual_cache.get(self.data,revision,room,special)
    def refresh_visual_cache(self):
        if self.data is None:return
        revision=self._visual_revision()
        if revision==getattr(self,'_local_render_revision',None):return
        # Stale UI images are regenerated only if requested by the viewport.
        self._tile_sheets.clear();self._room_image_cache.clear()
        self._local_render_signatures={};self._local_render_revision=revision
