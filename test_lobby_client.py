# test_lobby_client.py
import socket
import json
import sys
import os
import time

# 加入 lobby_server 到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lobby_server'))
from protocol import send_message, recv_message, ProtocolError

class LobbyClient:
    """Lobby Server 測試客戶端"""
    
    def __init__(self, host='localhost', port=10002):
        self.host = host
        self.port = port
        self.sock = None
        self.user_id = None
        self.user_name = None
    
    def connect(self):
        """連線到 Lobby Server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"✅ 成功連線到 Lobby Server ({self.host}:{self.port})\n")
            return True
        except Exception as e:
            print(f"❌ 無法連線: {e}")
            return False
    
    def send_request(self, action, data=None):
        """發送請求並接收回應"""
        request = {
            "action": action,
            "data": data or {}
        }
        send_message(self.sock, json.dumps(request))
        response_str = recv_message(self.sock)
        return json.loads(response_str)
    
    def register(self, name, email, password):
        """註冊"""
        print(f"📝 註冊使用者: {name}")
        response = self.send_request("register", {
            "name": name,
            "email": email,
            "password": password
        })
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        return response.get("status") == "success"
    
    def login(self, email, password):
        """登入"""
        print(f"🔐 登入: {email}")
        response = self.send_request("login", {
            "email": email,
            "password": password
        })
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        
        if response.get("status") == "success":
            self.user_id = response["data"]["user_id"]
            self.user_name = response["data"]["name"]
            return True
        return False
    
    def list_online_users(self):
        """列出線上使用者"""
        print("👥 查詢線上使用者")
        response = self.send_request("list_online_users")
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        return response
    
    def create_room(self, room_name, visibility="public"):
        """建立房間"""
        print(f"🏠 建立房間: {room_name}")
        response = self.send_request("create_room", {
            "name": room_name,
            "visibility": visibility
        })
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        return response
    
    def list_rooms(self):
        """列出公開房間"""
        print("🏠 查詢公開房間列表")
        response = self.send_request("list_rooms")
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        return response
    
    def join_room(self, room_id):
        """加入房間"""
        print(f"🚪 加入房間 ID: {room_id}")
        response = self.send_request("join_room", {
            "room_id": room_id
        })
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        return response
    
    def leave_room(self, room_id):
        """離開房間"""
        print(f"🚪 離開房間 ID: {room_id}")
        response = self.send_request("leave_room", {
            "room_id": room_id
        })
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        return response
    
    def logout(self):
        """登出"""
        print("👋 登出")
        response = self.send_request("logout")
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        return response
    
    def close(self):
        """關閉連線"""
        if self.sock:
            self.sock.close()

def test_lobby_server():
    """測試 Lobby Server"""
    
    print("=" * 60)
    print("開始測試 Lobby Server")
    print("=" * 60)
    print()
    
    # 建立兩個客戶端（模擬兩個玩家）
    alice = LobbyClient()
    bob = LobbyClient()
    
    try:
        # ========== 測試 1: 連線 ==========
        print("【測試 1】連線到 Lobby Server")
        print("-" * 60)
        if not alice.connect():
            return
        if not bob.connect():
            return
        
        # ========== 測試 2: 註冊 ==========
        print("【測試 2】註冊使用者")
        print("-" * 60)
        alice.register("Alice", "alice@test.com", "password123")
        bob.register("Bob", "bob@test.com", "password456")
        
        # ========== 測試 3: 登入 ==========
        print("【測試 3】登入")
        print("-" * 60)
        if not alice.login("alice@test.com", "password123"):
            print("❌ Alice 登入失敗")
            return
        print(f"✅ Alice 登入成功 (ID: {alice.user_id})\n")
        
        if not bob.login("bob@test.com", "password456"):
            print("❌ Bob 登入失敗")
            return
        print(f"✅ Bob 登入成功 (ID: {bob.user_id})\n")
        
        # ========== 測試 4: 線上使用者列表 ==========
        print("【測試 4】查詢線上使用者")
        print("-" * 60)
        response = alice.list_online_users()
        if response.get("status") == "success":
            users = response["data"]
            print(f"✅ 查詢到 {len(users)} 位線上使用者\n")
        
        # ========== 測試 5: 建立房間 ==========
        print("【測試 5】Alice 建立房間")
        print("-" * 60)
        response = alice.create_room("Alice's Game Room", "public")
        if response.get("status") == "success":
            room_id = response["data"]["id"]
            print(f"✅ Alice 成功建立房間 (ID: {room_id})\n")
        else:
            print("❌ 建立房間失敗")
            return
        
        # ========== 測試 6: 查詢房間列表 ==========
        print("【測試 6】查詢公開房間列表")
        print("-" * 60)
        response = bob.list_rooms()
        if response.get("status") == "success":
            rooms = response["data"]
            print(f"✅ 查詢到 {len(rooms)} 個公開房間\n")
        
        # ========== 測試 7: 加入房間 ==========
        print("【測試 7】Bob 加入 Alice 的房間")
        print("-" * 60)
        response = bob.join_room(room_id)
        if response.get("status") == "success":
            print(f"✅ Bob 成功加入房間\n")
        else:
            print(f"❌ Bob 加入房間失敗: {response.get('message')}\n")
        
        # ========== 測試 8: 離開房間 ==========
        print("【測試 8】Bob 離開房間")
        print("-" * 60)
        response = bob.leave_room(room_id)
        if response.get("status") == "success":
            print(f"✅ Bob 成功離開房間\n")
        
        # ========== 測試 9: 登出 ==========
        print("【測試 9】登出")
        print("-" * 60)
        alice.logout()
        print("✅ Alice 已登出\n")
        
        # Bob 繼續保持連線（測試不同情況）
        print("(Bob 保持連線)\n")
        
        print("=" * 60)
        print("✅ 所有測試完成！")
        print("=" * 60)
        
    except ConnectionRefusedError:
        print("❌ 無法連線到 Lobby Server")
        print("請確認 Lobby Server 是否已啟動：")
        print("  cd lobby_server")
        print("  python3 lobby_server.py")
    except ProtocolError as e:
        print(f"❌ 協定錯誤: {e}")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        alice.close()
        bob.close()
        print("\n🔌 已關閉所有連線")

if __name__ == "__main__":
    test_lobby_server()