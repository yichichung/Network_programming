import socket
import json
import threading
import logging
from protocol import send_message, recv_message, ProtocolError
from storage import Storage

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class DBServer:
    """Database Server"""
    
    def __init__(self, host='0.0.0.0', port=10001):
        self.host = host
        self.port = port
        self.storage = Storage()
        self.server_socket = None
        self.running = False
        self.client_threads = []
    
    def start(self):
        """啟動伺服器"""
        try:
            # 建立 socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # 設定 socket 選項（重要！）
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 綁定 & 監聽
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            logger.info(f"✅ DB Server 啟動於 {self.host}:{self.port}")
            
            # 主迴圈：接受連線
            while self.running:
                try:
                    client_sock, client_addr = self.server_socket.accept()
                    logger.info(f"📥 新連線來自 {client_addr}")
                    
                    # 為每個客戶端建立新執行緒
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_sock, client_addr),
                        daemon=True
                    )
                    client_thread.start()
                    self.client_threads.append(client_thread)
                    
                except KeyboardInterrupt:
                    logger.info("⚠️ 收到中斷信號，準備關閉...")
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"❌ 接受連線時發生錯誤: {e}")
        
        finally:
            self.shutdown()
    
    def handle_client(self, client_sock, client_addr):
        """
        處理單一客戶端（在獨立執行緒中運行）
        
        重點：完整的例外處理
        """
        try:
            # 設定超時（避免永久阻塞）
            client_sock.settimeout(300)  # 5 分鐘
            
            while self.running:
                try:
                    # 1. 接收請求
                    request_str = recv_message(client_sock)
                    logger.info(f"📨 收到請求 from {client_addr}: {request_str[:100]}")
                    
                    # 2. 解析 JSON
                    try:
                        request = json.loads(request_str)
                    except json.JSONDecodeError as e:
                        response = {"status": "error", "message": f"JSON 格式錯誤: {e}"}
                        send_message(client_sock, json.dumps(response))
                        continue
                    
                    # 3. 處理請求
                    response = self.process_request(request)
                    
                    # 4. 回傳結果
                    send_message(client_sock, json.dumps(response))
                    logger.info(f"📤 回傳 to {client_addr}: {response.get('status')}")
                
                except ProtocolError as e:
                    logger.warning(f"⚠️ 協定錯誤 from {client_addr}: {e}")
                    break  # 協定錯誤，關閉連線
                
                except socket.timeout:
                    logger.warning(f"⏰ 客戶端 {client_addr} 超時")
                    break
                
                except ConnectionResetError:
                    logger.info(f"🔌 客戶端 {client_addr} 強制關閉連線")
                    break
                
                except BrokenPipeError:
                    logger.info(f"🔌 客戶端 {client_addr} 管道中斷")
                    break
        
        except Exception as e:
            logger.error(f"❌ 處理客戶端 {client_addr} 時發生未預期錯誤: {e}")
        
        finally:
            # 確保關閉 socket
            try:
                client_sock.close()
                logger.info(f"👋 關閉與 {client_addr} 的連線")
            except:
                pass
    
    def process_request(self, request):
        """
        處理資料庫請求
        
        Args:
            request: {
                "collection": "User|Room|GameLog",
                "action": "create|read|update|delete|query",
                "data": {...}
            }
        
        Returns:
            response: {
                "status": "success|error",
                "data": {...} or "message": "..."
            }
        """
        try:
            collection = request.get("collection")
            action = request.get("action")
            data = request.get("data", {})
            
            # 路由到對應的處理函式
            if collection == "User":
                return self._handle_user(action, data)
            elif collection == "Room":
                return self._handle_room(action, data)
            elif collection == "GameLog":
                return self._handle_gamelog(action, data)
            else:
                return {"status": "error", "message": f"未知的 collection: {collection}"}
        
        except Exception as e:
            logger.error(f"❌ 處理請求時發生錯誤: {e}")
            return {"status": "error", "message": str(e)}
    
    def _handle_user(self, action, data):
        """處理 User 相關操作"""
        if action == "create":
            result = self.storage.create_user(data)
            return {"status": "success", "data": result}
        
        elif action == "read":
            user_id = data.get("id")
            result = self.storage.read_user(user_id)
            if result:
                return {"status": "success", "data": result}
            else:
                return {"status": "error", "message": "使用者不存在"}
        
        elif action == "update":
            user_id = data.get("id")
            updates = data.get("updates", {})
            result = self.storage.update_user(user_id, updates)
            if result:
                return {"status": "success", "data": result}
            else:
                return {"status": "error", "message": "使用者不存在"}
        
        elif action == "delete":
            user_id = data.get("id")
            self.storage.delete_user(user_id)
            return {"status": "success", "message": "刪除成功"}
        
        elif action == "query":
            filters = data.get("filters", {})
            result = self.storage.query_users(filters)
            return {"status": "success", "data": result}
        
        else:
            return {"status": "error", "message": f"未知的 action: {action}"}
    
    def _handle_room(self, action, data):
        """處理 Room 相關操作（類似 User）"""
        if action == "create":
            result = self.storage.create_room(data)
            return {"status": "success", "data": result}
        elif action == "read":
            room_id = data.get("id")
            result = self.storage.read_room(room_id)
            if result:
                return {"status": "success", "data": result}
            else:
                return {"status": "error", "message": "房間不存在"}
        elif action == "update":
            room_id = data.get("id")
            updates = data.get("updates", {})
            result = self.storage.update_room(room_id, updates)
            if result:
                return {"status": "success", "data": result}
            else:
                return {"status": "error", "message": "房間不存在"}
        elif action == "delete":
            room_id = data.get("id")
            self.storage.delete_room(room_id)
            return {"status": "success", "message": "刪除成功"}
        elif action == "query":
            filters = data.get("filters", {})
            result = self.storage.query_rooms(filters)
            return {"status": "success", "data": result}
        else:
            return {"status": "error", "message": f"未知的 action: {action}"}
    
    def _handle_gamelog(self, action, data):
        """處理 GameLog 相關操作"""
        if action == "create":
            result = self.storage.create_gamelog(data)
            return {"status": "success", "data": result}
        elif action == "query":
            filters = data.get("filters", {})
            result = self.storage.query_gamelogs(filters)
            return {"status": "success", "data": result}
        else:
            return {"status": "error", "message": f"未知的 action: {action}"}
    
    def shutdown(self):
        """關閉伺服器"""
        logger.info("🛑 正在關閉 DB Server...")
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        logger.info("✅ DB Server 已關閉")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=10001)
    args = parser.parse_args()

    server = DBServer(host=args.host, port=args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("\n⚠️ 收到 Ctrl+C，正在關閉...")
    finally:
        server.shutdown()
