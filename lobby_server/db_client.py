# db_client.py
# Lobby 需要透過這個模組與 DB Server 溝通。
import socket
import json
import logging
from protocol import send_message, recv_message, ProtocolError

logger = logging.getLogger(__name__)

class DBClient:
    """DB Server 客戶端（用於 Lobby Server）"""
    
    def __init__(self, db_host='localhost', db_port=10001):
        self.db_host = db_host
        self.db_port = db_port
        self.sock = None
    
    def connect(self):
        """連線到 DB Server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.db_host, self.db_port))
            logger.info(f"✅ 已連線到 DB Server: {self.db_host}:{self.db_port}")
            return True
        except Exception as e:
            logger.error(f"❌ 無法連線到 DB Server: {e}")
            return False
    
    def disconnect(self):
        """斷線"""
        if self.sock:
            try:
                self.sock.close()
                logger.info("🔌 已斷開 DB Server 連線")
            except:
                pass
            self.sock = None
    
    def _request(self, collection, action, data):
        """
        發送請求到 DB Server
        
        Returns:
            dict: 回應資料，若失敗則返回 None
        """
        if not self.sock:
            if not self.connect():
                return None
        
        try:
            # 建立請求
            request = {
                "collection": collection,
                "action": action,
                "data": data
            }
            
            # 發送
            send_message(self.sock, json.dumps(request))
            
            # 接收回應
            response_str = recv_message(self.sock)
            response = json.loads(response_str)
            
            if response.get("status") == "success":
                return response.get("data")
            else:
                logger.error(f"❌ DB 請求失敗: {response.get('message')}")
                return None
        
        except ProtocolError as e:
            logger.error(f"❌ 協定錯誤: {e}")
            self.disconnect()
            return None
        except Exception as e:
            logger.error(f"❌ DB 請求發生錯誤: {e}")
            self.disconnect()
            return None
    
    # ========== User 操作 ==========
    
    def create_user(self, name, email, password_hash):
        """建立使用者"""
        data = {
            "name": name,
            "email": email,
            "password_hash": password_hash
        }
        return self._request("User", "create", data)
    
    def get_user_by_email(self, email):
        """根據 email 查詢使用者"""
        result = self._request("User", "query", {"filters": {"email": email}})
        if result and len(result) > 0:
            return result[0]
        return None
    
    def get_user_by_id(self, user_id):
        """根據 ID 查詢使用者"""
        return self._request("User", "read", {"id": user_id})
    
    def update_user_login(self, user_id, last_login_at):
        """更新使用者最後登入時間"""
        return self._request("User", "update", {
            "id": user_id,
            "updates": {"last_login_at": last_login_at}
        })
    
    # ========== Room 操作 ==========
    
    def create_room(self, name, host_user_id, visibility="public"):
        """建立房間"""
        data = {
            "name": name,
            "host_user_id": host_user_id,
            "visibility": visibility,
            "status": "idle"
        }
        return self._request("Room", "create", data)
    
    def get_room(self, room_id):
        """取得房間資訊"""
        return self._request("Room", "read", {"id": room_id})
    
    def update_room(self, room_id, updates):
        """更新房間資訊"""
        return self._request("Room", "update", {
            "id": room_id,
            "updates": updates
        })
    
    def delete_room(self, room_id):
        """刪除房間"""
        return self._request("Room", "delete", {"id": room_id})
    
    def get_public_rooms(self):
        """取得所有公開房間"""
        result = self._request("Room", "query", {"filters": {"visibility": "public"}})
        return result if result else []
    
    # ========== GameLog 操作 ==========
    
    def create_gamelog(self, match_id, room_id, users, results):
        """建立遊戲記錄"""
        data = {
            "match_id": match_id,
            "room_id": room_id,
            "users": users,
            "results": results
        }
        return self._request("GameLog", "create", data)