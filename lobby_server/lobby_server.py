# lobby_server.py
import socket
import json
import threading
import logging
import hashlib
import signal
import sys
import argparse
from datetime import datetime
from protocol import send_message, recv_message, ProtocolError
from db_client import DBClient
from game_manager import GameManager
from queue import Queue  # 新增：發送任務隊列

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class LobbyServer:
    """Lobby Server"""
    
    def __init__(self, host='0.0.0.0', port=10002, db_host='localhost', db_port=10001):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.shutdown_flag = False
        
        # DB 客戶端
        self.db = DBClient(db_host, db_port)

        # Game Server 管理器
        self.game_manager = GameManager()
        
        # 線上使用者追蹤
        self.online_users = {}  # {user_id: {"socket": sock, "name": name, ...}}
        self.user_sockets = {}  # {socket: user_id}
        self.lock = threading.Lock()
        
        # 房間追蹤（記憶體中的即時狀態）
        self.rooms = {}  # {room_id: {"members": [user_id], "invitations": {user_id: status}}}
        
        # 邀請追蹤
        self.pending_invitations = {}  # {user_id: [{"room_id": ..., "from": ...}]}

        # 發送任務隊列與 worker（避免單一慢 client 阻塞 request thread）
        self.send_queue = Queue()
        self.send_workers = []
        self._start_send_workers(num_workers=4)
    
    def _start_send_workers(self, num_workers=4):
        """啟動固定數量的發送 worker（daemon threads）"""
        for i in range(num_workers):
            t = threading.Thread(target=self._send_worker, name=f"send-worker-{i}", daemon=True)
            t.start()
            self.send_workers.append(t)
        logger.info(f"🔁 已啟動 {num_workers} 個 send worker")

    def _send_worker(self):
        """持續處理 send_queue 的發送任務"""
        while True:
            try:
                user_id, message = self.send_queue.get()
                sock = None
                try:
                    with self.lock:
                        user_info = self.online_users.get(user_id)
                        if not user_info:
                            continue
                        sock = user_info["socket"]

                    # 實際發送（仍使用既有的 protocol.send_message）
                    send_message(sock, json.dumps(message))
                    logger.debug(f"[worker] 已發送給 user {user_id}: {message}")
                except Exception as e:
                    logger.error(f"[worker] 傳送給 {user_id} 發生錯誤: {e}")
                    # 嘗試清理失效連線（若 socket 與記錄一致）
                    try:
                        with self.lock:
                            if user_id in self.online_users and self.online_users[user_id]["socket"] is sock:
                                del self.user_sockets[sock]
                                del self.online_users[user_id]
                                logger.info(f"🧹 已移除連線失敗的使用者 {user_id}")
                    except Exception:
                        pass
                finally:
                    self.send_queue.task_done()
            except Exception as e:
                logger.error(f"[worker] 未預期錯誤: {e}")
                import time
                time.sleep(0.1)
    
    def start(self):
        """啟動 Lobby Server"""
        try:
            # 連線到 DB
            if not self.db.connect():
                logger.error("❌ 無法連線到 DB Server，請確認 DB Server 已啟動")
                return
            
            # 建立 socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True
            
            logger.info(f"✅ Lobby Server 啟動於 {self.host}:{self.port}")
            
            # 主迴圈
            while self.running:
                try:
                    client_sock, client_addr = self.server_socket.accept()
                    logger.info(f"📥 新連線來自 {client_addr}")
                    
                    # 建立執行緒處理
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_sock, client_addr),
                        daemon=True
                    )
                    client_thread.start()
                
                except KeyboardInterrupt:
                    logger.info("⚠️ 收到中斷信號")
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"❌ 接受連線時發生錯誤: {e}")
        
        finally:
            self.shutdown()
    
    def handle_client(self, client_sock, client_addr):
        """處理客戶端連線"""
        user_id = None
        
        try:
            client_sock.settimeout(600)  # 10 分鐘超時
            
            while self.running:
                try:
                    # 接收請求
                    request_str = recv_message(client_sock)
                    request = json.loads(request_str)
                    
                    action = request.get("action")
                    data = request.get("data", {})
                    
                    logger.info(f"📨 收到請求: {action} from {client_addr}")
                    
                    # 路由到對應的處理函式
                    if action == "register":
                        response = self.handle_register(data)
                    elif action == "login":
                        response = self.handle_login(data, client_sock)
                        if response.get("status") == "success":
                            user_id = response["data"]["user_id"]
                    elif action == "logout":
                        response = self.handle_logout(client_sock)
                        break  # 登出後關閉連線
                    elif action == "list_online_users":
                        response = self.handle_list_online_users()
                    elif action == "list_rooms":
                        response = self.handle_list_rooms()
                    elif action == "create_room":
                        response = self.handle_create_room(data, client_sock)
                    elif action == "join_room":
                        response = self.handle_join_room(data, client_sock)
                    elif action == "leave_room":
                        response = self.handle_leave_room(data, client_sock)
                    elif action == "invite_user":
                        response = self.handle_invite_user(data, client_sock)
                    elif action == "list_invitations":
                        response = self.handle_list_invitations(client_sock)
                    elif action == "respond_invitation":
                        response = self.handle_respond_invitation(data, client_sock)
                    elif action == "start_game":
                        response = self.handle_start_game(data, client_sock)
                    elif action == "report_game_result":
                        response = self.handle_game_result(data)
                    elif action == "spectate_game":
                        response = self.handle_spectate_game(data, client_sock)
                    elif action == "replay_response":
                        response = self.handle_replay_response(data, client_sock)
                    else:
                        response = {"status": "error", "message": f"未知的 action: {action}"}
                    
                    # 回傳結果
                    send_message(client_sock, json.dumps(response))
                
                except ProtocolError as e:
                    logger.warning(f"⚠️ 協定錯誤: {e}")
                    break
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON 解析錯誤: {e}")
                    error_response = {"status": "error", "message": "JSON 格式錯誤"}
                    send_message(client_sock, json.dumps(error_response))
                except socket.timeout:
                    logger.warning(f"⏰ 客戶端 {client_addr} 超時")
                    break
                except (ConnectionResetError, BrokenPipeError):
                    logger.info(f"🔌 客戶端 {client_addr} 斷線")
                    break
        
        except Exception as e:
            logger.error(f"❌ 處理客戶端時發生錯誤: {e}")
        
        finally:
            # 清理
            if user_id:
                self.remove_online_user(client_sock)
            
            try:
                client_sock.close()
            except:
                pass
            
            logger.info(f"👋 關閉與 {client_addr} 的連線")
    
    # ========== 註冊/登入 ==========
    
    def handle_register(self, data):
        """處理註冊"""
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        
        if not name or not email or not password:
            return {"status": "error", "message": "缺少必要欄位"}
        
        # 檢查 email 是否已存在
        existing_user = self.db.get_user_by_email(email)
        if existing_user:
            return {"status": "error", "message": "Email 已被註冊"}
        
        # 密碼雜湊
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # 建立使用者
        user = self.db.create_user(name, email, password_hash)
        if user:
            return {"status": "success", "message": "註冊成功", "data": {"user_id": user["id"]}}
        else:
            return {"status": "error", "message": "註冊失敗"}
    
    def handle_login(self, data, client_sock):
        """處理登入"""
        email = data.get("email")
        password = data.get("password")
        
        if not email or not password:
            return {"status": "error", "message": "缺少必要欄位"}
        
        # 查詢使用者
        user = self.db.get_user_by_email(email)
        if not user:
            return {"status": "error", "message": "使用者不存在"}
        
        # 驗證密碼
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if user["password_hash"] != password_hash:
            return {"status": "error", "message": "密碼錯誤"}
        
        # 更新最後登入時間
        now = datetime.now().isoformat()
        self.db.update_user_login(user["id"], now)
        
        # 加入線上使用者列表
        with self.lock:
            self.online_users[user["id"]] = {
                "socket": client_sock,
                "name": user["name"],
                "email": user["email"],
                "login_at": now
            }
            self.user_sockets[client_sock] = user["id"]
        
        logger.info(f"👤 使用者 {user['name']} (ID: {user['id']}) 已登入")
        
        return {
            "status": "success",
            "message": "登入成功",
            "data": {
                "user_id": user["id"],
                "name": user["name"]
            }
        }
    
    def handle_logout(self, client_sock):
        """處理登出"""
        self.remove_online_user(client_sock)
        return {"status": "success", "message": "登出成功"}
    
    def remove_online_user(self, client_sock):
        """移除線上使用者"""
        with self.lock:
            user_id = self.user_sockets.get(client_sock)
            if user_id:
                user_info = self.online_users.get(user_id)
                if user_info:
                    logger.info(f"👋 使用者 {user_info['name']} (ID: {user_id}) 已登出")
                    del self.online_users[user_id]
                del self.user_sockets[client_sock]
    
    # ========== 列表查詢 ==========
    
    def handle_list_online_users(self):
        """列出線上使用者"""
        with self.lock:
            users = [
                {"user_id": uid, "name": info["name"]}
                for uid, info in self.online_users.items()
            ]
        return {"status": "success", "data": users}
    
    def handle_list_rooms(self):
        """列出公開房間"""
        rooms = self.db.get_public_rooms()
        
        # 加上即時狀態（成員數量等）
        for room in rooms:
            room_id = room["id"]
            if room_id in self.rooms:
                room["current_members"] = len(self.rooms[room_id]["members"])
            else:
                room["current_members"] = 0
        
        return {"status": "success", "data": rooms}
    
    # ========== 房間管理 ==========
    
    def handle_create_room(self, data, client_sock):
        """建立房間"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}
        
        room_name = data.get("name")
        visibility = data.get("visibility", "public")  # "public" or "private"
        
        if not room_name:
            return {"status": "error", "message": "房間名稱不可為空"}
        
        # 建立房間（在 DB）
        room = self.db.create_room(room_name, user_id, visibility)
        if not room:
            return {"status": "error", "message": "建立房間失敗"}
        
        # 初始化房間狀態（在記憶體）
        with self.lock:
            self.rooms[room["id"]] = {
                "members": [user_id],
                "invitations": {}
            }
        
        logger.info(f"🏠 使用者 {user_id} 建立房間 '{room_name}' (ID: {room['id']})")
        
        return {"status": "success", "data": room}
    
    def handle_join_room(self, data, client_sock):
        """加入房間"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}

        room_id = data.get("room_id")

        # 從 DB 取得房間資訊
        room = self.db.get_room(room_id)
        if not room:
            return {"status": "error", "message": "房間不存在"}

        # 檢查是否為房主
        is_host = (room.get("host_user_id") == user_id)

        # 檢查房間狀態（房主可以加入 waiting 狀態的房間）
        if room["status"] == "playing":
            return {"status": "error", "message": "房間正在遊戲中"}

        # 檢查是否為私人房間（房主總是可以加入）
        if room["visibility"] == "private" and not is_host:
            # 檢查是否在邀請名單中
            if user_id not in room.get("invite_list", []):
                return {"status": "error", "message": "此房間為私人房間，需要邀請才能加入"}

        # 加入房間
        with self.lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = {"members": [], "invitations": {}}

            # 檢查是否已在房間中
            if user_id in self.rooms[room_id]["members"]:
                return {"status": "error", "message": "已在房間中"}

            # 檢查房間是否已滿（最多 2 人，但房主總是可以加入）
            if len(self.rooms[room_id]["members"]) >= 2 and not is_host:
                return {"status": "error", "message": "房間已滿"}

            # 如果房主重新加入，確保房主總是在成員列表中
            # 如果房間已滿但房主要加入，這是允許的（房主可能之前離開了）
            if is_host and len(self.rooms[room_id]["members"]) >= 2:
                # 房主優先，不檢查房間是否已滿
                pass

            self.rooms[room_id]["members"].append(user_id)

        if is_host:
            logger.info(f"🚪 房主 {user_id} 重新加入房間 {room_id}")
        else:
            logger.info(f"🚪 使用者 {user_id} 加入房間 {room_id}")

        # 廣播給房間內其他成員（非阻塞）
        self.broadcast_to_room(room_id, {
            "type": "room_update",
            "action": "user_joined",
            "user_id": user_id
        }, exclude_user=user_id)

        return {"status": "success", "message": "已加入房間"}
    
    def handle_leave_room(self, data, client_sock):
        """離開房間"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}
        
        room_id = data.get("room_id")
        
        with self.lock:
            if room_id not in self.rooms:
                return {"status": "error", "message": "房間不存在"}
            
            if user_id not in self.rooms[room_id]["members"]:
                return {"status": "error", "message": "不在房間中"}
            
            self.rooms[room_id]["members"].remove(user_id)
            
            # 如果房間空了，刪除房間
            if len(self.rooms[room_id]["members"]) == 0:
                del self.rooms[room_id]
                self.db.delete_room(room_id)
                logger.info(f"🗑️ 房間 {room_id} 已刪除（無成員）")
        
        logger.info(f"🚪 使用者 {user_id} 離開房間 {room_id}")
        
        # 廣播
        self.broadcast_to_room(room_id, {
            "type": "room_update",
            "action": "user_left",
            "user_id": user_id
        })
        
        return {"status": "success", "message": "已離開房間"}
    
    # ========== 邀請系統 ==========
    
    def handle_invite_user(self, data, client_sock):
        """邀請使用者"""
        inviter_id = self.user_sockets.get(client_sock)
        if not inviter_id:
            return {"status": "error", "message": "未登入"}
        
        room_id = data.get("room_id")
        invitee_id = data.get("user_id")
        
        # 檢查房間
        room = self.db.get_room(room_id)
        if not room:
            return {"status": "error", "message": "房間不存在"}
        
        # 檢查是否為房主或房間成員
        with self.lock:
            if room_id not in self.rooms or inviter_id not in self.rooms[room_id]["members"]:
                return {"status": "error", "message": "你不在這個房間中"}
        
        # 檢查被邀請者是否存在
        if invitee_id not in self.online_users:
            return {"status": "error", "message": "使用者不在線上"}
        
        # 建立邀請
        with self.lock:
            if invitee_id not in self.pending_invitations:
                self.pending_invitations[invitee_id] = []
            
            self.pending_invitations[invitee_id].append({
                "room_id": room_id,
                "room_name": room["name"],
                "from_user_id": inviter_id,
                "from_user_name": self.online_users[inviter_id]["name"]
            })
        
        # 通知被邀請者（非阻塞）
        self.send_to_user(invitee_id, {
            "type": "invitation",
            "room_id": room_id,
            "room_name": room["name"],
            "from_user_id": inviter_id,
            "from_user_name": self.online_users[inviter_id]["name"]
        })
        
        logger.info(f"✉️ 使用者 {inviter_id} 邀請 {invitee_id} 加入房間 {room_id}")
        
        return {"status": "success", "message": "已發送邀請"}
    
    def handle_list_invitations(self, client_sock):
        """列出待處理的邀請"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}
        
        with self.lock:
            invitations = self.pending_invitations.get(user_id, [])
        
        return {"status": "success", "data": invitations}
    
    def handle_respond_invitation(self, data, client_sock):
        """回應邀請"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}
        
        room_id = data.get("room_id")
        accept = data.get("accept", False)
        
        # 找到邀請
        with self.lock:
            if user_id not in self.pending_invitations:
                return {"status": "error", "message": "沒有待處理的邀請"}
            
            invitations = self.pending_invitations[user_id]
            invitation = None
            for inv in invitations:
                if inv["room_id"] == room_id:
                    invitation = inv
                    invitations.remove(inv)
                    break
            
            if not invitation:
                return {"status": "error", "message": "找不到該邀請"}
        
        if accept:
            # 接受邀請 → 加入房間
            return self.handle_join_room({"room_id": room_id}, client_sock)
        else:
            return {"status": "success", "message": "已拒絕邀請"}
    
    # ========== 開始遊戲 ==========
    
    def handle_start_game(self, data, client_sock):
        """開始遊戲"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}
        
        room_id = data.get("room_id")
        
        # 檢查房間
        with self.lock:
            if room_id not in self.rooms:
                return {"status": "error", "message": "房間不存在"}
            
            members = self.rooms[room_id]["members"]
            
            # 檢查人數
            if len(members) != 2:
                return {"status": "error", "message": f"房間需要 2 人才能開始（目前 {len(members)} 人）"}
            
            # 檢查是否為房主
            room = self.db.get_room(room_id)
            if room["host_user_id"] != user_id:
                return {"status": "error", "message": "只有房主可以開始遊戲"}
        
        # 啟動 Game Server
        player1_id, player2_id = members[0], members[1]
        game_info = self.game_manager.start_game_server(room_id, player1_id, player2_id)
        
        if not game_info:
            return {"status": "error", "message": "無法啟動 Game Server"}
        
        # 更新房間狀態
        self.db.update_room(room_id, {"status": "playing"})
        
        # 通知所有玩家連線到 Game Server
        game_port = game_info["port"]
        for member_id in members:
            self.send_to_user(member_id, {
                "type": "game_start",
                "room_id": room_id,
                "game_server_host": "localhost",  # 或課程機 IP
                "game_server_port": game_port
            })
        
        logger.info(f"🎮 房間 {room_id} 開始遊戲 (Port: {game_port})")
        
        return {
            "status": "success",
            "data": {
                "game_server_host": "localhost",
                "game_server_port": game_port
            }
        }

    def handle_game_result(self, data):
        """處理遊戲結果回報"""
        room_id = data.get("room_id")
        winner = data.get("winner")
        results = data.get("results", [])

        if not room_id:
            return {"status": "error", "message": "缺少 room_id"}

        # 儲存遊戲記錄到資料庫
        try:
            # 提取玩家 ID
            user_ids = [r["userId"] for r in results]

            # 建立 match_id (使用時間戳)
            match_id = f"match_{room_id}_{int(datetime.now().timestamp())}"

            # 儲存到資料庫
            self.db.create_gamelog(match_id, room_id, user_ids, results)
            logger.info(f"📊 已儲存遊戲記錄: {match_id}")
        except Exception as e:
            logger.error(f"❌ 儲存遊戲記錄失敗: {e}")

        # 重置房間狀態為 waiting
        self.db.update_room(room_id, {"status": "waiting"})
        logger.info(f"🏠 房間 {room_id} 狀態重置為 waiting")

        # 從 GameManager 清除遊戲
        with self.lock:
            if room_id in self.game_manager.active_games:
                del self.game_manager.active_games[room_id]

        # 發送 game_ended 通知給房間內所有成員（玩家和觀眾）
        # 玩家會收到 replay 請求，觀眾只收到遊戲結束通知
        with self.lock:
            if room_id in self.rooms:
                members = list(self.rooms[room_id]["members"])
                for member_id in members:
                    self.send_to_user(member_id, {
                        "type": "game_ended",
                        "room_id": room_id,
                        "winner": winner,
                        "results": results,
                        "request_replay": True  # 請求玩家回覆是否要replay
                    })

        return {"status": "success", "message": "遊戲結果已記錄"}

    def handle_replay_response(self, data, client_sock):
        """處理 replay 回應"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}

        room_id = data.get("room_id")
        want_replay = data.get("replay", False)

        logger.info(f"👤 使用者 {user_id} replay回應: {'是' if want_replay else '否'} (房間 {room_id})")

        with self.lock:
            # 確保房間存在
            if room_id not in self.rooms:
                return {"status": "error", "message": "房間不存在"}

            # 初始化 replay_responses 如果不存在
            if "replay_responses" not in self.rooms[room_id]:
                self.rooms[room_id]["replay_responses"] = {}

            # 記錄此玩家的回應
            self.rooms[room_id]["replay_responses"][user_id] = want_replay

            # 取得房間中的玩家列表
            room = self.db.get_room(room_id)
            if not room:
                return {"status": "error", "message": "房間資料不存在"}

            players = room.get("players", [])

            # 檢查是否所有玩家都已回應
            replay_responses = self.rooms[room_id]["replay_responses"]
            all_responded = all(player in replay_responses for player in players)

            if all_responded:
                # 所有玩家都回應了
                all_want_replay = all(replay_responses.get(player, False) for player in players)

                # 清除 replay_responses 以便下次使用
                self.rooms[room_id]["replay_responses"] = {}

                if all_want_replay:
                    # 所有玩家都想重玩
                    logger.info(f"✅ 房間 {room_id} 所有玩家同意重玩")

                    # 通知所有玩家可以重新開始
                    for player_id in players:
                        self.send_to_user(player_id, {
                            "type": "replay_accepted",
                            "room_id": room_id,
                            "message": "所有玩家同意重玩，房主可以重新開始遊戲"
                        })
                else:
                    # 至少有一個玩家不想重玩
                    logger.info(f"❌ 房間 {room_id} 有玩家拒絕重玩")

                    # 通知所有玩家重玩被拒絕
                    for player_id in players:
                        self.send_to_user(player_id, {
                            "type": "replay_rejected",
                            "room_id": room_id,
                            "message": "有玩家拒絕重玩，返回選單"
                        })

        return {"status": "success", "message": "已收到回應"}

    def handle_spectate_game(self, data, client_sock):
        """處理觀戰請求"""
        user_id = self.user_sockets.get(client_sock)
        if not user_id:
            return {"status": "error", "message": "未登入"}

        room_id = data.get("room_id")

        # 檢查房間是否存在
        room = self.db.get_room(room_id)
        if not room:
            return {"status": "error", "message": "房間不存在"}

        # 檢查房間是否在遊戲中
        if room["status"] != "playing":
            return {"status": "error", "message": "房間尚未開始遊戲"}

        # 取得 Game Server 資訊
        game_info = self.game_manager.get_game_info(room_id)
        if not game_info:
            return {"status": "error", "message": "找不到 Game Server"}

        logger.info(f"👁️ 使用者 {user_id} 觀戰房間 {room_id}")

        return {
            "status": "success",
            "data": {
                "game_server_host": "localhost",
                "game_server_port": game_info["port"],
                "room_id": room_id
            }
        }

    # ========== 輔助函式 ==========
    
    def broadcast_to_room(self, room_id, message, exclude_user=None):
        """廣播訊息給房間內所有成員（非阻塞）"""
        with self.lock:
            if room_id not in self.rooms:
                return
            
            members = list(self.rooms[room_id]["members"])  # 複製避免 race condition
        for member_id in members:
            if member_id != exclude_user:
                self.send_to_user(member_id, message)
    
    def send_to_user(self, user_id, message):
        """把發送任務放到 queue，由 worker 實際送出（非阻塞）"""
        try:
            self.send_queue.put((user_id, message))
        except Exception as e:
            logger.error(f"❌ enqueue 訊息給使用者 {user_id} 失敗: {e}")
    
    def shutdown(self):
        """關閉伺服器（支援多次呼叫）"""
        if self.shutdown_flag:
            return  # 已經關閉過了

        self.shutdown_flag = True
        logger.info("🛑 正在關閉 Lobby Server...")
        self.running = False

        # 關閉所有 Game Server
        try:
            self.game_manager.shutdown_all()
        except Exception as e:
            logger.error(f"關閉 Game Servers 時發生錯誤: {e}")

        # 關閉 DB 連線
        try:
            self.db.disconnect()
        except Exception as e:
            logger.error(f"關閉 DB 連線時發生錯誤: {e}")

        # 關閉伺服器 socket
        if self.server_socket:
            try:
                self.server_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.server_socket.close()
            except:
                pass

        logger.info("✅ Lobby Server 已關閉")


if __name__ == "__main__":
    # 解析命令列參數
    parser = argparse.ArgumentParser(description='Lobby Server for 2-Player Tetris')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host address (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=10002, help='Port number (default: 10002)')
    parser.add_argument('--db-host', type=str, default='localhost', help='DB Server host (default: localhost)')
    parser.add_argument('--db-port', type=int, default=10001, help='DB Server port (default: 10001)')
    args = parser.parse_args()

    # 建立伺服器實例
    server = LobbyServer(host=args.host, port=args.port, db_host=args.db_host, db_port=args.db_port)

    # 設定信號處理器，確保優雅關閉
    def signal_handler(sig, *_args):
        logger.info(f"\n⚠️ 收到信號 {sig}，正在關閉伺服器...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill command

    try:
        logger.info(f"🚀 啟動 Lobby Server (Host: {args.host}, Port: {args.port})")
        logger.info(f"📊 DB Server: {args.db_host}:{args.db_port}")
        logger.info("使用 Ctrl+C 停止伺服器")
        server.start()
    except OSError as e:
        if e.errno == 48 or "Address already in use" in str(e):
            logger.error(f"❌ 埠 {args.port} 已被使用")
            logger.error("解決方法:")
            logger.error(f"  1. 使用不同的埠: python3 lobby_server.py --port <其他埠號>")
            logger.error(f"  2. 找出並關閉佔用埠的程式: lsof -i :{args.port}")
            logger.error(f"  3. 等待幾秒鐘後重試（系統可能正在釋放埠）")
        else:
            logger.error(f"❌ 發生錯誤: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        server.shutdown()
