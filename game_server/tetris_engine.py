# tetris_engine.py
import random
import time
from copy import deepcopy

# Tetromino shapes (standard Tetris pieces)
SHAPES = {
    'I': [
        [[0, 0, 0, 0],
         [1, 1, 1, 1],
         [0, 0, 0, 0],
         [0, 0, 0, 0]]
    ],
    'O': [
        [[1, 1],
         [1, 1]]
    ],
    'T': [
        [[0, 1, 0],
         [1, 1, 1],
         [0, 0, 0]],
        [[0, 1, 0],
         [0, 1, 1],
         [0, 1, 0]],
        [[0, 0, 0],
         [1, 1, 1],
         [0, 1, 0]],
        [[0, 1, 0],
         [1, 1, 0],
         [0, 1, 0]]
    ],
    'S': [
        [[0, 1, 1],
         [1, 1, 0],
         [0, 0, 0]],
        [[0, 1, 0],
         [0, 1, 1],
         [0, 0, 1]]
    ],
    'Z': [
        [[1, 1, 0],
         [0, 1, 1],
         [0, 0, 0]],
        [[0, 0, 1],
         [0, 1, 1],
         [0, 1, 0]]
    ],
    'J': [
        [[1, 0, 0],
         [1, 1, 1],
         [0, 0, 0]],
        [[0, 1, 1],
         [0, 1, 0],
         [0, 1, 0]],
        [[0, 0, 0],
         [1, 1, 1],
         [0, 0, 1]],
        [[0, 1, 0],
         [0, 1, 0],
         [1, 1, 0]]
    ],
    'L': [
        [[0, 0, 1],
         [1, 1, 1],
         [0, 0, 0]],
        [[0, 1, 0],
         [0, 1, 0],
         [0, 1, 1]],
        [[0, 0, 0],
         [1, 1, 1],
         [1, 0, 0]],
        [[1, 1, 0],
         [0, 1, 0],
         [0, 1, 0]]
    ]
}

PIECE_TYPES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']


class PieceGenerator:
    """7-bag piece generator with Fisher-Yates shuffle"""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.bag = []

    def next_piece(self):
        """Get next piece from bag"""
        if not self.bag:
            # Refill bag with all 7 pieces
            self.bag = PIECE_TYPES.copy()
            self.rng.shuffle(self.bag)  # Fisher-Yates

        return self.bag.pop(0)

    def peek(self, count=3):
        """Peek at next N pieces without consuming"""
        result = []
        temp_bag = self.bag.copy()
        temp_rng_state = self.rng.getstate()

        for _ in range(count):
            if not temp_bag:
                temp_bag = PIECE_TYPES.copy()
                temp_rng = random.Random()
                temp_rng.setstate(temp_rng_state)
                temp_rng.shuffle(temp_bag)
                temp_rng_state = temp_rng.getstate()

            result.append(temp_bag.pop(0))

        return result


