"""Literal 8x8 tile transfers during room scrolling, including tile EE.

The native room-stream producer emits 20 data bytes for a horizontal row,
16 data bytes plus four EE padding bytes for a vertical column. Its consumer
skips EE by value; the row consumer also fails to advance the destination.
Use explicit 20/16 lengths and zero terminators instead. No new allocation,
command format, RAM or bank is needed. The non-transition drawer is untouched.
"""
from windfish.compatibility import api as profile


def records(data):
    layout=profile.transition_tile_layout(data,{
        'row_skip':0x2993,'column_skip':0x29A8,'lengths':0x809F0,
        'dmg_padding':0x80A0F,'cgb_padding':0x80A49})
    padding=bytes.fromhex('3e ee ea 14 d6 ea 15 d6 ea 16 d6 ea 17 d6')
    return (
        (layout['row_skip'],bytes.fromhex('fe ee 28 0b'),bytes(4)),
        (layout['column_skip'],bytes.fromhex('fe ee 28 01'),bytes(4)),
        (layout['lengths'],bytes.fromhex('93 93 13 13'),bytes.fromhex('8f 8f 13 13')),
        (layout['dmg_padding'],padding,padding[:1]+b'\0'+padding[2:]),
        (layout['cgb_padding'],padding,padding[:1]+b'\0'+padding[2:]),
    )


def check_original(data):
    """Refuse any unknown producer/consumer modifications before upgrading."""
    for at,old,new in records(data):
        if bytes(data[at:at+len(old)])!=old:
            raise ValueError(f'Room transition tile transfer conflicts at {at:06X}.')


def code(data):
    return {at:new for at,old,new in records(data)}
