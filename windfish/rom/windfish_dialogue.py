"""Native/VWF dialog editing plus optional native bank-7F added dialogs.

Original entries retain bounded in-place edits and alias protection. Additional
IDs use a separate packed pool whose pointers are rebuilt on every edit.
"""
from windfish.rom import windfish_dialogue_expansion as expansion

COUNT = 0x2B0
POINTERS = 0x70001
BANKS = 0x70741
CHARACTERS = {
    0x20: ' ',
    0x21: '!',
    0x22: '"',
    0x23: '#',
    0x26: '&',
    0x28: '(',
    0x29: ')',
    0x2C: ',',
    0x2D: '-',
    0x2E: '.',
    0x30: '0',
    0x31: '1',
    0x32: '2',
    0x33: '3',
    0x34: '4',
    0x35: '5',
    0x36: '6',
    0x37: '7',
    0x38: '8',
    0x39: '9',
    0x3A: ':',
    0x3B: ';',
    0x3F: '?',
    0x41: 'A',
    0x42: 'B',
    0x43: 'C',
    0x44: 'D',
    0x45: 'E',
    0x46: 'F',
    0x47: 'G',
    0x48: 'H',
    0x49: 'I',
    0x4A: 'J',
    0x4B: 'K',
    0x4C: 'L',
    0x4D: 'M',
    0x4E: 'N',
    0x4F: 'O',
    0x50: 'P',
    0x51: 'Q',
    0x52: 'R',
    0x53: 'S',
    0x54: 'T',
    0x55: 'U',
    0x56: 'V',
    0x57: 'W',
    0x58: 'X',
    0x59: 'Y',
    0x5A: 'Z',
    0x5E: "'",
    0x61: 'a',
    0x62: 'b',
    0x63: 'c',
    0x64: 'd',
    0x65: 'e',
    0x66: 'f',
    0x67: 'g',
    0x68: 'h',
    0x69: 'i',
    0x6A: 'j',
    0x6B: 'k',
    0x6C: 'l',
    0x6D: 'm',
    0x6E: 'n',
    0x6F: 'o',
    0x70: 'p',
    0x71: 'q',
    0x72: 'r',
    0x73: 's',
    0x74: 't',
    0x75: 'u',
    0x76: 'v',
    0x77: 'w',
    0x78: 'x',
    0x79: 'y',
    0x7A: 'z',
    0x7F: '+',
    0x80: 'Á',
    0x81: 'É',
    0x82: 'Í',
    0x83: 'Ó',
    0x84: 'Ú',
    0x85: 'Ü',
    0x86: 'Ñ',
    0x88: 'Ç',
    0x89: 'á',
    0x8A: 'é',
    0x8B: 'í',
    0x8C: 'ó',
    0x8D: 'ú',
    0x8E: 'ü',
    0x8F: 'ñ',
    0x90: 'à',
    0x91: 'è',
    0x92: 'ì',
    0x93: 'ò',
    0x94: 'ù',
    0x95: 'ä',
    0x96: 'ë',
    0x97: 'ï',
    0x98: 'ö',
    0x9A: '¡',
    0x9B: '¿',
    0x9C: '`',
    0xB0: 'â',
    0xB1: 'ê',
    0xB2: 'î',
    0xB3: 'ô',
    0xB4: 'û',
    0xD9: '<flower>',
    0xDA: '<footprint>',
    0xDC: '<skull>',
    0xDD: '<link>',
    0xDE: '<marin>',
    0xDF: '<tarin>',
    0xE0: '<yoshi>',
    0xE1: '<ribbon>',
    0xE2: '<dogfood>',
    0xE3: '<bananas>',
    0xE4: '<stick>',
    0xE5: '<honeycomb>',
    0xE6: '<pineapple>',
    0xE7: '<flower2>',
    0xE8: '<broom>',
    0xE9: '<fishhook>',
    0xEA: '<bra>',
    0xEB: '<scale>',
    0xEC: '<glass>',
    0xED: '<letter>',
    0xEE: '<dpad>',
    0xF0: '<up>',
    0xF1: '<down>',
    0xF2: '<left>',
    0xF3: '<right>',
    0xFD: '/',
}

import re


def validate(data):
    if is_vwf(data):
        return vwf_codec().validate(data)
    if (len(data) not in (0x100000, 0x200000) or data[0x13F:0x143] != b'AZLE'
            or data[0x14C] != 2):
        raise ValueError('Text editing requires English Link’s Awakening DX Rev2.')
    # The native reader loads both tables and masks bank flags with 3F.
    # HUD-on-Top can change nearby code; verify lookup sequences, not the ISR.
    if expansion.enabled(data):
        expansion.records(data)
        return
    code = bytes(data[0x2300:0x2800])
    if (bytes.fromhex('21 01 40 19 2a 5f 56') not in code or
            bytes.fromhex('21 41 47 19 7e e6 3f') not in code):
        raise ValueError('Custom dialogue reader detected; native text editing is unavailable.')


