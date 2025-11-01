# Game Instructions - 2-Player Tetris

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

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Python 3.7+** required

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

### Step 3: Test Lobby (Optional)

You can test the lobby with the test client:

```bash
python3 test_lobby_client.py
```

### Step 4: Two Players Join and Start Game

**Player 1 - Connect to Lobby:**

```bash
# In Python interactive shell or create a simple lobby client
python3
>>> from test_lobby_client import LobbyClient
>>> alice = LobbyClient()
>>> alice.connect()
>>> alice.register("Alice", "alice@test.com", "pass123")
>>> alice.login("alice@test.com", "pass123")
>>> response = alice.create_room("Game Room", "public")
>>> room_id = response["data"]["id"]
>>> print(f"Room ID: {room_id}")
```

**Player 2 - Connect to Lobby:**

```bash
# In another Python shell
python3
>>> from test_lobby_client import LobbyClient
>>> bob = LobbyClient()
>>> bob.connect()
>>> bob.register("Bob", "bob@test.com", "pass456")
>>> bob.login("bob@test.com", "pass456")
>>> bob.join_room(room_id)  # Use room_id from Player 1
```

**Player 1 - Start Game:**

```python
>>> alice.send_request("start_game", {"room_id": room_id})
```

This will return game server connection info (host and port).

### Step 5: Launch Game Clients

The lobby will automatically start a Game Server. Players need to launch their game clients.

**Player 1 - Launch Game Client:**

```bash
python3 game_client.py --host localhost --port <game_port> --room-id <room_id> --user-id <alice_user_id>
```

**Player 2 - Launch Game Client:**

```bash
python3 game_client.py --host localhost --port <game_port> --room-id <room_id> --user-id <bob_user_id>
```

Replace:
- `<game_port>` with the port returned from start_game (e.g., 10100)
- `<room_id>` with the actual room ID
- `<alice_user_id>` and `<bob_user_id>` with actual user IDs from login

## Game Controls

- **← →** : Move left/right
- **↓** : Soft drop (move down faster)
- **↑** : Rotate clockwise
- **Z** : Rotate counter-clockwise
- **SPACE** : Hard drop (instant drop)
- **C** : Hold piece

## Game Rules

1. **2 Players** compete simultaneously
2. **10×20 board** per player
3. **7-bag piece generation** with shared seed (same piece sequence for both)
4. **No attack mechanics** - players compete independently
5. **Win condition**: Survive longer than opponent
6. **Scoring**:
   - 1 line = 100 points
   - 2 lines = 300 points
   - 3 lines = 500 points
   - 4 lines = 800 points
7. **Level**: Increases every 10 lines cleared

## Features Implemented

✅ Length-Prefixed Framing Protocol (TCP)
✅ DB Server (User, Room, GameLog storage)
✅ Lobby Server (registration, login, rooms, invitations)
✅ Game Server (Tetris logic, server authority)
✅ Game Client (pygame GUI with opponent board view)
✅ 7-bag piece generation with seeded randomization
✅ State synchronization (INPUT + SNAPSHOT messages)
✅ Game over detection and result reporting

## Troubleshooting

### "Connection refused" errors
- Make sure DB Server is running first
- Make sure Lobby Server is running before connecting clients
- Check that ports 10001 and 10002 are not in use

### "No module named pygame"
```bash
pip install pygame
```

### Game Server not starting
- Check that the game_server.py file exists in `game_server/` directory
- Check that port 10100+ is available
- Look at Lobby Server logs for error messages

### Clients can't connect to Game Server
- Make sure both clients connect within 30 seconds
- Check that the game_server port is correct
- Verify room_id and user_id match

## Architecture Notes

- **Server Authority**: All game logic runs on Game Server
- **Client Rendering**: Clients only display state, don't compute logic
- **Protocol**: TCP with 4-byte length prefix + JSON body
- **Synchronization**: Server broadcasts snapshots 10 times/second
- **Gravity**: Fixed 500ms drop interval (configurable)

## Next Steps / Future Improvements

- [ ] Implement attack mechanics (garbage lines)
- [ ] Add spectator mode
- [ ] Save game logs to DB after match ends
- [ ] Add variable gravity (increases with level)
- [ ] Add sound effects and music
- [ ] Implement ghost piece (preview of drop location)
- [ ] Add pause/resume functionality
- [ ] Create a proper lobby GUI (currently CLI-based)
