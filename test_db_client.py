# test_db_client.py
import socket
import json
import sys
import os

# 加入 db_server 到路徑，以便導入 protocol
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'db_server'))
from protocol import send_message, recv_message, ProtocolError

def test_db_server():
    """測試 DB Server 的基本功能"""
    
    print("=" * 50)
    print("開始測試 DB Server")
    print("=" * 50)
    
    try:
        # 連線到 DB Server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 10001))
        print("✅ 成功連線到 DB Server (localhost:10001)\n")
        
        # ========== 測試 1: 建立使用者 ==========
        print("測試 1: 建立使用者")
        request = {
            "collection": "User",
            "action": "create",
            "data": {
                "name": "Alice",
                "email": "alice@example.com",
                "password_hash": "hashed_password_123"
            }
        }
        send_message(sock, json.dumps(request))
        response_str = recv_message(sock)
        response = json.loads(response_str)
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        
        if response.get("status") == "success":
            user_id = response["data"]["id"]
            print(f"✅ 成功建立使用者，ID: {user_id}\n")
        else:
            print(f"❌ 建立使用者失敗\n")
            return
        
        # ========== 測試 2: 查詢使用者 ==========
        print("測試 2: 查詢使用者 (by email)")
        request = {
            "collection": "User",
            "action": "query",
            "data": {
                "filters": {"email": "alice@example.com"}
            }
        }
        send_message(sock, json.dumps(request))
        response_str = recv_message(sock)
        response = json.loads(response_str)
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        
        if response.get("status") == "success" and len(response["data"]) > 0:
            print(f"✅ 成功查詢到使用者\n")
        else:
            print(f"❌ 查詢使用者失敗\n")
        
        # ========== 測試 3: 更新使用者 ==========
        print("測試 3: 更新使用者")
        request = {
            "collection": "User",
            "action": "update",
            "data": {
                "id": user_id,
                "updates": {
                    "name": "Alice Updated"
                }
            }
        }
        send_message(sock, json.dumps(request))
        response_str = recv_message(sock)
        response = json.loads(response_str)
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        
        if response.get("status") == "success":
            print(f"✅ 成功更新使用者\n")
        else:
            print(f"❌ 更新使用者失敗\n")
        
        # ========== 測試 4: 建立房間 ==========
        print("測試 4: 建立房間")
        request = {
            "collection": "Room",
            "action": "create",
            "data": {
                "name": "Test Room",
                "host_user_id": user_id,
                "visibility": "public",
                "status": "idle"
            }
        }
        send_message(sock, json.dumps(request))
        response_str = recv_message(sock)
        response = json.loads(response_str)
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        
        if response.get("status") == "success":
            room_id = response["data"]["id"]
            print(f"✅ 成功建立房間，ID: {room_id}\n")
        else:
            print(f"❌ 建立房間失敗\n")
        
        # ========== 測試 5: 查詢公開房間 ==========
        print("測試 5: 查詢公開房間")
        request = {
            "collection": "Room",
            "action": "query",
            "data": {
                "filters": {"visibility": "public"}
            }
        }
        send_message(sock, json.dumps(request))
        response_str = recv_message(sock)
        response = json.loads(response_str)
        print(f"回應: {json.dumps(response, indent=2, ensure_ascii=False)}\n")
        
        if response.get("status") == "success":
            print(f"✅ 成功查詢到 {len(response['data'])} 個公開房間\n")
        else:
            print(f"❌ 查詢房間失敗\n")
        
        print("=" * 50)
        print("✅ 所有測試完成！")
        print("=" * 50)
        
    except ConnectionRefusedError:
        print("❌ 無法連線到 DB Server")
        print("請確認 DB Server 是否已啟動：")
        print("  cd db_server")
        print("  python3 db_server.py")
    except ProtocolError as e:
        print(f"❌ 協定錯誤: {e}")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sock.close()
        print("\n🔌 已關閉連線")

if __name__ == "__main__":
    test_db_server()