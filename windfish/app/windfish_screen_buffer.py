"""Isolated Screen Editor buffers and conflict-checked ROM saves."""


class TabBuffer:
    """One staged tab, merged only on Save. Root ROM owns final disk writes."""
    def __init__(self,owner):
        from types import SimpleNamespace
        from windfish.rom.windfish_history import StrokeHistory
        self.root=owner;self.base=bytes(owner.data);self.data=bytearray(self.base)
        self.identity=id(owner.data);self.history=StrokeHistory();self.catalog_windows={};self.notify=lambda:None
        self.document=SimpleNamespace(path=owner.document.path,data=self.data)
    def __getattr__(self,name):return getattr(self.root,name)
    def end_stroke(self):self.history.commit()
    def show_room(self):self.notify()
    def refresh_changed_rooms(self,*args):self.notify()
    def undo(self):self.end_stroke();self.history.undo(self.data);self.notify()
    def redo(self):self.end_stroke();self.history.redo(self.data);self.notify()
    def save(self):
        if id(self.root.data)!=self.identity:raise ValueError('The ROM changed; reopen Screen Editor before saving this tab.')
        self.end_stroke();edits=[]
        for at,(old,new) in enumerate(zip(self.base,self.data)):
            if old==new:continue
            if self.root.data[at] not in (old,new):raise ValueError(f'Another editor changed shared data at {at:06X}. Reopen this tab before saving.')
            if self.root.data[at]!=new:edits.append((at,self.root.data[at],new))
        self.root.end_stroke()
        for at,old,new in edits:self.root.history.record(at,old,new,self.root.room,False);self.root.data[at]=new
        self.root.history.commit()
        self.root.document.data[0x1D2BFC]=self.root.room
        self.root.document.save()
        self.root.refresh_title()
        self.base=bytes(self.data)
        self.root.show_room()


