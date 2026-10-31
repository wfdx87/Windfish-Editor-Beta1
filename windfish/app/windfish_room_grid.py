"""GUI-independent 16×16 overworld room selector geometry."""
GRID_SIZE = 16
ROOM_COUNT = GRID_SIZE * GRID_SIZE


def centered_geometry(width, height, margin=20):
    """Return (left, top, cell size) for a square grid centered in a canvas."""
    side = min(max(1, width), max(1, height)) - margin
    cell = side / GRID_SIZE
    return (width - side) / 2, (height - side) / 2, cell


def room_at(x, y, geometry):
    """Convert a click to a room ID; return None for clicks outside the grid."""
    left, top, cell = geometry
    if cell <= 0 or x < left or y < top:
        return None
    column = int((x - left) // cell)
    row = int((y - top) // cell)
    if 0 <= column < GRID_SIZE and 0 <= row < GRID_SIZE:
        return row * GRID_SIZE + column
    return None


def room_rect(room, geometry):
    """Rectangle coordinates for a room in row-major room ID order."""
    if not 0 <= room < ROOM_COUNT:
        raise ValueError('Room ID must be between 00 and FF')
    left, top, cell = geometry
    x = left + (room % GRID_SIZE) * cell
    y = top + (room // GRID_SIZE) * cell
    return x, y, x + cell, y + cell
