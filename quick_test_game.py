#!/usr/bin/env python3
"""
Quick test script for the Tetris game
This automates the lobby connection and launches game clients
"""

import subprocess
import time
import sys
from test_lobby_client import LobbyClient

def test_game():
    """Quick test of the full game flow"""

    print("=" * 60)
    print("🎮 Tetris Game Quick Test")
    print("=" * 60)
    print()

    # Create two clients
    alice = LobbyClient()
    bob = LobbyClient()

    try:
        # Connect
        print("📡 Connecting to Lobby Server...")
        if not alice.connect() or not bob.connect():
            print("❌ Failed to connect to Lobby Server")
            print("   Make sure Lobby Server is running:")
            print("   cd lobby_server && python3 lobby_server.py")
            return

        # Register (may fail if already exists, that's ok)
        print("📝 Registering users...")
        alice.register("TestAlice", "testalice@test.com", "testpass")
        bob.register("TestBob", "testbob@test.com", "testpass")

        # Login
        print("🔐 Logging in...")
        if not alice.login("testalice@test.com", "testpass"):
            print("❌ Alice login failed")
            return
        if not bob.login("testbob@test.com", "testpass"):
            print("❌ Bob login failed")
            return

        print(f"✅ Alice ID: {alice.user_id}")
        print(f"✅ Bob ID: {bob.user_id}")

        # Create room
        print("\n🏠 Creating game room...")
        response = alice.create_room("Test Game", "public")
        if response.get("status") != "success":
            print(f"❌ Failed to create room: {response.get('message')}")
            return

        room_id = response["data"]["id"]
        print(f"✅ Room created: ID {room_id}")

        # Bob joins
        print("\n🚪 Bob joining room...")
        response = bob.join_room(room_id)
        if response.get("status") != "success":
            print(f"❌ Failed to join room: {response.get('message')}")
            return
        print("✅ Bob joined")

        # Start game
        print("\n🎮 Starting game...")
        response = alice.send_request("start_game", {"room_id": room_id})
        if response.get("status") != "success":
            print(f"❌ Failed to start game: {response.get('message')}")
            return

        game_host = response["data"]["game_server_host"]
        game_port = response["data"]["game_server_port"]

        print(f"✅ Game Server started: {game_host}:{game_port}")
        print()

        # Wait for game server to be ready
        print("⏳ Waiting for Game Server to initialize...")
        time.sleep(2)

        # Launch game clients
        print("\n🚀 Launching game clients...")
        print("   (Close the pygame windows to exit)")
        print()

        alice_cmd = [
            "python3", "game_client.py",
            "--host", game_host,
            "--port", str(game_port),
            "--room-id", str(room_id),
            "--user-id", str(alice.user_id)
        ]

        bob_cmd = [
            "python3", "game_client.py",
            "--host", game_host,
            "--port", str(game_port),
            "--room-id", str(room_id),
            "--user-id", str(bob.user_id)
        ]

        print(f"🎮 Player 1 (Alice): {' '.join(alice_cmd)}")
        print(f"🎮 Player 2 (Bob): {' '.join(bob_cmd)}")
        print()

        # Launch clients (they will run in foreground)
        # Note: In real testing, you'd launch these in separate terminals
        print("⚠️  Note: Launch these commands in separate terminals:")
        print()
        print("Terminal 1:")
        print(f"  {' '.join(alice_cmd)}")
        print()
        print("Terminal 2:")
        print(f"  {' '.join(bob_cmd)}")
        print()

        print("✅ Test setup complete!")
        print()
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Keep connections alive
        print("\n💡 Press Ctrl+C to cleanup and exit...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Cleaning up...")
            alice.close()
            bob.close()


if __name__ == "__main__":
    test_game()
