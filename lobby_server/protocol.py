import struct
import socket

MAX_MESSAGE_SIZE = 65536

class ProtocolError(Exception):
    """協定錯誤"""
    pass

def send_message(sock, message):
    """
    發送訊息（完整處理部分 I/O）

    Args:
        sock: socket 物件
        message: 字串或 bytes

    Raises:
        ProtocolError: 當發送失敗時
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # 1. 將訊息轉成 bytes
        if isinstance(message, str):
            message = message.encode('utf-8')

        # 2. 檢查長度限制
        msg_len = len(message)
        if msg_len > MAX_MESSAGE_SIZE:
            raise ProtocolError(f"訊息過長: {msg_len} bytes (最大 {MAX_MESSAGE_SIZE})")

        logger.info(f"[PROTOCOL] 準備發送 {msg_len} bytes")

        # 3. 建立長度標頭（4 bytes, 網路位元序）
        header = struct.pack('!I', msg_len)

        # 4. 完整發送標頭 + 訊息（處理部分 I/O）
        full_message = header + message
        total_sent = 0

        while total_sent < len(full_message):
            try:
                sent = sock.send(full_message[total_sent:])
                if sent == 0:
                    raise ProtocolError("Socket 連線已關閉")
                total_sent += sent
                logger.info(f"[PROTOCOL] 已發送 {total_sent}/{len(full_message)} bytes")
            except socket.error as e:
                raise ProtocolError(f"發送失敗: {e}")

        logger.info(f"[PROTOCOL] ✅ 完整發送 {total_sent} bytes")

    except Exception as e:
        logger.error(f"[PROTOCOL] ❌ 發送訊息失敗: {e}")
        raise ProtocolError(f"發送訊息時發生錯誤: {e}")


def recv_exact(sock, n):
    """
    接收確切 n bytes（處理部分 I/O）
    
    Args:
        sock: socket 物件
        n: 要接收的位元組數
        
    Returns:
        bytes: 接收到的資料
        
    Raises:
        ProtocolError: 當接收失敗時
    """
    data = b''
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ProtocolError("連線已關閉（recv 回傳空資料）")
            data += chunk
        except socket.timeout:
            raise ProtocolError("接收逾時")
        except socket.error as e:
            raise ProtocolError(f"接收失敗: {e}")
    return data


def recv_message(sock):
    """
    接收一個完整訊息
    
    Args:
        sock: socket 物件
        
    Returns:
        str: 解碼後的訊息
        
    Raises:
        ProtocolError: 當接收失敗或格式錯誤時
    """
    try:
        # 1. 先接收 4 bytes 的長度標頭
        header = recv_exact(sock, 4)
        
        # 2. 解析長度
        msg_len = struct.unpack('!I', header)[0]
        
        # 3. 驗證長度
        if msg_len <= 0:
            raise ProtocolError(f"無效的訊息長度: {msg_len}")
        if msg_len > MAX_MESSAGE_SIZE:
            raise ProtocolError(f"訊息過長: {msg_len} bytes (最大 {MAX_MESSAGE_SIZE})")
        
        # 4. 接收訊息本體
        message = recv_exact(sock, msg_len)
        
        # 5. 解碼為字串
        return message.decode('utf-8')
        
    except UnicodeDecodeError as e:
        raise ProtocolError(f"UTF-8 解碼失敗: {e}")