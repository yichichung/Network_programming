#!/usr/bin/env python3
"""
Interactive Lobby Client - Easy-to-use interface for joining game rooms
No coding required - just follow the prompts!
"""

import socket
import json
import sys
import os

# Add lobby_server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lobby_server'))
from protocol import send_message, recv_message, ProtocolError

class InteractiveLobbyClient:
    """User-friendly interactive lobby client"""

    def __init__(self, host='localhost', port=10002):
        self.host = host
        self.port = port
        self.sock = None
        self.user_id = None
        self.user_name = None
        self.current_room_id = None

    def connect(self):
        """Connect to Lobby Server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"✅ Successfully connected to Lobby Server\n")
            return True
        except Exception as e:
            print(f"❌ Cannot connect: {e}")
            print("\nMake sure the Lobby Server is running:")
            print("  cd lobby_server")
            print("  python3 lobby_server.py\n")
            return False

    def send_request(self, action, data=None):
        """Send request and receive response"""
        request = {
            "action": action,
            "data": data or {}
        }
        send_message(self.sock, json.dumps(request))
        response_str = recv_message(self.sock)
        return json.loads(response_str)

    def register_user(self):
        """Register a new user"""
        print("\n" + "="*60)
        print("REGISTER NEW ACCOUNT")
        print("="*60)

        name = input("Enter your name: ").strip()
        if not name:
            print("❌ Name cannot be empty")
            return False

        email = input("Enter your email: ").strip()
        if not email:
            print("❌ Email cannot be empty")
            return False

        password = input("Enter your password: ").strip()
        if not password:
            print("❌ Password cannot be empty")
            return False

        try:
            response = self.send_request("register", {
                "name": name,
                "email": email,
                "password": password
            })

            if response.get("status") == "success":
                print(f"\n✅ Registration successful! Welcome, {name}!")
                return True
            else:
                print(f"\n❌ Registration failed: {response.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error during registration: {e}")
            return False

    def login_user(self):
        """Login existing user"""
        print("\n" + "="*60)
        print("LOGIN")
        print("="*60)

        email = input("Enter your email: ").strip()
        if not email:
            print("❌ Email cannot be empty")
            return False

        password = input("Enter your password: ").strip()
        if not password:
            print("❌ Password cannot be empty")
            return False

        try:
            response = self.send_request("login", {
                "email": email,
                "password": password
            })

            if response.get("status") == "success":
                self.user_id = response["data"]["user_id"]
                self.user_name = response["data"]["name"]
                print(f"\n✅ Login successful! Welcome back, {self.user_name}!")
                print(f"Your User ID: {self.user_id}")
                return True
            else:
                print(f"\n❌ Login failed: {response.get('message', 'Invalid credentials')}")
                return False
        except Exception as e:
            print(f"❌ Error during login: {e}")
            return False

    def create_room(self):
        """Create a new game room"""
        print("\n" + "="*60)
        print("CREATE NEW ROOM")
        print("="*60)

        room_name = input("Enter room name: ").strip()
        if not room_name:
            print("❌ Room name cannot be empty")
            return None

        print("\nRoom visibility:")
        print("  1. Public (anyone can join)")
        print("  2. Private (invitation only)")
        visibility_choice = input("Choose (1 or 2, default=1): ").strip()

        visibility = "private" if visibility_choice == "2" else "public"

        try:
            response = self.send_request("create_room", {
                "name": room_name,
                "visibility": visibility
            })

            if response.get("status") == "success":
                room_id = response["data"]["id"]
                self.current_room_id = room_id
                print(f"\n✅ Room created successfully!")
                print(f"Room ID: {room_id}")
                print(f"Room Name: {room_name}")
                print(f"Visibility: {visibility}")
                print("\n📋 Share this Room ID with your friend: " + str(room_id))
                return room_id
            else:
                print(f"\n❌ Failed to create room: {response.get('message', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"❌ Error creating room: {e}")
            return None

    def list_rooms(self):
        """List all public rooms"""
        print("\n" + "="*60)
        print("PUBLIC ROOMS")
        print("="*60)

        try:
            response = self.send_request("list_rooms")

            if response.get("status") == "success":
                rooms = response["data"]
                if not rooms:
                    print("No public rooms available.")
                    return

                print(f"\nFound {len(rooms)} room(s):\n")
                for room in rooms:
                    print(f"  Room ID: {room['id']}")
                    print(f"  Name: {room['name']}")
                    print(f"  Host: {room['host_name']}")
                    print(f"  Players: {room['current_players']}/{room['max_players']}")
                    print(f"  Status: {room['status']}")
                    print("-" * 40)
            else:
                print(f"❌ Failed to list rooms: {response.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error listing rooms: {e}")

    def join_room(self):
        """Join an existing room"""
        print("\n" + "="*60)
        print("JOIN ROOM")
        print("="*60)

        room_id = input("Enter Room ID to join: ").strip()
        if not room_id:
            print("❌ Room ID cannot be empty")
            return False

        try:
            room_id = int(room_id)
        except ValueError:
            print("❌ Room ID must be a number")
            return False

        try:
            response = self.send_request("join_room", {
                "room_id": room_id
            })

            if response.get("status") == "success":
                self.current_room_id = room_id
                print(f"\n✅ Successfully joined room {room_id}!")
                print("Waiting for the host to start the game...")
                return True
            else:
                print(f"\n❌ Failed to join room: {response.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error joining room: {e}")
            return False

    def start_game(self):
        """Start the game (host only)"""
        if not self.current_room_id:
            print("\n❌ You must be in a room to start the game!")
            return None

        print("\n" + "="*60)
        print("STARTING GAME...")
        print("="*60)

        try:
            response = self.send_request("start_game", {
                "room_id": self.current_room_id
            })

            if response.get("status") == "success":
                game_info = response["data"]
                print("\n✅ Game starting!")
                print(f"\nGame Server Info:")
                print(f"  Host: {game_info['host']}")
                print(f"  Port: {game_info['port']}")
                print(f"  Room ID: {self.current_room_id}")
                print(f"  Your User ID: {self.user_id}")

                print("\n" + "="*60)
                print("LAUNCH YOUR GAME CLIENT NOW:")
                print("="*60)
                print(f"\npython3 game_client.py --host {game_info['host']} --port {game_info['port']} --room-id {self.current_room_id} --user-id {self.user_id}\n")

                return game_info
            else:
                print(f"\n❌ Failed to start game: {response.get('message', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"❌ Error starting game: {e}")
            return None

    def list_online_users(self):
        """List all online users"""
        print("\n" + "="*60)
        print("ONLINE USERS")
        print("="*60)

        try:
            response = self.send_request("list_online_users")

            if response.get("status") == "success":
                users = response["data"]
                if not users:
                    print("No users online.")
                    return

                print(f"\nFound {len(users)} user(s) online:\n")
                for user in users:
                    print(f"  {user['name']} (ID: {user['id']})")
            else:
                print(f"❌ Failed to list users: {response.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error listing users: {e}")

    def close(self):
        """Close connection"""
        if self.sock:
            try:
                self.send_request("logout")
            except:
                pass
            self.sock.close()


def print_menu():
    """Print main menu"""
    print("\n" + "="*60)
    print("LOBBY MENU")
    print("="*60)
    print("1. Register new account")
    print("2. Login")
    print("3. Create room")
    print("4. List public rooms")
    print("5. Join room")
    print("6. Start game (host only)")
    print("7. List online users")
    print("8. Exit")
    print("="*60)


def main():
    """Main interactive loop"""
    print("="*60)
    print("WELCOME TO TETRIS LOBBY")
    print("="*60)
    print()

    client = InteractiveLobbyClient()

    if not client.connect():
        return

    logged_in = False

    try:
        while True:
            print_menu()
            choice = input("\nEnter your choice (1-8): ").strip()

            if choice == "1":
                client.register_user()

            elif choice == "2":
                if client.login_user():
                    logged_in = True

            elif choice == "3":
                if not logged_in:
                    print("\n❌ You must login first!")
                else:
                    client.create_room()

            elif choice == "4":
                client.list_rooms()

            elif choice == "5":
                if not logged_in:
                    print("\n❌ You must login first!")
                else:
                    client.join_room()

            elif choice == "6":
                if not logged_in:
                    print("\n❌ You must login first!")
                else:
                    client.start_game()

            elif choice == "7":
                if not logged_in:
                    print("\n❌ You must login first!")
                else:
                    client.list_online_users()

            elif choice == "8":
                print("\n👋 Goodbye!")
                break

            else:
                print("\n❌ Invalid choice. Please enter 1-8.")

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()
        print("🔌 Connection closed.\n")


if __name__ == "__main__":
    main()
