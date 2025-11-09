# Network Programming - 2-Player Tetris

A multiplayer Tetris game built with Python using TCP socket programming, demonstrating client-server architecture, database integration, and real-time game synchronization.

## Project Overview

This project implements a complete multiplayer gaming system with three main components:

1. **DB Server** - Manages user accounts, rooms, and game logs
2. **Lobby Server** - Handles user authentication, room management, and game session coordination
3. **Game Server** - Runs the actual Tetris game with server-authoritative logic

Players can register accounts, create or join game rooms, and compete in real-time 2-player Tetris matches.

## System Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  DB Server  │◄────────┤ Lobby Server │────────►│ Game Server │
│   (10001)   │         │   (10002)    │         │  (10100+)   │
└─────────────┘         └──────────────┘         └─────────────┘
                              ▲                         ▲
                              │                         │
                        ┌─────┴─────┐           ┌───────┴───────┐
                        │           │           │               │
                   ┌────┴────┐ ┌────┴────┐ ┌────┴────┐   ┌────┴────┐
                   │Client 1 │ │Client 2 │ │Client 1 │   │Client 2 │
                   │ (Lobby) │ │ (Lobby) │ │ (Game)  │   │ (Game)  │
                   └─────────┘ └─────────┘ └─────────┘   └─────────┘
```

## Quick Start

### For Players (Easy Mode)

1. **Start the servers**:

   ```bash
   cd db_server && python3 db_server.py &
   cd ../lobby_server && python3 lobby_server.py &
   ```

2. **Both players run the interactive lobby client**:

   ```bash
   python3 play_lobby.py
   ```

3. **Follow the menu prompts**:
   - **Player 1 (Host)**: Register → Login → Create Room → Start Game
   - **Player 2 (Guest)**: Register → Login → Join Room (enter Room ID)
   - **Both players**: Copy and paste the game client command when it appears

No coding required!

### For Developers (Advanced Mode)

See [GAME_INSTRUCTIONS.md](GAME_INSTRUCTIONS.md) for detailed setup instructions.

## Features

### Implemented

- **Length-Prefixed Framing Protocol** - Custom TCP protocol with 4-byte length prefix + JSON body
- **Database Server** - SQLite-based storage for users, rooms, and game logs
- **Lobby Server**:
  - User registration and authentication
  - Room creation and management (public/private)
  - Online user listing
  - Game session coordination
- **Game Server**:
  - Server-authoritative Tetris logic
  - 7-bag piece generation with seeded randomization
  - Real-time state synchronization (10 snapshots/second)
  - Input validation and processing
- **Game Client**:
  - Pygame-based GUI
  - Split-screen view (your board + opponent's board)
  - Smooth rendering and controls
  - Game over detection

### Game Rules

- **2 Players** compete simultaneously
- **10×20 board** per player
- **7-bag piece generation** - same piece sequence for both players
- **No attack mechanics** - pure survival competition
- **Scoring**:
  - 1 line = 100 points
  - 2 lines = 300 points
  - 3 lines = 500 points
  - 4 lines (Tetris) = 800 points
- **Level**: Increases every 10 lines cleared

### Game Controls

- **← →** : Move left/right
- **↓** : Soft drop (move down faster)
- **↑** : Rotate clockwise
- **Z** : Rotate counter-clockwise
- **SPACE** : Hard drop (instant drop)
- **C** : Hold piece

## Prerequisites

- **Python 3.7+**
- **Dependencies**:
  ```bash
  pip install -r requirements.txt
  ```

Main dependencies:

- `pygame` - For game client GUI
- `sqlite3` - For database (included in Python standard library)

## Project Structure

```
Network_programming/
├── db_server/
│   ├── db_server.py       # Database server
│   ├── models.py          # Data models
│   ├── storage.py         # SQLite storage layer
│   └── protocol.py        # Protocol utilities
├── lobby_server/
│   ├── lobby_server.py    # Lobby server
│   ├── db_client.py       # DB server client
│   ├── game_manager.py    # Game server management
│   └── protocol.py        # Protocol utilities
├── game_server/
│   ├── game_server.py     # Game server
│   └── tetris_engine.py   # Tetris game logic
├── game_client.py         # Game client GUI
├── play_lobby.py          # Interactive lobby client (Easy Mode)
├── test_lobby_client.py   # Test client library
├── GAME_INSTRUCTIONS.md   # Detailed instructions
└── README.md              # This file
```

## How to Run

### Step 1: Start DB Server

```bash
cd db_server
python3 db_server.py
```

The DB server will start on **port 10001**.

### Step 2: Start Lobby Server

In a new terminal:

```bash
cd lobby_server
python3 lobby_server.py
```

The lobby server will start on **port 10002**.

### Step 3: Players Join Lobby

**Easy way** - Use the interactive client:

```bash
python3 play_lobby.py
```

**Advanced way** - Use Python interactive shell (see [GAME_INSTRUCTIONS.md](GAME_INSTRUCTIONS.md))

### Step 4: Launch Game Clients

After the host starts the game, both players will receive a command to copy and paste:

```bash
python3 game_client.py --host localhost --port 10100 --room-id 1 --user-id 1
```

## Network Protocol

### TCP with Length-Prefixed Framing

All messages follow this format:

```
[4 bytes: message length (big-endian)] + [JSON message body]
```

### Message Format

```json
{
  "action": "action_name",
  "data": {
    "key": "value"
  }
}
```

### Response Format

```json
{
  "status": "success" | "error",
  "message": "Human-readable message",
  "data": {}
}
```

## Technical Highlights

### Server Authority

All game logic runs on the Game Server - clients only send inputs and render states. This prevents cheating and ensures synchronization.

### State Synchronization

- Clients send **INPUT** messages (key presses)
- Server processes inputs and updates game state
- Server broadcasts **SNAPSHOT** messages (10 times/second) with complete game state
- Clients render the received state

### Concurrent Connections

- DB Server handles multiple Lobby Server connections
- Lobby Server handles multiple client connections
- Each game gets its own dedicated Game Server instance

### Error Handling

- Connection timeouts
- Malformed message detection
- Invalid action handling
- Graceful disconnection handling

## Troubleshooting

### "Connection refused" errors

Make sure the servers are running in the correct order:

1. DB Server first
2. Lobby Server second
3. Then clients can connect

### "No module named pygame"

```bash
pip install pygame
```

### Port already in use

Check if another instance is running:

```bash
lsof -i :10001  # DB Server
lsof -i :10002  # Lobby Server
lsof -i :10100  # Game Server
```

### Game Server not starting

- Check that `game_server.py` exists in `game_server/` directory
- Check Lobby Server logs for error messages
- Ensure port 10100+ is available

## Future Improvements

- [ ] Implement attack mechanics (garbage lines)
- [ ] Add spectator mode
- [ ] Save game replays to database
- [ ] Variable gravity (increases with level)
- [ ] Sound effects and music
- [ ] Ghost piece preview
- [ ] Pause/resume functionality
- [ ] Web-based lobby GUI
- [ ] Ranking system and leaderboards
- [ ] Tournament mode

## Course Information

**Network Programming**
Fall 2025

## License

This project is for educational purposes.

## Contributors

Built as part of the Network Programming course.
