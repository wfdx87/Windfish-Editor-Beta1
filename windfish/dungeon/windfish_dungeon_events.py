"""Native indoor room event table and immediate Room Properties controls."""
import tkinter as tk
from tkinter import ttk
import windfish.rendering.windfish_dungeon_render as dungeon

TRIGGERS={0:'None (disable event)',1:'Defeat counted enemies',2:'Push a block (A7)',
    3:'Step on a button',4:'Special / externally handled (Color fairy)',
    5:'Light two torches',6:'Defeat three enemies in order',7:'Push blocks together horizontally',
    8:'Defeat special enemies',9:'Solve glowing-tile puzzle',10:'Defeat side-view boss',
    11:'Throw something at a shut door',12:'Make both horse heads stand',
    13:'Throw a pot at the special chest',14:'Fill gaps with rolling platform',
    15:'Shoot statue eye upward',16:'Color Dungeon puzzle'}
EFFECTS={0:'None',0x20:'Open shutter doors',0x40:'Destroy eligible active sprites',
    0x60:'Reveal chest',0x80:'Drop small key',0xA0:'Reveal stairs',
    0xC0:'Miniboss completion / shutters',0xE0:'Drop fairy (unused in original events)'}


def event_offset(data,map_id,room):
    dungeon.check_map(map_id)
    if not isinstance(room,int) or not 0<=room<(22 if map_id==255 else 256):
        raise ValueError('Invalid indoor room.')
    at=(0x50200 if map_id==255 else 0x50100 if dungeon.room_bank(map_id)=='B' else 0x50000)+room
    if at>=len(data):raise ValueError('Room event table is missing.')
    return at


def event_changes(data,map_id,room,trigger,effect,expected=None):
    at=event_offset(data,map_id,room);old=data[at]
    if expected is not None and expected!=(at,old):raise ValueError('Room event changed. Select the room again.')
    if not isinstance(trigger,int) or trigger not in TRIGGERS:
        raise ValueError('Choose a decoded trigger; unknown existing events are preserved until replaced.')
    if effect not in EFFECTS:raise ValueError('Choose a supported event effect.')
    # Trigger 00 is unsafe with a nonzero effect: the native dispatch decrements
    # the trigger before indexing its table. Treat None as the whole event off.
    value=trigger|effect if trigger else 0
    return [] if value==old else [(at,old,value)]


def label(value,labels):return f'{value:02X} — {labels.get(value,"Unknown / preserve existing")}'


class RoomEventsMixin:
    def build_events(self,tabs):
        page=ttk.Frame(tabs,padding=12);tabs.add(page,text='Room Events')
        self.event_trigger=tk.StringVar();self.event_effect=tk.StringVar()
        self.event_summary=tk.StringVar();self.event_feedback=tk.StringVar();self._event_expected=None
        ttk.Label(page,textvariable=self.event_summary,wraplength=430).pack(anchor='w',pady=(0,12))
        self.event_inputs=[]
        for name,var,values in (('Trigger',self.event_trigger,TRIGGERS),('Effect',self.event_effect,EFFECTS)):
            ttk.Label(page,text=name).pack(anchor='w')
            combo=ttk.Combobox(page,textvariable=var,state='disabled',values=[label(v,values) for v in values])
            combo.pack(fill='x',pady=(2,12));combo.bind('<<ComboboxSelected>>',self.change_event);self.event_inputs.append(combo)
        ttk.Label(page,text='Changes apply immediately. Undo/Redo uses the shared editor history.\n\nTrigger 00 disables the entire event.\n\nShutter and miniboss effects can close doors and play the closing sound on entry, even without shutter objects.\n\nKey-drop events and key chest rewards can trigger the compass alert. Chest contents are separate.\n\nSpecial puzzles require their original objects, sprites or room-specific code. Trigger 10 handles Color Dungeon puzzles, including room 12 tunic answers.\n\nEvents are shared by layouts using the same physical room. Existing save flags are not reset.',wraplength=430,justify='left').pack(anchor='w')
        ttk.Label(page,textvariable=self.event_feedback,wraplength=430).pack(anchor='w',pady=10)

    def reset_events(self):
        self._event_expected=None
        self.event_trigger.set('');self.event_effect.set('');self.event_summary.set('');self.event_feedback.set('')
        for combo in self.event_inputs:combo.configure(state='disabled')

    def refresh_events(self,context):
        at=event_offset(self.owner.data,context,self.owner.room);value=self.owner.data[at]
        trigger=value&31;effect=value&224
        self._event_expected=(at,value)
        self.event_trigger.set(label(trigger,TRIGGERS));self.event_effect.set(label(effect,EFFECTS))
        self.event_inputs[0].configure(state='readonly',values=[label(v,TRIGGERS) for v in sorted(set(TRIGGERS)|{trigger})])
        self.event_inputs[1].configure(state='readonly')
        self.event_summary.set(f'Room {self.owner.room:02X} · Bank {dungeon.room_bank(context)}\nEvent {value:02X} = trigger {trigger:02X} + effect {effect:02X}\nROM {at:06X}')

    def change_event(self,event=None):
        if self._extra_loading or self._target is None or self._event_expected is None:return
        try:
            trigger=int(self.event_trigger.get()[:2],16);effect=int(self.event_effect.get()[:2],16)
            self.owner.apply_room_changes(event_changes(self.owner.data,*self._target,trigger,effect,self._event_expected))
            self.refresh_events(self._target[0]);self.event_feedback.set('')
        except (ValueError,IndexError,TypeError) as exc:self.event_feedback.set(str(exc))
