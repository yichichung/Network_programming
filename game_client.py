# game_client.py
import pygame
import socket
import json
import threading
import sys
import os
import time
import argparse

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lobby_server'))
from protocol import send_message, recv_message, ProtocolError

# Initialize Pygame
pygame.init()

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 100, 255)
CYAN = (0, 255, 255)
YELLOW = (255, 255, 0)
MAGENTA = (255, 0, 255)
ORANGE = (255, 165, 0)

# Piece colors
PIECE_COLORS = {
    'I': CYAN,
    'O': YELLOW,
    'T': MAGENTA,
    'S': GREEN,
    'Z': RED,
    'J': BLUE,
    'L': ORANGE
}

# Display settings
CELL_SIZE = 30
BOARD_WIDTH = 10
BOARD_HEIGHT = 20
MINI_CELL_SIZE = 15

# Screen dimensions
INFO_WIDTH = 200
MAIN_BOARD_WIDTH = BOARD_WIDTH * CELL_SIZE
MAIN_BOARD_HEIGHT = BOARD_HEIGHT * CELL_SIZE
MINI_BOARD_WIDTH = BOARD_WIDTH * MINI_CELL_SIZE
MINI_BOARD_HEIGHT = BOARD_HEIGHT * MINI_CELL_SIZE

SCREEN_WIDTH = INFO_WIDTH + MAIN_BOARD_WIDTH + 20 + MINI_BOARD_WIDTH + 40
SCREEN_HEIGHT = max(MAIN_BOARD_HEIGHT, MINI_BOARD_HEIGHT) + 100


