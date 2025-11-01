#!/usr/bin/env python3
"""
Manual step-by-step test
"""

from test_lobby_client import LobbyClient
import sys

print("Creating clients...")
alice = LobbyClient()
bob = LobbyClient()

print("Connecting...")
alice.connect()
bob.connect()

print("Registering...")
alice.register("ManualAlice", "manualalice@test.com", "pass")
bob.register("ManualBob", "manualbob@test.com", "pass")

print("Logging in...")
alice.login("manualalice@test.com", "pass")
bob.login("manualbob@test.com", "pass")

print(f"Alice ID: {alice.user_id}, Bob ID: {bob.user_id}")

print("Creating room...")
resp = alice.create_room("Manual Test Room", "public")
room_id = resp["data"]["id"]
print(f"Room ID: {room_id}")

print("Bob joining...")
bob.join_room(room_id)

print("Starting game...")
resp = alice.send_request("start_game", {"room_id": room_id})
print(f"Start game response: {resp}")

if resp.get("status") == "success":
    game_host = resp["data"]["game_server_host"]
    game_port = resp["data"]["game_server_port"]
    print(f"\nGame server at: {game_host}:{game_port}")
    print(f"\nTo play:")
    print(f"python3 game_client.py --host {game_host} --port {game_port} --room-id {room_id} --user-id {alice.user_id}")
    print(f"python3 game_client.py --host {game_host} --port {game_port} --room-id {room_id} --user-id {bob.user_id}")
