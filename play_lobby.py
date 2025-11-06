#!/usr/bin/env python3
"""
Interactive Lobby Client - Easy-to-use interface for joining game rooms
No coding required - just follow the prompts!
"""

import socket
import json
import sys
import os
import threading

# Add lobby_server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lobby_server'))
from protocol import send_message, recv_message, ProtocolError
class InteractiveLobbyClient:
    def __init__(self, host='localhost', port=10002):
        self.host = host
        self.port = port
        self.sock = None
        self.user_id = None
        self.user_name = None
        self.current_room_id = None

        # 用於 background recv 與同步 request 回應
        from queue import Queue, Empty  # 在 class 內匯入以避免外部依賴問題
        self._Queue = Queue
        self._Empty = Empty

        self._response_queue = self._Queue()
        self._recv_thread = None
        self._recv_running = False

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            # 啟動 background recv thread（收到通知會即時印出）
            self._start_recv_thread()
            print(f"✅ 成功連線到 Lobby Server\n")
            return True
        except Exception as e:
            print(f"❌ 無法連線: {e}\n")
            return False

    def _start_recv_thread(self):
        if self._recv_thread and self._recv_thread.is_alive():
            return
        self._recv_running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def _stop_recv_thread(self):
        # 停止接收 loop；實際上會在 close 時關 socket 讓 recv_message 拋例外離開
        self._recv_running = False

    def _recv_loop(self):
        """背景持續接收：通知直接處理、回應放到 response_queue"""
        while self._recv_running:
            try:
                # blocking recv (不設 timeout)，交由 recv_message 處理 frame
                msg = recv_message(self.sock)
                if not msg:
                    # 若收到空則略過
                    continue
                try:
                    response = json.loads(msg)
                except Exception:
                    # 非 JSON 或解析錯誤時略過
                    continue

                # 通知（server push）
                if response.get("type"):
                    try:
                        self._handle_notification(response)
                    except Exception:
                        # 保險起見不要讓通知 handler 崩潰整個 recv loop
                        pass
                    continue

                # 同步回應 → 放到 response queue，供 send_request 取
                try:
                    self._response_queue.put(response)
                except Exception:
                    # 若放 queue 失敗，忽略
                    pass

            except Exception as e:
                # 常見情況：socket 被關閉或網路錯誤
                # 若是因為我們主動停止，結束 loop
                if not self._recv_running:
                    break
                # 否則短暫休息後重試（避免 busy loop）
                import time
                time.sleep(0.1)
                continue

    def send_request(self, action, data=None, timeout=10.0):
        """
        送出請求，並從 background recv 放入的 response_queue 等待回應。
        timeout: 等待伺服器回應最大秒數（預設 10 秒）
        """
        request = {"action": action, "data": data or {}}
        # 送出請求（此函式仍為同步，等待回應）
        send_message(self.sock, json.dumps(request))

        # 等待 background thread 把回應放進 queue
        try:
            resp = self._response_queue.get(timeout=timeout)
            return resp
        except Exception as e:
            # 若超時或其他，擲出 TimeoutError 讓呼叫端處理
            raise TimeoutError("等待伺服器回應逾時") from e

    def _handle_notification(self, notif):
        t = notif.get("type")
        if t == "game_start":
            print("\n" + "="*60)
            print("🎮 遊戲開始！")
            print("="*60)
            print(f"請在新終端機執行：")
            print(f"python3 game_client.py --host {notif.get('game_server_host','localhost')} --port {notif.get('game_server_port')} --room-id {notif.get('room_id')} --user-id {self.user_id}")
            print("="*60 + "\n")
        elif t == "room_update":
            action = notif.get("action")
            uid = notif.get("user_id")
            if action == "user_joined":
                print(f"\n📢 玩家 {uid} 加入了房間\n")
            elif action == "user_left":
                print(f"\n📢 玩家 {uid} 離開了房間\n")
        elif t == "invitation":
            # 如果你也要顯示邀請通知可以在這裡處理
            from_user = notif.get("from_user_name") or notif.get("from_user_id")
            room_name = notif.get("room_name")
            print(f"\n✉️ 收到邀請：{from_user} 邀請你加入房間 {room_name}\n")
        else:
            # 其他通知類型
            pass

    def register_user(self):
        print("\n" + "="*60)
        print("註冊")
        print("="*60)
        name = input("姓名: ").strip()
        email = input("Email: ").strip()
        password = input("密碼: ").strip()
        if not name or not email or not password:
            print("❌ 欄位不可空白")
            return False

        try:
            resp = self.send_request("register", {"name": name, "email": email, "password": password})
            if resp.get("status") == "success":
                print(f"\n✅ 註冊成功！")
                return True
            else:
                print(f"\n❌ 註冊失敗: {resp.get('message')}")
                return False
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            return False

    def login_user(self):
        print("\n" + "="*60)
        print("登入")
        print("="*60)
        email = input("Email: ").strip()
        password = input("密碼: ").strip()
        if not email or not password:
            print("❌ 欄位不可空白")
            return False

        try:
            resp = self.send_request("login", {"email": email, "password": password})
            if resp.get("status") == "success":
                self.user_id = resp["data"]["user_id"]
                self.user_name = resp["data"]["name"]
                print(f"\n✅ 登入成功！歡迎 {self.user_name}！")
                print(f"你的 User ID: {self.user_id}\n")
                return True
            else:
                print(f"\n❌ 登入失敗: {resp.get('message')}")
                return False
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            return False

    def create_room(self):
        print("\n" + "="*60)
        print("建立房間")
        print("="*60)
        room_name = input("房間名稱: ").strip()
        if not room_name:
            print("❌ 房間名稱不可空白")
            return None

        print("\n房間類型:")
        print("  1. 公開")
        print("  2. 私人")
        choice = input("選擇 (1 or 2, 預設=1): ").strip()
        visibility = "private" if choice == "2" else "public"

        try:
            resp = self.send_request("create_room", {"name": room_name, "visibility": visibility})
            if resp.get("status") == "success":
                room_id = resp["data"]["id"]
                self.current_room_id = room_id
                print(f"\n✅ 房間建立成功！")
                print(f"房間 ID: {room_id}")
                print(f"房間名稱: {room_name}")
                print(f"類型: {visibility}")
                print(f"\n📋 請將此 Room ID 分享給朋友: {room_id}\n")
                return room_id
            else:
                print(f"\n❌ 建立房間失敗: {resp.get('message')}")
                return None
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            return None

    def join_room(self):
        print("\n" + "="*60)
        print("加入房間")
        print("="*60)
        room_id = input("房間 ID: ").strip()
        if not room_id:
            print("❌ 房間 ID 不可空白")
            return False

        try:
            room_id = int(room_id)
        except ValueError:
            print("❌ 房間 ID 必須是數字")
            return False

        try:
            resp = self.send_request("join_room", {"room_id": room_id})
            if resp.get("status") == "success":
                self.current_room_id = room_id
                print(f"\n✅ 成功加入房間 {room_id}！")
                print("等待房主開始遊戲...\n")
                return True
            else:
                print(f"\n❌ 加入房間失敗: {resp.get('message')}")
                return False
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            return False

    def start_game(self):
        if not self.current_room_id:
            print("\n❌ 你必須先在房間中！")
            return None

        print("\n" + "="*60)
        print("啟動遊戲")
        print("="*60)

        try:
            resp = self.send_request("start_game", {"room_id": self.current_room_id})
            if resp.get("status") == "success":
                game_info = resp["data"]
                print("\n✅ 遊戲伺服器啟動成功！")
                print(f"\n請在新終端機執行：")
                print("="*60)
                print(f"python3 game_client.py --host {game_info.get('game_server_host','localhost')} --port {game_info.get('game_server_port')} --room-id {self.current_room_id} --user-id {self.user_id}")
                print("="*60 + "\n")
                return game_info
            else:
                print(f"\n❌ 啟動遊戲失敗: {resp.get('message')}")
                return None
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            return None

    def list_online_users(self):
        print("\n" + "="*60)
        print("線上使用者")
        print("="*60)
        try:
            resp = self.send_request("list_online_users")
            if resp.get("status") == "success":
                users = resp["data"]
                if not users:
                    print("沒有其他使用者在線上")
                else:
                    print(f"\n共 {len(users)} 位使用者在線上:\n")
                    for user in users:
                        print(f"  {user['name']} (ID: {user['user_id']})")
                print()
            else:
                print(f"❌ 取得列表失敗: {resp.get('message')}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    def list_rooms(self):
        print("\n" + "="*60)
        print("公開房間列表")
        print("="*60)
        try:
            resp = self.send_request("list_rooms")
            if resp.get("status") == "success":
                rooms = resp["data"]
                if not rooms:
                    print("目前沒有公開房間")
                else:
                    print(f"\n共 {len(rooms)} 個公開房間:\n")
                    for room in rooms:
                        print(f"  房間 ID: {room['id']}")
                        print(f"  名稱: {room['name']}")
                        print(f"  狀態: {room['status']}")
                        print(f"  目前人數: {room.get('current_members', 0)}/2")
                        print()
                print()
            else:
                print(f"❌ 取得房間列表失敗: {resp.get('message')}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    def close(self):
        # 先嘗試優雅登出（如果你想避免在 close 時把緩衝區通知印出，可註解掉 logout）
        if self.sock:
            try:
                # 保持原本行為：嘗試 logout（send_request 會等待 background thread 的回應）
                try:
                    self.send_request("logout", timeout=5.0)
                except Exception:
                    # 忽略登出失敗
                    pass
            except Exception:
                pass

            # 停 background thread 並關 socket
            try:
                self._stop_recv_thread()
            except Exception:
                pass

            try:
                self.sock.close()
            except Exception:
                pass


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
