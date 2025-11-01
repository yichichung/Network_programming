from datetime import datetime
from typing import List, Optional

class User:
    """使用者資料模型"""
    def __init__(self, id=None, name="", email="", password_hash="", 
                 created_at=None, last_login_at=None):
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at or datetime.now().isoformat()
        self.last_login_at = last_login_at
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at
        }
    
    @staticmethod
    def from_dict(data):
        return User(**data)


class Room:
    """房間資料模型"""
    def __init__(self, id=None, name="", host_user_id=None, 
                 visibility="public", invite_list=None, 
                 status="idle", created_at=None):
        self.id = id
        self.name = name
        self.host_user_id = host_user_id
        self.visibility = visibility  # "public" or "private"
        self.invite_list = invite_list or []
        self.status = status  # "idle" or "playing"
        self.created_at = created_at or datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "host_user_id": self.host_user_id,
            "visibility": self.visibility,
            "invite_list": self.invite_list,
            "status": self.status,
            "created_at": self.created_at
        }
    
    @staticmethod
    def from_dict(data):
        return Room(**data)


class GameLog:
    """遊戲記錄資料模型"""
    def __init__(self, id=None, match_id=None, room_id=None, 
                 users=None, start_at=None, end_at=None, results=None):
        self.id = id
        self.match_id = match_id
        self.room_id = room_id
        self.users = users or []  # [user_id1, user_id2]
        self.start_at = start_at or datetime.now().isoformat()
        self.end_at = end_at
        self.results = results or []  # [{userId, score, lines, maxCombo}, ...]
    
    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "room_id": self.room_id,
            "users": self.users,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "results": self.results
        }
    
    @staticmethod
    def from_dict(data):
        return GameLog(**data)