"""Byte-accurate undo/redo for direct overworld overlay painting."""

MAX_HISTORY = 64


class StrokeHistory:
    def __init__(self):
        self.clear()

    def clear(self):
        self.undo_stack = []
        self.redo_stack = []
        self.pending = {}

    @property
    def can_undo(self):
        return bool(self.undo_stack or self.pending)

    @property
    def can_redo(self):
        return bool(self.redo_stack)

    def record(self, offset, before, after, room, alternate):
        if offset in self.pending:
            original = self.pending[offset][1]
            self.pending[offset] = (offset, original, after, room, alternate)
        else:
            self.pending[offset] = (offset, before, after, room, alternate)

    def commit(self):
        if not self.pending:
            return False
        stroke = [v for v in self.pending.values() if v[1] != v[2]]
        self.pending.clear()
        if stroke:
            self.undo_stack.append(stroke)
            del self.undo_stack[:-MAX_HISTORY]
            self.redo_stack.clear()
            return True
        return False

    def undo(self, data):
        self.commit()
        if not self.undo_stack:
            return []
        stroke = self.undo_stack.pop()
        for offset, before, after, room, alternate in stroke:
            data[offset] = before
        self.redo_stack.append(stroke)
        del self.redo_stack[:-MAX_HISTORY]
        return stroke

    def redo(self, data):
        if not self.redo_stack:
            return []
        stroke = self.redo_stack.pop()
        for offset, before, after, room, alternate in stroke:
            data[offset] = after
        self.undo_stack.append(stroke)
        del self.undo_stack[:-MAX_HISTORY]
        return stroke