class GameClient:
    """Tetris Game Client with GUI"""

    def __init__(self, host, port, room_id, user_id):
        self.host = host
        self.port = port
        self.room_id = room_id
        self.user_id = user_id

        # Connection
        self.sock = None
        self.connected = False
        self.running = True

        # Game state
        self.role = None
        self.seed = None
        self.my_board = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.opponent_board = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.my_score = 0
        self.my_lines = 0
        self.my_level = 1
        self.opponent_score = 0
        self.opponent_lines = 0
        self.opponent_level = 1
        self.my_hold = None
        self.my_next = []
        self.game_over = False
        self.winner = None

        # Input tracking
        self.input_seq = 0
        self.last_key_time = {}
        self.key_repeat_delay = 0.05  # seconds - faster response

        # Lock for thread-safe updates
        self.lock = threading.Lock()

        # Pygame setup
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"Tetris - Player {user_id}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 48)

    def connect(self):
        """Connect to game server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"✅ Connected to Game Server ({self.host}:{self.port})")

            # Send HELLO
            hello_msg = {
                "type": "HELLO",
                "version": 1,
                "roomId": self.room_id,
                "userId": self.user_id
            }
            send_message(self.sock, json.dumps(hello_msg))

            # Receive WELCOME
            welcome_str = recv_message(self.sock)
            welcome = json.loads(welcome_str)

            if welcome.get("type") == "WELCOME":
                self.role = welcome.get("role")
                self.seed = welcome.get("seed")
                print(f"✅ Welcomed as {self.role}, seed: {self.seed}")
                self.connected = True
                return True
            else:
                print(f"❌ Unexpected response: {welcome}")
                return False

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def start(self):
        """Start client"""
        if not self.connect():
            return

        # Start network thread
        network_thread = threading.Thread(target=self.network_loop, daemon=True)
        network_thread.start()

        # Start game loop
        self.game_loop()

    def network_loop(self):
        """Receive messages from server"""
        try:
            while self.running and self.connected:
                msg_str = recv_message(self.sock)
                msg = json.loads(msg_str)

                msg_type = msg.get("type")

                if msg_type == "SNAPSHOT":
                    self.handle_snapshot(msg)
                elif msg_type == "GAME_OVER":
                    self.handle_game_over(msg)
                elif msg_type == "TEMPO":
                    pass  # Handle tempo updates if needed

        except ProtocolError:
            print("🔌 Connection closed")
        except Exception as e:
            print(f"❌ Network error: {e}")
        finally:
            self.connected = False

    def handle_snapshot(self, snapshot):
        """Handle snapshot message"""
        user_id = snapshot.get("userId")
        role = snapshot.get("role")

        # Decompress board
        board_rle = snapshot.get("boardRLE", "")
        board = self.decompress_board(board_rle)

        with self.lock:
            if user_id == self.user_id:
                # My board
                self.my_board = board
                self.my_score = snapshot.get("score", 0)
                self.my_lines = snapshot.get("lines", 0)
                self.my_level = snapshot.get("level", 1)
                self.my_hold = snapshot.get("hold")
                self.my_next = snapshot.get("next", [])
            else:
                # Opponent's board
                self.opponent_board = board
                self.opponent_score = snapshot.get("score", 0)
                self.opponent_lines = snapshot.get("lines", 0)
                self.opponent_level = snapshot.get("level", 1)

    def decompress_board(self, board_rle):
        """Decompress RLE board"""
        if not board_rle:
            return [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]

        flat = []
        for token in board_rle.split(","):
            if "x" in token:
                value, count = token.split("x")
                flat.extend([int(value)] * int(count))

        # Reshape to 2D
        board = []
        for i in range(BOARD_HEIGHT):
            row = flat[i * BOARD_WIDTH:(i + 1) * BOARD_WIDTH]
            if len(row) < BOARD_WIDTH:
                row.extend([0] * (BOARD_WIDTH - len(row)))
            board.append(row)

        return board

    def handle_game_over(self, msg):
        """Handle game over message"""
        with self.lock:
            self.game_over = True
            self.winner = msg.get("winner")
        print(f"🎮 Game Over! Winner: {self.winner}")

    def send_input(self, action):
        """Send input to server"""
        if not self.connected:
            return

        self.input_seq += 1

        input_msg = {
            "type": "INPUT",
            "userId": self.user_id,
            "seq": self.input_seq,
            "ts": int(time.time() * 1000),
            "action": action
        }

        try:
            send_message(self.sock, json.dumps(input_msg))
        except Exception as e:
            print(f"❌ Failed to send input: {e}")

    def handle_input(self):
        """Handle keyboard input"""
        keys = pygame.key.get_pressed()
        current_time = time.time()

        # Map keys to actions with repeat delay
        key_actions = [
            (pygame.K_LEFT, "LEFT"),
            (pygame.K_RIGHT, "RIGHT"),
            (pygame.K_DOWN, "DOWN"),
            (pygame.K_UP, "CW"),           # Rotate clockwise
            (pygame.K_z, "CCW"),           # Rotate counter-clockwise
            (pygame.K_SPACE, "HARD_DROP"),
            (pygame.K_c, "HOLD")
        ]

        for key, action in key_actions:
            if keys[key]:
                # Check repeat delay
                last_time = self.last_key_time.get(key, 0)
                if current_time - last_time > self.key_repeat_delay:
                    print(f"🎮 Sending input: {action}")  # Debug output
                    self.send_input(action)
                    self.last_key_time[key] = current_time

    def draw_board(self, surface, board, cell_size, offset_x, offset_y):
        """Draw a Tetris board"""
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                cell = board[y][x]

                # Cell position
                px = offset_x + x * cell_size
                py = offset_y + y * cell_size

                # Draw cell
                if cell == 0:
                    # Empty
                    color = BLACK
                    pygame.draw.rect(surface, DARK_GRAY, (px, py, cell_size, cell_size), 1)
                elif cell == 1:
                    # Locked block
                    color = GRAY
                    pygame.draw.rect(surface, color, (px, py, cell_size, cell_size))
                    pygame.draw.rect(surface, WHITE, (px, py, cell_size, cell_size), 1)
                elif cell == 2:
                    # Active piece
                    color = GREEN
                    pygame.draw.rect(surface, color, (px, py, cell_size, cell_size))
                    pygame.draw.rect(surface, WHITE, (px, py, cell_size, cell_size), 2)

    def draw_piece_preview(self, surface, piece_type, x, y, size=20):
        """Draw a small piece preview"""
        if not piece_type:
            return

        color = PIECE_COLORS.get(piece_type, GRAY)

        # Simple representation
        if piece_type == 'I':
            for i in range(4):
                pygame.draw.rect(surface, color, (x + i * size, y, size - 2, size - 2))
        elif piece_type == 'O':
            for dy in range(2):
                for dx in range(2):
                    pygame.draw.rect(surface, color, (x + dx * size, y + dy * size, size - 2, size - 2))
        else:
            # Generic 3-block representation
            for i in range(3):
                pygame.draw.rect(surface, color, (x + i * size, y, size - 2, size - 2))

    def draw_ui(self):
        """Draw UI elements"""
        self.screen.fill(BLACK)

        with self.lock:
            # Info panel (left)
            info_x = 10
            y_offset = 20

            # Role
            role_text = self.font.render(f"Role: {self.role or '?'}", True, WHITE)
            self.screen.blit(role_text, (info_x, y_offset))
            y_offset += 30

            # My stats
            score_text = self.font.render(f"Score: {self.my_score}", True, WHITE)
            self.screen.blit(score_text, (info_x, y_offset))
            y_offset += 25

            lines_text = self.font.render(f"Lines: {self.my_lines}", True, WHITE)
            self.screen.blit(lines_text, (info_x, y_offset))
            y_offset += 25

            level_text = self.font.render(f"Level: {self.my_level}", True, WHITE)
            self.screen.blit(level_text, (info_x, y_offset))
            y_offset += 40

            # Hold piece
            hold_text = self.font.render("Hold:", True, WHITE)
            self.screen.blit(hold_text, (info_x, y_offset))
            y_offset += 25
            if self.my_hold:
                self.draw_piece_preview(self.screen, self.my_hold, info_x, y_offset)
            y_offset += 40

            # Next pieces
            next_text = self.font.render("Next:", True, WHITE)
            self.screen.blit(next_text, (info_x, y_offset))
            y_offset += 25
            for piece in self.my_next[:3]:
                self.draw_piece_preview(self.screen, piece, info_x, y_offset)
                y_offset += 25

            # Main board (center)
            board_x = INFO_WIDTH + 10
            board_y = 50
            self.draw_board(self.screen, self.my_board, CELL_SIZE, board_x, board_y)

            # Board label
            label = self.font.render("Your Board", True, WHITE)
            self.screen.blit(label, (board_x, 20))

            # Opponent board (right)
            mini_x = board_x + MAIN_BOARD_WIDTH + 20
            mini_y = 50
            self.draw_board(self.screen, self.opponent_board, MINI_CELL_SIZE, mini_x, mini_y)

            # Opponent label
            opp_label = self.font.render("Opponent", True, WHITE)
            self.screen.blit(opp_label, (mini_x, 20))

            # Opponent stats
            opp_stats_y = mini_y + MINI_BOARD_HEIGHT + 20
            opp_score = self.font.render(f"Score: {self.opponent_score}", True, WHITE)
            self.screen.blit(opp_score, (mini_x, opp_stats_y))

            opp_lines = self.font.render(f"Lines: {self.opponent_lines}", True, WHITE)
            self.screen.blit(opp_lines, (mini_x, opp_stats_y + 25))

            # Game over overlay
            if self.game_over:
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                overlay.set_alpha(200)
                overlay.fill(BLACK)
                self.screen.blit(overlay, (0, 0))

                if self.winner == self.user_id:
                    text = self.big_font.render("YOU WIN!", True, GREEN)
                elif self.winner is None:
                    text = self.big_font.render("DRAW!", True, YELLOW)
                else:
                    text = self.big_font.render("YOU LOSE!", True, RED)

                text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                self.screen.blit(text, text_rect)

            # Controls hint
            controls_y = SCREEN_HEIGHT - 60
            controls = [
                "Controls: ← → ↓ (move), ↑ (rotate CW), Z (rotate CCW),",
                "SPACE (hard drop), C (hold)"
            ]
            for i, line in enumerate(controls):
                text = self.font.render(line, True, GRAY)
                self.screen.blit(text, (10, controls_y + i * 20))

    def game_loop(self):
        """Main game loop"""
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            # Handle input
            if self.connected and not self.game_over:
                self.handle_input()

            # Draw
            self.draw_ui()
            pygame.display.flip()

            # FPS limit
            self.clock.tick(60)

        self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="Tetris Game Client")
    parser.add_argument("--host", type=str, default="localhost", help="Game server host")
    parser.add_argument("--port", type=int, required=True, help="Game server port")
    parser.add_argument("--room-id", type=int, required=True, help="Room ID")
    parser.add_argument("--user-id", type=int, required=True, help="User ID")

    args = parser.parse_args()

    client = GameClient(
        host=args.host,
        port=args.port,
        room_id=args.room_id,
        user_id=args.user_id
    )

    try:
        client.start()
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
    finally:
        client.cleanup()


if __name__ == "__main__":
    main()
