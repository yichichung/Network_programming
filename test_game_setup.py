#!/usr/bin/env python3
"""
Test script to setup a game and verify it works
"""

import sys
import time
from test_lobby_client import LobbyClient

def main():
    print("=" * 60)
    print("🎮 Testing Game Setup")
    print("=" * 60)
    print()

    # Create two clients
    alice = LobbyClient()
    bob = LobbyClient()

    try:
        # Connect
        print("📡 Connecting to Lobby Server...")
        if not alice.connect():
            print("❌ Alice: Failed to connect")
            return False
        if not bob.connect():
            print("❌ Bob: Failed to connect")
            return False
        print("✅ Both clients connected")

        # Register (may fail if already exists, that's ok)
        print("\n📝 Registering users...")
        alice.register("TestAlice", "testalice@test.com", "testpass")
        bob.register("TestBob", "testbob@test.com", "testpass")

        # Login
        print("\n🔐 Logging in...")
        if not alice.login("testalice@test.com", "testpass"):
            print("❌ Alice login failed")
            return False
        if not bob.login("testbob@test.com", "testpass"):
            print("❌ Bob login failed")
            return False

        print(f"✅ Alice ID: {alice.user_id}")
        print(f"✅ Bob ID: {bob.user_id}")

        # Create room
        print("\n🏠 Creating game room...")
        response = alice.create_room("Test Game", "public")
        if response.get("status") != "success":
            print(f"❌ Failed to create room: {response.get('message')}")
            return False

        room_id = response["data"]["id"]
        print(f"✅ Room created: ID {room_id}")

        # Bob joins
        print("\n🚪 Bob joining room...")
        response = bob.join_room(room_id)
        if response.get("status") != "success":
            print(f"❌ Failed to join room: {response.get('message')}")
            return False
        print("✅ Bob joined")

        # Start game
        print("\n🎮 Starting game...")
        response = alice.send_request("start_game", {"room_id": room_id})
        if response.get("status") != "success":
            print(f"❌ Failed to start game: {response.get('message')}")
            return False

        game_host = response["data"]["game_server_host"]
        game_port = response["data"]["game_server_port"]

        print(f"✅ Game Server started: {game_host}:{game_port}")

        # Wait a bit for game server to fully initialize
        print("\n⏳ Waiting for Game Server to initialize...")
        time.sleep(3)

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("To play the game, run these commands in 2 separate terminals:")
        print()
        print(f"Terminal 1 (Alice):")
        print(f"  python3 game_client.py --host {game_host} --port {game_port} --room-id {room_id} --user-id {alice.user_id}")
        print()
        print(f"Terminal 2 (Bob):")
        print(f"  python3 game_client.py --host {game_host} --port {game_port} --room-id {room_id} --user-id {bob.user_id}")
        print()

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        alice.close()
        bob.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
