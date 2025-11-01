# Game Instructions - 2-Player Tetris

## Quick Start (For Players)

**Want to play right now? Follow these 3 simple steps:**

1. **Start the servers** (or ask your admin to do this):
   ```bash
   cd db_server && python3 db_server.py &
   cd ../lobby_server && python3 lobby_server.py &
   ```

2. **Both players run:**
   ```bash
   python3 play_lobby.py
   ```

3. **Follow the menu prompts:**
   - Player 1: Register → Login → Create Room → Start Game
   - Player 2: Register → Login → Join Room (enter Room ID from Player 1)
   - Both: Copy and paste the game client command when it appears

That's it! No coding required!

---

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

**🎮 EASY MODE - Use Interactive Client (Recommended)**

**Player 1 (Host):**

```bash
python3 play_lobby.py
```

Then follow these steps:
1. Choose `1` to Register (or `2` if you already have an account)
   - Enter your name (e.g., "Alice")
   - Enter your email (e.g., "alice@test.com")
   - Enter your password (e.g., "pass123")
2. Choose `2` to Login
   - Enter your email and password
3. Choose `3` to Create Room
   - Enter room name (e.g., "Game Room")
   - Choose visibility (1 for public, 2 for private)
   - **Note the Room ID** displayed - share this with Player 2!
4. Wait for Player 2 to join
5. Choose `6` to Start Game
   - Copy the game client command that appears
   - Open a new terminal and run that command

**Player 2 (Guest):**

```bash
python3 play_lobby.py
```

Then follow these steps:
1. Choose `1` to Register (or `2` if you already have an account)
   - Enter your name (e.g., "Bob")
   - Enter your email (e.g., "bob@test.com")
   - Enter your password (e.g., "pass456")
2. Choose `2` to Login
   - Enter your email and password
3. Choose `5` to Join Room
   - Enter the Room ID that Player 1 shared
4. Wait for Player 1 to start the game
5. When the game starts, copy the game client command
   - Open a new terminal and run that command

---

**💻 ADVANCED MODE - Use Python Code (For Developers)**

<details>
<summary>Click to expand Python code method</summary>

**Player 1 - Connect to Lobby:**

```bash
# In Python interactive shell
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

</details>

### Step 5: Launch Game Clients

**🎮 EASY MODE:**

When using `play_lobby.py`, the game client command is **automatically generated** for you!

After the host starts the game (Step 4, option 6), both players will see:

```
LAUNCH YOUR GAME CLIENT NOW:
python3 game_client.py --host localhost --port 10100 --room-id 1 --user-id 1
```

Simply **copy and paste** this command into a new terminal window.

---

**💻 ADVANCED MODE:**

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
