# Testing Guide - Complete System Test

## ✅ What's Been Completed

All components are now implemented and ready:

1. **DB Server** ✅ - Running on port 10001
2. **Lobby Server** ✅ - Running on port 10002
3. **Game Server** ✅ - Auto-launched by Lobby (ports 10100+)
4. **Game Client** ✅ - pygame GUI ready
5. **pygame installed** ✅

## Current Status

Your servers are **ALREADY RUNNING**:
- DB Server: `localhost:10001` ✅
- Lobby Server: `localhost:10002` ✅

## How to Test the Complete Game

### Method 1: Quick Manual Test (Recommended)

#### Step 1: Keep Servers Running
Your DB and Lobby servers are already running in the background. Keep them running!

#### Step 2: Open Python Interactive Shell (Terminal 1)

```bash
cd /Users/ninachung/Documents/GitHub/Network_programming
python3
```

```python
from test_lobby_client import LobbyClient

# Create Alice
alice = LobbyClient()
alice.connect()
alice.register("Alice", "alice@game.com", "pass123")
alice.login("alice@game.com", "pass123")

# Create room
resp = alice.create_room("Test Game", "public")
room_id = resp["data"]["id"]
print(f"Room ID: {room_id}")
print(f"Alice User ID: {alice.user_id}")
```

#### Step 3: Open Another Python Shell (Terminal 2)

```bash
cd /Users/ninachung/Documents/GitHub/Network_programming
python3
```

```python
from test_lobby_client import LobbyClient

# Create Bob
bob = LobbyClient()
bob.connect()
bob.register("Bob", "bob@game.com", "pass456")
bob.login("bob@game.com", "pass456")

# Join room (use the room_id from Alice)
bob.join_room(ROOM_ID_HERE)  # Replace with actual room_id
print(f"Bob User ID: {bob.user_id}")
```

#### Step 4: Start Game (in Alice's terminal)

```python
# In Alice's terminal
resp = alice.send_request("start_game", {"room_id": room_id})
print(resp)

# You'll see something like:
# {'status': 'success', 'data': {'game_server_host': 'localhost', 'game_server_port': 10100}}
```

#### Step 5: Launch Game Clients (Two New Terminals)

**Terminal 3 (Alice's Game Client):**
```bash
cd /Users/ninachung/Documents/GitHub/Network_programming
python3 game_client.py --host localhost --port 10100 --room-id ROOM_ID --user-id ALICE_USER_ID
```

**Terminal 4 (Bob's Game Client):**
```bash
cd /Users/ninachung/Documents/GitHub/Network_programming
python3 game_client.py --host localhost --port 10100 --room-id ROOM_ID --user-id BOB_USER_ID
```

Replace:
- `ROOM_ID` with the actual room ID
- `ALICE_USER_ID` with Alice's user ID
- `BOB_USER_ID` with Bob's user ID
- `10100` with the actual game server port if different

#### Step 6: Play!

**Game Controls:**
- **← →** : Move left/right
- **↓** : Soft drop
- **↑** : Rotate clockwise
- **Z** : Rotate counter-clockwise
- **SPACE** : Hard drop (instant drop)
- **C** : Hold piece

You should see:
- Your own board (large, center)
- Opponent's board (small, right side)
- Scores, lines, levels
- Hold piece and next 3 pieces

---

### Method 2: Script-Based Test

I've created `test_game_setup.py` which automates the lobby setup, but you'll still need to manually launch the game clients.

```bash
python3 test_game_setup.py
```

This will output the exact commands to run for both game clients.

---

## Verification Checklist

Test these features:

### Lobby Features
- [  ] Register new users
- [  ] Login with correct credentials
- [  ] Create public/private rooms
- [  ] Join rooms
- [  ] Leave rooms
- [  ] Start game (2 players required)
- [  ] View online users list
- [  ] View room list

### Game Features
- [  ] Both clients connect to game server
- [  ] See your own board
- [  ] See opponent's board
- [  ] Pieces fall automatically (gravity)
- [  ] Move pieces left/right
- [  ] Rotate pieces (CW/CCW)
- [  ] Soft drop (↓)
- [  ] Hard drop (SPACE)
- [  ] Hold piece (C)
- [  ] Clear lines
- [  ] Score increases
- [  ] Level increases every 10 lines
- [  ] Game ends when someone tops out
- [  ] Winner is determined correctly

### Technical Requirements
- [  ] Length-Prefixed Framing Protocol (all TCP communication)
- [  ] All DB operations go through DB Server
- [  ] Game logic runs on server (not client)
- [  ] Clients only send input and render state
- [  ] 7-bag piece generation with seed
- [  ] Same piece sequence for both players

---

## Troubleshooting

### "Connection refused" - Lobby Server
```bash
# Check if lobby server is running
ps aux | grep lobby_server

# If not, start it:
cd /Users/ninachung/Documents/GitHub/Network_programming/lobby_server
python3 lobby_server.py
```

### "Connection refused" - DB Server
```bash
# Check if DB server is running
ps aux | grep db_server

# If not, start it:
cd /Users/ninachung/Documents/GitHub/Network_programming/db_server
python3 db_server.py
```

### Game Server Not Starting
Check lobby server logs for error messages. The game server is automatically launched when you call `start_game`.

### Game Client Won't Connect
- Make sure game server had time to start (wait 2-3 seconds after `start_game`)
- Check the port number is correct
- Both clients must connect within 30 seconds

### Pygame Window Issues
- Make sure pygame is installed: `pip3 install pygame`
- On macOS, you might need to allow the app in Security & Privacy

---

## Stopping Servers

When you're done testing:

```bash
# Find and kill servers
pkill -f db_server.py
pkill -f lobby_server.py
pkill -f game_server.py
```

---

## Next Steps

After testing works:

1. **Deploy to Course Machine**
   - Upload all code
   - Change `localhost` to course machine IP in clients
   - Run servers on course machine
   - Connect clients from your local machine

2. **Add Spectator Mode** (+10 points)
   - Allow users to watch ongoing games
   - Only receive SNAPSHOT messages
   - Can't send INPUT

3. **Write Report**
   - System architecture diagram
   - Protocol documentation (JSON format)
   - DB schema
   - Game rules and scoring
   - Test results

4. **Create Demo Video**
   - Show registration/login
   - Show room creation/joining
   - Show actual 2-player game
   - Show game over condition

---

## Files Created

```
Network_programming/
├── db_server/
│   ├── db_server.py          (already existed)
│   ├── models.py             (already existed)
│   ├── storage.py            (already existed)
│   └── protocol.py           (already existed)
├── lobby_server/
│   ├── lobby_server.py       (already existed)
│   ├── game_manager.py       (updated!)
│   ├── db_client.py          (already existed)
│   └── protocol.py           (already existed)
├── game_server/              NEW!
│   ├── game_server.py        ✨ Complete game server
│   ├── tetris_engine.py      ✨ Tetris logic
│   └── __init__.py
├── game_client.py            ✨ NEW! pygame GUI
├── test_lobby_client.py      (already existed)
├── test_db_client.py         (already existed)
├── test_game_setup.py        ✨ NEW! Helper script
├── manual_test.py            ✨ NEW! Manual test helper
├── requirements.txt          ✨ NEW!
├── GAME_INSTRUCTIONS.md      ✨ NEW!
└── TESTING_GUIDE.md          ✨ NEW! (this file)
```

Good luck with your testing! 🎮