def records(data):
    """Resolve all native entries, retaining bank flag bits and alias identity."""
    if is_vwf(data):
        return vwf_codec().records(data)
    validate(data)
    result = []
    for index in range(COUNT):
        pointer = int.from_bytes(data[POINTERS + index * 2:POINTERS + index * 2 + 2], 'little')
        flag = data[BANKS + index]
        bank = flag & 0x3F
        if not 0x4000 <= pointer < 0x8000:
            raise ValueError(f'Dialogue {index:03X}: invalid pointer.')
        start = bank * 0x4000 + pointer - 0x4000
        limit = (bank + 1) * 0x4000
        end = next((at + 1 for at in range(start, limit) if data[at] in (0xFE, 0xFF)), None)
        if end is None:
            raise ValueError(f'Dialogue {index:03X}: missing ending within its bank.')
        result.append((start, bytes(data[start:end]), flag))
    return tuple(result)+expansion.records(data)


def decode(raw, data=None):
    """Display one glyph per cell; unknown glyphs round-trip as <$XX>."""
    if data is not None and is_vwf(data):
        return vwf_codec().decode(raw)
    if not raw or raw[-1] not in (0xFE, 0xFF):
        raise ValueError('Missing dialogue ending.')
    lines = []
    for start in range(0, len(raw) - 1, 16):
        lines.append(''.join(CHARACTERS.get(byte, f'<${byte:02X}>') for byte in raw[start:min(start + 16, len(raw) - 1)]))
    return '\n'.join(lines), raw[-1]


def glyphs(text):
    """Parse Unicode/charmap tokens without treating token spelling as width."""
    reverse = {value: key for key, value in CHARACTERS.items()}
    tokens = sorted(reverse, key=len, reverse=True)
    result = []
    while text:
        raw = re.match(r'<\$([0-9A-Fa-f]{2})>', text)
        if raw:
            value = int(raw[1], 16)
            if value >= 0xFE:
                raise ValueError('Choose the ending separately; FE/FF cannot appear inside text.')
            result.append(value)
            text = text[len(raw[0]):]
            continue
        token = next((token for token in tokens if text.startswith(token)), None)
        if token is None:
            raise ValueError(f'Unsupported text character near {text[:16]!r}. Use the token list for special glyphs.')
        result.append(reverse[token])
        text = text[len(token):]
    return result


def encode(text, ending=0xFF, data=None):
    """Wrap long input at words; explicit newlines advance to a 16-cell boundary.

    Existing decoded 16-cell lines are preserved exactly, including spaces.
    Word wrapping occurs only when an entered line exceeds sixteen glyphs.
    """
    if data is not None and is_vwf(data):
        return vwf_codec().encode(text, ending)
    if ending not in (0xFE, 0xFF):
        raise ValueError('Choose normal end FF or choice end FE.')
    result = bytearray()
    lines = text.replace('\r\n', '\n').split('\n')
    for index, line in enumerate(lines):
        values = glyphs(line)
        while len(values) > 16:
            split = next((i for i in range(16, 0, -1) if values[i] == 0x20), 16)
            part = values[:split]
            result.extend(part)
            result.extend(b' ' * (16 - len(part)))
            values = values[split + 1:] if values[split] == 0x20 else values[split:]
        result.extend(values)
        if index < len(lines) - 1:
            padding = (-len(result)) % 16
            if not values and padding == 0:
                padding = 16
            result.extend(b' ' * padding)
    result.append(ending)
    return bytes(result)


def changes(data, index, text, ending, expected=None):
    if is_vwf(data):
        return vwf_codec().changes(data, index, text, ending, expected)
    if isinstance(index,int) and index>=COUNT:
        return expansion.changes(data,index,encode(text,ending,data=data),expected)
    if not isinstance(index, int) or not 0 <= index < COUNT:
        raise ValueError('Select a dialogue ID 000–2AF.')
    all_records = records(data)
    start, original, flag = all_records[index]
    if expected is not None and expected != (start, original, flag):
        raise ValueError('Dialogue changed. Reload the selected entry before applying.')
    new = encode(text, ending)
    if len(new) > len(original):
        raise ValueError(f'Text needs {len(new)} bytes; this entry currently has {len(original)}. Text expansion is not supported yet.')
    # Exact pointer aliases intentionally edit together. Suffix/interior aliases
    # need detachment support and are rejected before any byte changes are made.
    end = start + len(original)
    for other, raw, _ in all_records:
        if other != start and max(start, other) < min(end, other + len(raw)):
            raise ValueError('This dialogue overlaps another text entry. Relocation support is required to edit it.')
    payload = new.ljust(len(original), b'\xFF')
    return [(start + i, old, value) for i, (old, value) in enumerate(zip(original, payload)) if old != value]


def is_vwf(data):
    from windfish.compatibility.api import is_vwf as detect
    return data is not None and detect(data)


def vwf_codec():
    from windfish.compatibility.api import vwf_codec as codec
    return codec()


def characters(data):
    return vwf_codec().characters() if is_vwf(data) else CHARACTERS


def add_changes(data):
    """Allocate the next sequential ID, initialized to an empty normal dialog."""
    validate(data)
    if is_vwf(data):raise ValueError('Additional dialog IDs currently require the native Rev2 test profile.')
    return expansion.changes(data)
