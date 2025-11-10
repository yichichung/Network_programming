# game_server.py
import socket
import json
import threading
import time
import argparse
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db_server.protocol import send_message, recv_message, ProtocolError

from tetris_engine import TetrisBoard, PieceGenerator

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class GameServer:
    """Game Server for 2-player Tetris"""

    def __init__(self, port, room_id, player1_id, player2_id, drop_interval=500, lobby_host='localhost', lobby_port=10002):
        self.port = port
        self.room_id = room_id
        self.player_ids = [player1_id, player2_id]
        self.lobby_host = lobby_host
        self.lobby_port = lobby_port

        self.drop_interval = drop_interval  # ms between gravity drops
        self.seed = int(time.time() * 1000) % (2**31)  # Random seed

        # Server socket
        self.server_socket = None
        self.running = False

        # Player connections
        self.players = {}  # {player_id: {"socket": sock, "board": TetrisBoard, "ready": bool}}
        self.spectators = {}  # {spectator_id: {"socket": sock, "addr": addr}}
        self.lock = threading.Lock()

        # Game state
        self.game_started = False
        self.game_over = False
        self.winner = None

        # Piece generators (shared seed for consistency)
        self.piece_gen1 = PieceGenerator(self.seed)
        self.piece_gen2 = PieceGenerator(self.seed)

    def start(self):
        """Start Game Server"""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(10)  # Allow players + spectators
            self.running = True

            logger.info(f"🎮 Game Server started on port {self.port}")
            logger.info(f"   Room: {self.room_id}, Players: {self.player_ids}")
            logger.info(f"   Seed: {self.seed}")

            # Accept 2 players
            self.accept_players()

            # Wait for both players to be ready
            if len(self.players) == 2:
                logger.info("✅ Both players connected, starting game...")

                # Start spectator acceptance thread
                spectator_thread = threading.Thread(
                    target=self.accept_spectators,
                    daemon=True
                )
                spectator_thread.start()

                self.start_game()

            else:
                logger.error("❌ Not all players connected, shutting down")

        except Exception as e:
            logger.error(f"❌ Error starting server: {e}")
        finally:
            self.shutdown()

    def accept_players(self):
        """Accept connections from 2 players"""
        self.server_socket.settimeout(30)  # 30s timeout for connections

        for i in range(2):
            try:
                client_sock, client_addr = self.server_socket.accept()
                logger.info(f"📥 Player {i+1} connected from {client_addr}")

                # Handle handshake in separate thread
                thread = threading.Thread(
                    target=self.handle_player_handshake,
                    args=(client_sock, client_addr),
                    daemon=True
                )
                thread.start()
                thread.join(timeout=10)  # Wait for handshake

            except socket.timeout:
                logger.error(f"⏰ Timeout waiting for player {i+1}")
                break
            except Exception as e:
                logger.error(f"❌ Error accepting player {i+1}: {e}")
                break

    def accept_spectators(self):
        """Accept spectator connections while game is running"""
        self.server_socket.settimeout(1.0)  # Short timeout for checking game state

        while self.running and not self.game_over:
            try:
                client_sock, client_addr = self.server_socket.accept()
                logger.info(f"👁️ Spectator connection from {client_addr}")

                # Handle spectator handshake in separate thread
                thread = threading.Thread(
                    target=self.handle_spectator_handshake,
                    args=(client_sock, client_addr),
                    daemon=True
                )
                thread.start()

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"❌ Error accepting spectator: {e}")

    def handle_spectator_handshake(self, client_sock, client_addr):
        """Handle spectator HELLO -> WELCOME handshake"""
        try:
            # Receive HELLO
            msg_str = recv_message(client_sock)
            msg = json.loads(msg_str)

            if msg.get("type") != "HELLO":
                logger.error(f"❌ Expected HELLO, got {msg.get('type')}")
                client_sock.close()
                return

            user_id = msg.get("userId")
            room_id = msg.get("roomId")
            is_spectator = msg.get("spectator", False)

            # Validate room
            if room_id != self.room_id:
                logger.error(f"❌ Wrong room ID: {room_id} != {self.room_id}")
                client_sock.close()
                return

            if not is_spectator:
                logger.error(f"❌ Not a spectator connection")
                client_sock.close()
                return

            # Store spectator info
            spectator_id = f"spectator_{user_id}_{int(time.time() * 1000)}"
            with self.lock:
                self.spectators[spectator_id] = {
                    "socket": client_sock,
                    "addr": client_addr,
                    "user_id": user_id
                }

            # Send WELCOME (spectator mode)
            welcome_msg = {
                "type": "WELCOME",
                "role": "SPECTATOR",
                "seed": self.seed,
                "bagRule": "7bag",
                "gravityPlan": {
                    "mode": "fixed",
                    "dropMs": self.drop_interval
                }
            }
            send_message(client_sock, json.dumps(welcome_msg))

            logger.info(f"✅ Spectator {user_id} joined (ID: {spectator_id})")

        except Exception as e:
            logger.error(f"❌ Spectator handshake error: {e}")
            try:
                client_sock.close()
            except:
                pass

    def handle_player_handshake(self, client_sock, client_addr):
        """Handle HELLO -> WELCOME handshake"""
        try:
            # Receive HELLO
            msg_str = recv_message(client_sock)
            msg = json.loads(msg_str)

            if msg.get("type") != "HELLO":
                logger.error(f"❌ Expected HELLO, got {msg.get('type')}")
                client_sock.close()
                return

            user_id = msg.get("userId")
            room_id = msg.get("roomId")
            is_spectator = msg.get("spectator", False)

            # Validate
            if room_id != self.room_id:
                logger.error(f"❌ Wrong room ID: {room_id} != {self.room_id}")
                client_sock.close()
                return

            if is_spectator:
                logger.error(f"❌ Spectator trying to connect during player phase")
                client_sock.close()
                return

            if user_id not in self.player_ids:
                logger.error(f"❌ Unknown player: {user_id}")
                client_sock.close()
                return

            # Determine player role (P1 or P2)
            role = "P1" if user_id == self.player_ids[0] else "P2"

            # Create board for this player
            piece_gen = self.piece_gen1 if role == "P1" else self.piece_gen2
            board = TetrisBoard(piece_generator=piece_gen)

            # Store player info
            with self.lock:
                self.players[user_id] = {
                    "socket": client_sock,
                    "addr": client_addr,
                    "role": role,
                    "board": board,
                    "ready": True,
                    "last_input_seq": 0
                }

            # Send WELCOME
            welcome_msg = {
                "type": "WELCOME",
                "role": role,
                "seed": self.seed,
                "bagRule": "7bag",
                "gravityPlan": {
                    "mode": "fixed",
                    "dropMs": self.drop_interval
                }
            }
            send_message(client_sock, json.dumps(welcome_msg))

            logger.info(f"✅ Player {user_id} ({role}) ready")

        except Exception as e:
            logger.error(f"❌ Handshake error: {e}")
            try:
                client_sock.close()
            except:
                pass

    def start_game(self):
        """Start the game loop"""
        self.game_started = True

        # Start input handler threads for each player
        for user_id, player_info in self.players.items():
            thread = threading.Thread(
                target=self.handle_player_input,
                args=(user_id,),
                daemon=True
            )
            thread.start()

        # Start gravity thread
        gravity_thread = threading.Thread(target=self.gravity_loop, daemon=True)
        gravity_thread.start()

        # Start snapshot broadcast thread
        snapshot_thread = threading.Thread(target=self.snapshot_loop, daemon=True)
        snapshot_thread.start()

        # Wait for game to end
        while self.running and not self.game_over:
            time.sleep(0.1)
            self.check_game_over()

        # Game ended
        if self.game_over:
            self.handle_game_over()

    def handle_player_input(self, user_id):
        """Handle input from a player"""
        player_info = self.players[user_id]
        sock = player_info["socket"]
        board = player_info["board"]

        logger.info(f"🎮 Starting input handler for player {user_id}")

        try:
            sock.settimeout(1.0)

            while self.running and not self.game_over:
                try:
                    msg_str = recv_message(sock)
                    if not msg_str:
                        logger.warning(f"⚠️ Empty message from {user_id}")
                        continue

                    msg = json.loads(msg_str)

                    if msg.get("type") == "INPUT":
                        action = msg.get("action")
                        seq = msg.get("seq", 0)

                        logger.info(f"🎮 Received INPUT from {user_id}: {action} (seq: {seq})")

                        # Process input
                        with self.lock:
                            if seq > player_info["last_input_seq"]:
                                player_info["last_input_seq"] = seq
                                logger.info(f"✅ Processing action: {action}")
                                self.process_action(board, action)
                            else:
                                logger.warning(f"⚠️ Ignoring old input seq {seq} (last: {player_info['last_input_seq']})")

                except socket.timeout:
                    continue
                except ProtocolError as e:
                    # Check if it's a timeout error (not a fatal error)
                    if "逾時" in str(e) or "timeout" in str(e).lower():
                        continue  # Treat timeout as non-fatal
                    logger.error(f"❌ ProtocolError for {user_id}: {e}")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSONDecodeError for {user_id}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Unexpected error in input loop for {user_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    break

        except Exception as e:
            logger.error(f"❌ Error handling input for {user_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            logger.info(f"🔌 Player {user_id} input handler stopped")

    def process_action(self, board, action):
        """Process player action"""
        if action == "LEFT":
            board.move_left()
        elif action == "RIGHT":
            board.move_right()
        elif action == "DOWN":
            board.move_down()
        elif action == "CW":
            board.rotate_cw()
        elif action == "CCW":
            board.rotate_ccw()
        elif action == "HARD_DROP":
            board.hard_drop()
        elif action == "HOLD":
            board.hold_current_piece()

    def gravity_loop(self):
        """Gravity loop - drop pieces periodically"""
        last_drop = time.time()

        while self.running and not self.game_over:
            now = time.time()

            if (now - last_drop) * 1000 >= self.drop_interval:
                # Apply gravity to all players
                with self.lock:
                    for player_info in self.players.values():
                        board = player_info["board"]
                        if not board.game_over:
                            board.move_down()

                last_drop = now

            time.sleep(0.01)  # 10ms tick

    def snapshot_loop(self):
        """Broadcast game state snapshots"""
        tick = 0

        while self.running and not self.game_over:
            time.sleep(0.1)  # 100ms = 10 snapshots/sec

            tick += 1

            # Create snapshots for each player (need lock for reading)
            snapshots = []
            with self.lock:
                for user_id, player_info in self.players.items():
                    snapshot = self.create_snapshot(user_id, tick)
                    snapshots.append(snapshot)

            # Broadcast snapshots (outside lock to avoid deadlock)
            for snapshot in snapshots:
                self.broadcast_to_all(snapshot)

    def create_snapshot(self, user_id, tick):
        """Create snapshot message for a player"""
        player_info = self.players[user_id]
        board = player_info["board"]

        # Get board state
        board_state = board.get_board_state()

        # Compress board (simple RLE)
        board_rle = self.compress_board(board_state)

        snapshot = {
            "type": "SNAPSHOT",
            "tick": tick,
            "userId": user_id,
            "role": player_info["role"],
            "boardRLE": board_rle,
            "active": {
                "shape": board.current_type if board.current_piece else None,
                "x": board.current_x,
                "y": board.current_y,
                "rot": board.current_rotation
            },
            "hold": board.hold_piece,
            "next": board.get_next_pieces(3),
            "score": board.score,
            "lines": board.lines_cleared,
            "level": board.level,
            "gameOver": board.game_over,
            "at": int(time.time() * 1000)
        }

        return snapshot

    def compress_board(self, board):
        """Simple RLE compression for board"""
        # Flatten board
        flat = []
        for row in board:
            flat.extend(row)

        # RLE encode
        if not flat:
            return ""

        result = []
        current = flat[0]
        count = 1

        for i in range(1, len(flat)):
            if flat[i] == current:
                count += 1
            else:
                result.append(f"{current}x{count}")
                current = flat[i]
                count = 1

        result.append(f"{current}x{count}")

        return ",".join(result)

    def broadcast_to_all(self, message, force=False):
        """Broadcast message to all players and spectators"""
        # Skip if game is over to avoid broken pipe errors (unless forced)
        if self.game_over and not force:
            return

        msg_str = json.dumps(message)

        # Send to players
        for player_info in self.players.values():
            try:
                send_message(player_info["socket"], msg_str)
            except Exception:
                # Silently ignore - player probably disconnected
                pass

        # Send to spectators
        with self.lock:
            disconnected_spectators = []
            for spec_id, spec_info in self.spectators.items():
                try:
                    send_message(spec_info["socket"], msg_str)
                except Exception:
                    # Mark for cleanup but don't log error
                    disconnected_spectators.append(spec_id)

            # Clean up disconnected spectators
            for spec_id in disconnected_spectators:
                del self.spectators[spec_id]
                logger.info(f"🔌 Spectator {spec_id} disconnected")

    def check_game_over(self):
        """Check if game is over"""
        with self.lock:
            alive_players = [
                uid for uid, info in self.players.items()
                if not info["board"].game_over
            ]

            if len(alive_players) == 0:
                # Both lost (draw)
                self.game_over = True
                self.winner = None
            elif len(alive_players) == 1:
                # One winner
                self.game_over = True
                self.winner = alive_players[0]

    def handle_game_over(self):
        """Handle game over"""
        logger.info(f"🎮 Game Over! Winner: {self.winner}")

        # Collect results
        results = {}
        for user_id, player_info in self.players.items():
            board = player_info["board"]
            # Determine player role (P1 or P2)
            role = "P1" if user_id == self.player_ids[0] else "P2"
            results[role] = {
                "user_id": user_id,
                "score": board.score,
                "lines_cleared": board.lines_cleared,
                "max_combo": 0  # Not implemented
            }

        # Send GAME_OVER message to clients
        game_over_msg = {
            "type": "GAME_OVER",
            "winner": self.winner,
            "results": [
                {
                    "userId": user_id,
                    "score": player_info["board"].score,
                    "lines": player_info["board"].lines_cleared,
                    "maxCombo": 0
                }
                for user_id, player_info in self.players.items()
            ]
        }
        # Force broadcast even though game_over is True
        self.broadcast_to_all(game_over_msg, force=True)

        # Report to Lobby Server
        self.report_game_result(results)
        logger.info(f"📊 Final results: {results}")

        # Wait a bit before shutdown
        time.sleep(2)

    def report_game_result(self, results):
        """Report game results to Lobby Server"""
        try:
            # Connect to lobby server
            lobby_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            lobby_sock.connect((self.lobby_host, self.lobby_port))

            # Determine winner role
            winner_role = None
            if self.winner:
                winner_role = "P1" if self.winner == self.player_ids[0] else "P2"

            # Send report
            report = {
                "action": "report_game_result",
                "data": {
                    "room_id": self.room_id,
                    "winner": winner_role,
                    "results": results
                }
            }
            send_message(lobby_sock, json.dumps(report))

            # Wait for response
            response_str = recv_message(lobby_sock)
            response = json.loads(response_str)

            if response.get("status") == "success":
                logger.info("✅ Game result reported to Lobby Server")
            else:
                logger.warning(f"⚠️ Lobby Server response: {response.get('message')}")

            lobby_sock.close()

        except Exception as e:
            logger.error(f"❌ Failed to report game result: {e}")

    def shutdown(self):
        """Shutdown server"""
        logger.info("🛑 Shutting down Game Server...")
        self.running = False

        # Close all player sockets
        with self.lock:
            for player_info in self.players.values():
                try:
                    player_info["socket"].close()
                except:
                    pass

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        logger.info("✅ Game Server shut down")


def main():
    parser = argparse.ArgumentParser(description="Tetris Game Server")
    parser.add_argument("--port", type=int, required=True, help="Server port")
    parser.add_argument("--room-id", type=int, required=True, help="Room ID")
    parser.add_argument("--player1", type=int, required=True, help="Player 1 ID")
    parser.add_argument("--player2", type=int, required=True, help="Player 2 ID")
    parser.add_argument("--drop-interval", type=int, default=500, help="Drop interval in ms")

    args = parser.parse_args()

    server = GameServer(
        port=args.port,
        room_id=args.room_id,
        player1_id=args.player1,
        player2_id=args.player2,
        drop_interval=args.drop_interval
    )

    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
