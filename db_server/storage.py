import json
import os
import threading
from models import User, Room, GameLog

class Storage:
    """資料存取層（線程安全）"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.lock = threading.Lock()  # 防止多執行緒同時寫入
        
        # 確保資料目錄存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 檔案路徑
        self.users_file = os.path.join(data_dir, "users.json")
        self.rooms_file = os.path.join(data_dir, "rooms.json")
        self.gamelogs_file = os.path.join(data_dir, "gamelogs.json")
        
        # 初始化檔案
        self._init_file(self.users_file, [])
        self._init_file(self.rooms_file, [])
        self._init_file(self.gamelogs_file, [])
    
    def _init_file(self, filepath, default_data):
        """初始化檔案（如果不存在）"""
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
    
    def _load_json(self, filepath):
        """讀取 JSON 檔案"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_json(self, filepath, data):
        """儲存 JSON 檔案"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ============ User CRUD ============
    
    def create_user(self, user_data):
        """建立使用者"""
        with self.lock:
            users = self._load_json(self.users_file)
            
            # 生成新 ID
            new_id = max([u.get('id', 0) for u in users], default=0) + 1
            user_data['id'] = new_id
            
            users.append(user_data)
            self._save_json(self.users_file, users)
            return user_data
    
    def read_user(self, user_id):
        """讀取使用者（by ID）"""
        with self.lock:
            users = self._load_json(self.users_file)
            for user in users:
                if user.get('id') == user_id:
                    return user
            return None
    
    def update_user(self, user_id, updates):
        """更新使用者"""
        with self.lock:
            users = self._load_json(self.users_file)
            for i, user in enumerate(users):
                if user.get('id') == user_id:
                    users[i].update(updates)
                    self._save_json(self.users_file, users)
                    return users[i]
            return None
    
    def delete_user(self, user_id):
        """刪除使用者"""
        with self.lock:
            users = self._load_json(self.users_file)
            users = [u for u in users if u.get('id') != user_id]
            self._save_json(self.users_file, users)
            return True
    
    def query_users(self, filters):
        """查詢使用者（例如：by email）"""
        with self.lock:
            users = self._load_json(self.users_file)
            result = users
            
            # 簡單過濾
            for key, value in filters.items():
                result = [u for u in result if u.get(key) == value]
            
            return result
    
    # ============ Room CRUD（類似實作）============
    
    def create_room(self, room_data):
        with self.lock:
            rooms = self._load_json(self.rooms_file)
            new_id = max([r.get('id', 0) for r in rooms], default=0) + 1
            room_data['id'] = new_id
            rooms.append(room_data)
            self._save_json(self.rooms_file, rooms)
            return room_data
    
    def read_room(self, room_id):
        with self.lock:
            rooms = self._load_json(self.rooms_file)
            for room in rooms:
                if room.get('id') == room_id:
                    return room
            return None
    
    def update_room(self, room_id, updates):
        with self.lock:
            rooms = self._load_json(self.rooms_file)
            for i, room in enumerate(rooms):
                if room.get('id') == room_id:
                    rooms[i].update(updates)
                    self._save_json(self.rooms_file, rooms)
                    return rooms[i]
            return None
    
    def delete_room(self, room_id):
        with self.lock:
            rooms = self._load_json(self.rooms_file)
            rooms = [r for r in rooms if r.get('id') != room_id]
            self._save_json(self.rooms_file, rooms)
            return True
    
    def query_rooms(self, filters):
        with self.lock:
            rooms = self._load_json(self.rooms_file)
            result = rooms
            for key, value in filters.items():
                result = [r for r in result if r.get(key) == value]
            return result
    
    # ============ GameLog CRUD（類似實作）============
    
    def create_gamelog(self, log_data):
        with self.lock:
            logs = self._load_json(self.gamelogs_file)
            new_id = max([l.get('id', 0) for l in logs], default=0) + 1
            log_data['id'] = new_id
            logs.append(log_data)
            self._save_json(self.gamelogs_file, logs)
            return log_data
    
    def query_gamelogs(self, filters):
        with self.lock:
            logs = self._load_json(self.gamelogs_file)
            result = logs
            for key, value in filters.items():
                result = [l for l in result if l.get(key) == value]
            return result