class TetrisBoard:
    """Individual player's Tetris board"""

    def __init__(self, width=10, height=20, piece_generator=None):
        self.width = width
        self.height = height
        self.board = [[0] * width for _ in range(height)]

        self.piece_gen = piece_generator or PieceGenerator()

        # Current piece state
        self.current_piece = None
        self.current_type = None
        self.current_rotation = 0
        self.current_x = 0
        self.current_y = 0

        # Hold piece
        self.hold_piece = None
        self.can_hold = True

        # Stats
        self.score = 0
        self.lines_cleared = 0
        self.level = 1

        # Game state
        self.game_over = False

        # Spawn first piece
        self.spawn_piece()

    def spawn_piece(self):
        """Spawn a new piece at the top"""
        self.current_type = self.piece_gen.next_piece()
        self.current_piece = SHAPES[self.current_type]
        self.current_rotation = 0

        # Center at top
        piece_width = len(self.current_piece[0][0])
        self.current_x = self.width // 2 - piece_width // 2
        self.current_y = 0

        self.can_hold = True

        # Check if piece can spawn (game over check)
        if not self._is_valid_position(self.current_x, self.current_y, self.current_rotation):
            self.game_over = True

    def _is_valid_position(self, x, y, rotation):
        """Check if piece position is valid"""
        shape = self.current_piece[rotation]

        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    board_x = x + col_idx
                    board_y = y + row_idx

                    # Check bounds
                    if board_x < 0 or board_x >= self.width:
                        return False
                    if board_y >= self.height:
                        return False
                    if board_y < 0:
                        continue

                    # Check collision with board
                    if self.board[board_y][board_x]:
                        return False

        return True

    def move_left(self):
        """Move piece left"""
        if self._is_valid_position(self.current_x - 1, self.current_y, self.current_rotation):
            self.current_x -= 1
            return True
        return False

    def move_right(self):
        """Move piece right"""
        if self._is_valid_position(self.current_x + 1, self.current_y, self.current_rotation):
            self.current_x += 1
            return True
        return False

    def move_down(self):
        """Move piece down (soft drop)"""
        if self._is_valid_position(self.current_x, self.current_y + 1, self.current_rotation):
            self.current_y += 1
            return True
        else:
            # Lock piece
            self.lock_piece()
            return False

    def rotate_cw(self):
        """Rotate clockwise"""
        new_rotation = (self.current_rotation + 1) % len(self.current_piece)
        if self._is_valid_position(self.current_x, self.current_y, new_rotation):
            self.current_rotation = new_rotation
            return True
        return False

    def rotate_ccw(self):
        """Rotate counter-clockwise"""
        new_rotation = (self.current_rotation - 1) % len(self.current_piece)
        if self._is_valid_position(self.current_x, self.current_y, new_rotation):
            self.current_rotation = new_rotation
            return True
        return False

    def hard_drop(self):
        """Drop piece immediately"""
        drop_distance = 0
        while self._is_valid_position(self.current_x, self.current_y + 1, self.current_rotation):
            self.current_y += 1
            drop_distance += 1

        self.lock_piece()
        return drop_distance

    def hold_current_piece(self):
        """Hold current piece"""
        if not self.can_hold:
            return False

        if self.hold_piece is None:
            # First hold
            self.hold_piece = self.current_type
            self.spawn_piece()
        else:
            # Swap with held piece
            self.hold_piece, self.current_type = self.current_type, self.hold_piece
            self.current_piece = SHAPES[self.current_type]
            self.current_rotation = 0

            # Re-center
            piece_width = len(self.current_piece[0][0])
            self.current_x = self.width // 2 - piece_width // 2
            self.current_y = 0

        self.can_hold = False
        return True

    def lock_piece(self):
        """Lock current piece to board"""
        shape = self.current_piece[self.current_rotation]

        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    board_x = self.current_x + col_idx
                    board_y = self.current_y + row_idx

                    if 0 <= board_y < self.height and 0 <= board_x < self.width:
                        self.board[board_y][board_x] = 1

        # Clear lines
        lines = self.clear_lines()
        if lines > 0:
            self.lines_cleared += lines
            # Scoring: 100, 300, 500, 800 for 1-4 lines
            line_scores = [0, 100, 300, 500, 800]
            self.score += line_scores[min(lines, 4)] * self.level

            # Level up every 10 lines
            self.level = self.lines_cleared // 10 + 1

        # Spawn next piece
        self.spawn_piece()

    def clear_lines(self):
        """Clear completed lines"""
        lines_cleared = 0
        y = self.height - 1

        while y >= 0:
            if all(self.board[y]):
                # Clear this line
                del self.board[y]
                self.board.insert(0, [0] * self.width)
                lines_cleared += 1
            else:
                y -= 1

        return lines_cleared

    def get_board_state(self):
        """Get current board state including active piece"""
        # Create a copy with current piece rendered
        display_board = [row[:] for row in self.board]

        if self.current_piece and not self.game_over:
            shape = self.current_piece[self.current_rotation]
            for row_idx, row in enumerate(shape):
                for col_idx, cell in enumerate(row):
                    if cell:
                        board_x = self.current_x + col_idx
                        board_y = self.current_y + row_idx

                        if 0 <= board_y < self.height and 0 <= board_x < self.width:
                            display_board[board_y][board_x] = 2  # Active piece marker

        return display_board

    def get_next_pieces(self, count=3):
        """Get preview of next pieces"""
        return self.piece_gen.peek(count)
