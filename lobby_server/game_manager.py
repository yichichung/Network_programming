# game_manager.py

import subprocess
import socket
import logging
import threading
import time
import os

logger = logging.getLogger(__name__)

class GameManager:
    """管理 Game Server 的生命週期"""
    
    def __init__(self, game_server_script=None):
        if game_server_script is None:
            # Default to game_server/game_server.py relative to project root
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.game_server_script = os.path.join(script_dir, "game_server", "game_server.py")
        else:
            self.game_server_script = game_server_script
        self.active_games = {}  # {room_id: {"process": proc, "port": port, ...}}
        self.lock = threading.Lock()
    
    def find_available_port(self, start_port=10100, end_port=10200):
        """尋找可用的 Port"""
        for port in range(start_port, end_port):
            try:
                # 嘗試綁定 port
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.bind(('', port))
                test_sock.close()
                return port
            except OSError:
                continue
        return None
    
    def start_game_server(self, room_id, player1_id, player2_id):
        """
        啟動 Game Server
        
        Returns:
            dict: {"port": int, "process": subprocess.Popen} or None
        """
        with self.lock:
            # 檢查是否已經有 Game Server 在運行
            if room_id in self.active_games:
                logger.warning(f"⚠️ 房間 {room_id} 已有 Game Server 在運行")
                return self.active_games[room_id]
            
            # 尋找可用 port
            port = self.find_available_port()
            if not port:
                logger.error("❌ 找不到可用的 Port")
                return None
            
            try:
                # 啟動 Game Server 子行程
                cmd = [
                    "python3",
                    self.game_server_script,
                    "--port", str(port),
                    "--room-id", str(room_id),
                    "--player1", str(player1_id),
                    "--player2", str(player2_id)
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # 等待一下確保啟動
                time.sleep(0.5)
                
                # 檢查是否成功啟動
                if process.poll() is not None:
                    # 已經結束了，啟動失敗
                    stdout, stderr = process.communicate()
                    logger.error(f"❌ Game Server 啟動失敗:\n{stderr}")
                    return None
                
                game_info = {
                    "port": port,
                    "process": process,
                    "room_id": room_id,
                    "players": [player1_id, player2_id],
                    "start_time": time.time()
                }
                
                self.active_games[room_id] = game_info
                logger.info(f"✅ 已為房間 {room_id} 啟動 Game Server (Port: {port})")
                
                # 啟動監控執行緒
                monitor_thread = threading.Thread(
                    target=self._monitor_game_server,
                    args=(room_id,),
                    daemon=True
                )
                monitor_thread.start()
                
                return game_info
            
            except Exception as e:
                logger.error(f"❌ 啟動 Game Server 時發生錯誤: {e}")
                return None
    
    def _monitor_game_server(self, room_id):
        """監控 Game Server（在獨立執行緒中運行）"""
        game_info = self.active_games.get(room_id)
        if not game_info:
            return
        
        process = game_info["process"]
        
        # 等待行程結束
        return_code = process.wait()
        
        logger.info(f"🎮 Game Server (房間 {room_id}) 已結束 (return code: {return_code})")
        
        # 讀取輸出（用於除錯）
        stdout, stderr = process.communicate()
        if stdout:
            logger.debug(f"Game Server stdout: {stdout}")
        if stderr:
            logger.error(f"Game Server stderr: {stderr}")
        
        # 清理
        with self.lock:
            if room_id in self.active_games:
                del self.active_games[room_id]
    
    def stop_game_server(self, room_id):
        """停止 Game Server"""
        with self.lock:
            game_info = self.active_games.get(room_id)
            if not game_info:
                logger.warning(f"⚠️ 房間 {room_id} 沒有 Game Server")
                return False
            
            process = game_info["process"]
            
            try:
                # 優雅地終止
                process.terminate()
                
                # 等待最多 5 秒
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 強制殺死
                    logger.warning(f"⚠️ 強制終止 Game Server (房間 {room_id})")
                    process.kill()
                
                del self.active_games[room_id]
                logger.info(f"🛑 已停止 Game Server (房間 {room_id})")
                return True
            
            except Exception as e:
                logger.error(f"❌ 停止 Game Server 時發生錯誤: {e}")
                return False
    
    def get_game_info(self, room_id):
        """取得 Game Server 資訊"""
        return self.active_games.get(room_id)
    
    def shutdown_all(self):
        """關閉所有 Game Server"""
        logger.info("🛑 關閉所有 Game Server...")
        with self.lock:
            room_ids = list(self.active_games.keys())
            for room_id in room_ids:
                self.stop_game_server(room_id)