#!/usr/bin/env python3
# lee xiang is a xiao bengo
"""
Interactive Lobby Client - Easy-to-use interface for joining game rooms
No coding required - just follow the prompts!
"""

import socket
import json
import sys
import os
import threading
import subprocess

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

        # 用於處理 replay 請求（避免 stdin 競爭）
        self.pending_replay_request = None  # {"room_id": int}

        # 用於標記是否在等待遊戲開始（避免選單循環）
        self.waiting_for_game = False
        self.is_host = False  # Track if user is the room host

        # 用於標記是否應該退出（server shutdown）
        self._should_exit = False

        # 心跳機制
        self._heartbeat_thread = None
        self._heartbeat_running = False

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            # 啟動 background recv thread（收到通知會即時印出）
            self._start_recv_thread()
            # 暫時關閉心跳執行緒 - 需要修復
            # self._start_heartbeat_thread()
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

    def _start_heartbeat_thread(self):
        """啟動心跳執行緒，每 2 秒發送一次心跳"""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self):
        """停止心跳執行緒"""
        self._heartbeat_running = False

    def _heartbeat_loop(self):
        """背景持續發送心跳"""
        import time
        while self._heartbeat_running:
            try:
                # 每 2 秒發送一次心跳
                time.sleep(2)

                if not self._heartbeat_running:
                    break

                # 發送心跳訊息
                send_message(self.sock, json.dumps({
                    "action": "heartbeat",
                    "data": {}
                }))
            except Exception as e:
                # 如果發送失敗，可能是斷線了
                if self._heartbeat_running:
                    # 短暫休息後重試
                    time.sleep(1)

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
                # 但要過濾掉心跳回應（heartbeat 回應沒有 action 欄位）
                try:
                    # Check if this is a generic success response without data
                    # This might be a heartbeat response, so we should skip it
                    # unless it has meaningful data
                    if response.get("status") == "success" and not response.get("data") and not response.get("message"):
                        # This is likely a heartbeat response, skip it
                        continue
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
            # Clear any pending replay request from previous game
            self.pending_replay_request = None
            # Set waiting flag (don't clear - we're waiting for game to end now)
            self.waiting_for_game = True

            print("\n" + "="*60)
            print("🎮 遊戲開始！正在自動啟動遊戲...")
            print("="*60)

            # 自動啟動遊戲客戶端
            host = notif.get('game_server_host', 'localhost')
            port = notif.get('game_server_port')
            room_id = notif.get('room_id')

            self._launch_game_client(host, port, room_id)
            print("="*60 + "\n")
        elif t == "room_update":
            action = notif.get("action")
            uid = notif.get("user_id")
            if action == "user_joined":
                print(f"\n📢 玩家 {uid} 加入了房間")
                # If I'm the host, remind to press 6
                if self.current_room_id and uid != self.user_id:
                    print("💡 按 6 開始遊戲\n")
                else:
                    print()
            elif action == "user_left":
                print(f"\n📢 玩家 {uid} 離開了房間")
                # If I'm waiting for a game and someone left, return to menu
                if self.waiting_for_game and uid != self.user_id:
                    print("⚠️  其他玩家離開，返回主選單...\n")
                    self.current_room_id = None
                    self.is_host = False
                    self.waiting_for_game = False
                    # Force exit from waiting loop by printing newline
                    print()
                else:
                    print()
        elif t == "invitation":
            # 如果你也要顯示邀請通知可以在這裡處理
            from_user = notif.get("from_user_name") or notif.get("from_user_id")
            room_name = notif.get("room_name")
            print(f"\n✉️ 收到邀請：{from_user} 邀請你加入房間 {room_name}\n")
        elif t == "game_ended":
            # 遊戲結束通知
            room_id = notif.get("room_id")
            winner = notif.get("winner")
            results = notif.get("results", {})
            request_replay = notif.get("request_replay", False)

            print(f"\n[DEBUG] 收到 game_ended 通知: room_id={room_id}, winner={winner}")

            # Clear waiting flag - game ended
            self.waiting_for_game = False

            print("\n" + "="*60)
            print("🏁 遊戲結束！")
            print("="*60)

            # 顯示勝利者
            if winner:
                print(f"🏆 勝利者: Player {winner}")

            # 顯示結果統計（如果有）
            if results:
                for player, stats in results.items():
                    print(f"\n{player}:")
                    print(f"  分數: {stats.get('score', 0)}")
                    print(f"  消除行數: {stats.get('lines_cleared', 0)}")

            print("="*60)

            # 檢查是否請求 replay
            if not request_replay:
                # 不需要 replay（對手已離線或其他原因）
                # 顯示額外訊息並返回主選單
                message = notif.get("message", "")
                if message:
                    print(f"\n⚠️  {message}")
                print("\n返回主選單...\n")
                # 清除房間狀態
                self.current_room_id = None
                self.is_host = False
                self.waiting_for_game = False
                # Print a newline to interrupt any pending input() call
                print()
            else:
                # 需要 replay - 檢查是否為玩家（不是觀眾）
                # 檢查結果中是否包含當前使用者的 user_id
                is_player = False
                if self.user_id and results:
                    for role, player_stats in results.items():
                        stats_user_id = player_stats.get("user_id")
                        # Compare both as strings and as ints to handle type mismatches
                        if stats_user_id == self.user_id or str(stats_user_id) == str(self.user_id):
                            is_player = True
                            break

                if not is_player:
                    # 觀眾：顯示遊戲結束，回到選單
                    print("\n📺 觀戰結束，返回主選單...\n")
                else:
                    # 玩家：設置待處理的 replay 請求
                    # 不在背景執行緒中讀取 stdin，而是讓主執行緒處理
                    self.pending_replay_request = {"room_id": room_id}
                    # Print a newline to interrupt any pending input() call
                    print()
        elif t == "replay_accepted":
            # 所有玩家同意重玩
            message = notif.get("message", "")
            print("\n" + "="*60)
            print("✅ " + message)
            print("="*60 + "\n")
            # Set waiting flag - waiting for host to start game
            self.waiting_for_game = True
        elif t == "replay_rejected":
            # 有玩家拒絕重玩
            message = notif.get("message", "")
            print("\n" + "="*60)
            print("❌ " + message)
            print("="*60 + "\n")
            # 清除房間狀態但保持登入
            self.current_room_id = None
            self.is_host = False
            self.waiting_for_game = False
        elif t == "server_shutdown":
            # 伺服器關閉通知
            message = notif.get("message", "Server is shutting down")
            print("\n" + "="*60)
            print(f"⚠️  {message}")
            print("="*60 + "\n")
            print("按 Enter 結束...")
            # Set flag to exit main loop
            self._should_exit = True
        elif t == "player_disconnected":
            # 玩家斷線通知
            disconnected_user_id = notif.get("user_id")
            room_id = notif.get("room_id")
            message = notif.get("message", f"玩家 {disconnected_user_id} 已斷線")

            print("\n" + "="*60)
            print(f"⚠️  {message}")
            print("="*60 + "\n")

            # 如果在等待中或遊戲中，返回主選單
            if self.waiting_for_game:
                print("⚠️  返回主選單...\n")
                self.current_room_id = None
                self.is_host = False
                self.waiting_for_game = False
                # Force exit from waiting loop
                print()
        else:
            # 其他通知類型
            pass

    def _launch_game_client(self, host, port, room_id):
        """自動啟動遊戲客戶端"""
        try:
            game_client_path = os.path.join(os.path.dirname(__file__), "game_client.py")

            cmd = [
                "python3",
                game_client_path,
                "--host", host,
                "--port", str(port),
                "--room-id", str(room_id),
                "--user-id", str(self.user_id)
            ]

            print(f"🚀 啟動遊戲客戶端...")
            print(f"   Host: {host}")
            print(f"   Port: {port}")
            print(f"   Room: {room_id}")
            print(f"   User: {self.user_name} (ID: {self.user_id})")

            # 創建日誌文件來記錄遊戲客戶端輸出
            log_file = open(f"game_client_{self.user_id}.log", "w")

            # 在新進程中啟動遊戲客戶端（不等待它結束）
            subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )

            print("✅ 遊戲視窗應該已經開啟！")
            print(f"📄 遊戲日誌: game_client_{self.user_id}.log")

        except Exception as e:
            print(f"❌ 無法啟動遊戲客戶端: {e}")
            print(f"\n請手動執行：")
            print(f"python3 game_client.py --host {host} --port {port} --room-id {room_id} --user-id {self.user_id}")

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
                data = resp.get("data", {})
                self.user_id = data.get("user_id")
                self.user_name = data.get("name")
                if not self.user_id or not self.user_name:
                    print(f"\n❌ 登入失敗: 無法取得使用者資訊")
                    return False
                print(f"\n✅ 登入成功！歡迎 {self.user_name}！")
                print(f"你的 User ID: {self.user_id}\n")
                return True
            else:
                print(f"\n❌ 登入失敗: {resp.get('message')}")
                return False
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_room(self):
        print("\n" + "="*60)
        print("建立房間")
        print("="*60)
        room_name = input("房間名稱: ").strip()
        if not room_name:
            print("❌ 房間名稱不可空白")
            return None

        # All rooms are public (simplified)
        visibility = "public"

        try:
            print("[DEBUG] Sending create_room request...")
            resp = self.send_request("create_room", {"name": room_name, "visibility": visibility}, timeout=10.0)
            print(f"[DEBUG] create_room response: {resp}")  # Debug logging

            if not resp:
                print(f"\n❌ 建立房間失敗: 沒有收到回應")
                return None

            if resp.get("status") == "success":
                data = resp.get("data", {})
                print(f"[DEBUG] data: {data}")  # Debug logging
                room_id = data.get("id")
                if not room_id:
                    print(f"\n❌ 建立房間失敗: 無法取得房間 ID")
                    print(f"[DEBUG] Response was: {resp}")
                    return None
                self.current_room_id = room_id
                self.is_host = True  # Mark as host
                self.waiting_for_game = True  # Wait for players
                print(f"\n✅ 房間建立成功！")
                print(f"房間 ID: {room_id}")
                print(f"房間名稱: {room_name}")
                print(f"\n📋 請將此 Room ID 分享給朋友: {room_id}\n")
                return room_id
            else:
                print(f"\n❌ 建立房間失敗: {resp.get('message', '未知錯誤')}")
                print(f"[DEBUG] Full response: {resp}")
                return None
        except TimeoutError as e:
            print(f"❌ 請求逾時: {e}")
            return None
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            import traceback
            traceback.print_exc()
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
                self.waiting_for_game = True  # Set waiting flag
                print(f"\n✅ 成功加入房間 {room_id}！")
                print("⏳ 等待房主開始遊戲...\n")
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
                game_info = resp.get("data", {})
                print("\n✅ 遊戲伺服器啟動成功！等待通知...\n")
                return game_info
            else:
                print(f"\n❌ 啟動遊戲失敗: {resp.get('message')}")
                return None
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            import traceback
            traceback.print_exc()
            return None

    def leave_room(self):
        if not self.current_room_id:
            print("\n❌ 你不在任何房間中！")
            return False

        try:
            resp = self.send_request("leave_room", {"room_id": self.current_room_id})
            if resp.get("status") == "success":
                print(f"\n✅ {resp.get('message', '已離開房間')}")
                # Clear room state
                self.current_room_id = None
                self.is_host = False
                self.waiting_for_game = False
                return True
            else:
                print(f"\n❌ 離開房間失敗: {resp.get('message')}")
                return False
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            return False

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

    def spectate_game(self):
        """觀戰遊戲"""
        print("\n" + "="*60)
        print("觀戰遊戲")
        print("="*60)

        # 顯示正在進行中的房間
        try:
            resp = self.send_request("list_rooms")
            if resp.get("status") != "success":
                print("❌ 無法取得房間列表")
                return

            rooms = resp["data"]
            playing_rooms = [r for r in rooms if r.get("status") == "playing"]

            if not playing_rooms:
                print("\n目前沒有正在進行的遊戲")
                return

            print(f"\n共 {len(playing_rooms)} 個正在進行的遊戲:\n")
            for room in playing_rooms:
                print(f"  房間 ID: {room['id']}")
                print(f"  名稱: {room['name']}")
                print()

            room_id = input("請輸入要觀戰的房間 ID: ").strip()
            if not room_id:
                return

            try:
                room_id = int(room_id)
            except ValueError:
                print("❌ 房間 ID 必須是數字")
                return

            # 取得遊戲伺服器資訊
            resp = self.send_request("spectate_game", {"room_id": room_id})
            if resp.get("status") == "success":
                game_info = resp["data"]
                host = game_info.get("game_server_host", "localhost")
                port = game_info.get("game_server_port")

                print(f"\n🎮 連接到遊戲伺服器...")
                self._launch_spectator_client(host, port, room_id)
            else:
                print(f"\n❌ {resp.get('message', '無法觀戰此遊戲')}")

        except Exception as e:
            print(f"❌ 錯誤: {e}")

    def _launch_spectator_client(self, host, port, room_id):
        """啟動觀戰客戶端"""
        try:
            game_client_path = os.path.join(os.path.dirname(__file__), "game_client.py")

            cmd = [
                "python3",
                game_client_path,
                "--host", host,
                "--port", str(port),
                "--room-id", str(room_id),
                "--user-id", str(self.user_id),
                "--spectate"  # 觀戰模式標記
            ]

            print(f"🚀 啟動觀戰視窗...")
            print(f"   Host: {host}")
            print(f"   Port: {port}")
            print(f"   Room: {room_id}")

            log_file = open(f"spectator_{self.user_id}.log", "w")

            subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )

            print("✅ 觀戰視窗應該已經開啟！")
            print(f"📄 觀戰日誌: spectator_{self.user_id}.log\n")

        except Exception as e:
            print(f"❌ 無法啟動觀戰視窗: {e}")

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
                self._stop_heartbeat_thread()
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
    print("5. Join room (as player)")
    print("6. Start game (host only)")
    print("7. List online users")
    print("8. Spectate game (watch only)")
    print("9. Exit")
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
            # 檢查是否收到 server shutdown 通知
            if client._should_exit:
                print("正在退出...")
                break

            # 檢查是否有待處理的 replay 請求
            if client.pending_replay_request:
                room_id = client.pending_replay_request["room_id"]
                print("\n" + "="*60)
                print("⚠️  等待您的 REPLAY 回應")
                print("="*60)
                replay_choice = input("是否要重新對戰？ (y/n): ").strip().lower()

                want_replay = (replay_choice == 'y')

                # 發送回應給伺服器
                try:
                    send_message(client.sock, json.dumps({
                        "action": "replay_response",
                        "data": {
                            "room_id": room_id,
                            "replay": want_replay
                        }
                    }))
                    if want_replay:
                        print("✅ 已發送重新對戰請求，等待對手回應...\n")
                        # DON'T set waiting_for_game yet - wait for replay_accepted notification
                        # The server will send replay_accepted when BOTH players have responded
                    else:
                        print("✅ 已回絕重新對戰，返回主選單...\n")
                        # Clear room state but stay logged in
                        client.current_room_id = None
                        client.is_host = False
                        client.waiting_for_game = False
                except Exception as e:
                    print(f"❌ 發送回應失敗: {e}\n")

                # 清除待處理請求
                client.pending_replay_request = None
                continue

            # 如果正在等待遊戲開始或遊戲進行中
            if client.waiting_for_game:
                # 如果是房主，顯示簡化選單（只有開始遊戲選項）
                if client.is_host and client.current_room_id:
                    print("\n" + "="*60)
                    print("等待中 - 房主控制")
                    print("="*60)
                    print("6. 開始遊戲")
                    print("9. 離開房間")
                    print("="*60)

                    print("\n輸入選項: ", end='', flush=True)

                    # Use non-blocking polling to allow replay prompt to interrupt
                    import sys
                    import select

                    while True:
                        # Check if replay request arrived while waiting for input
                        if client.pending_replay_request:
                            print()  # New line after the prompt
                            break

                        # Check if we should exit waiting mode (someone left, etc.)
                        if not client.waiting_for_game:
                            print()  # New line after the prompt
                            choice = None
                            break

                        # Check if input is available
                        if hasattr(select, 'select'):
                            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                            if ready:
                                choice = sys.stdin.readline().strip()
                                break
                        else:
                            # Fallback for Windows
                            import time
                            time.sleep(0.1)
                            continue

                    # If we broke out due to replay request, continue to handle it
                    if client.pending_replay_request:
                        continue

                    # If we broke out due to exiting waiting mode, continue to main menu
                    if not client.waiting_for_game or choice is None:
                        continue

                    if choice == "6":
                        client.start_game()
                    elif choice == "9":
                        client.leave_room()
                    continue
                else:
                    # 非房主，只是安靜等待
                    import time
                    time.sleep(0.1)  # 短暫休息避免 busy loop
                    continue

            print_menu()

            # Use a non-blocking approach to check for pending_replay_request
            import sys
            import select

            print("\nEnter your choice (1-9): ", end='', flush=True)

            # Poll for input with timeout to allow checking for replay requests
            while True:
                # Check if replay request arrived while waiting for input
                if client.pending_replay_request:
                    print()  # New line after the prompt
                    break

                # Check if input is available (Unix-like systems)
                if hasattr(select, 'select'):
                    ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if ready:
                        choice = sys.stdin.readline().strip()
                        break
                else:
                    # For Windows or systems without select, just use input with timeout handling
                    # This is a fallback - won't be as responsive
                    try:
                        choice = input()
                        break
                    except:
                        import time
                        time.sleep(0.1)
                        continue

            # If we broke out due to replay request, continue to handle it
            if client.pending_replay_request:
                continue

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
                if not logged_in:
                    print("\n❌ You must login first!")
                else:
                    client.spectate_game()

            elif choice == "9":
                print("\n👋 Goodbye!")
                break

            else:
                print("\n❌ Invalid choice. Please enter 1-9.")

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
