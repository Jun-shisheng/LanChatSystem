import socket
import threading
import signal
import sys

# 核心配置
HOST = "0.0.0.0"
PORT = 8888
online_users = {}
server_socket = None
is_running = True

# 自动获取本地IP（极简版）
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"

# 客户端处理（新增在线查询+严格转发）
def handle_client(client_socket, client_addr):
    username = None
    try:
        client_socket.settimeout(3000.0)
        username = client_socket.recv(1024).decode("utf-8")
        if not username or not is_running:
            raise Exception("无效用户名")

        online_users[username] = client_socket
        # 新增：显示完整IP+端口
        print(f"✅ {username} 上线 | 客户端地址：{client_addr} | 在线：{list(online_users.keys())}")

        while is_running:
            msg = client_socket.recv(1024).decode("utf-8")
            if not msg:
                break

            # 解析消息：类型|目标|内容
            try:
                msg_type, target_user, content = msg.split("|", 2)
            except ValueError:
                client_socket.send("❌ 消息格式错误".encode("utf-8"))
                continue

            # 1. 文字消息（仅转发给在线用户）
            if msg_type == "text":
                if target_user in online_users:
                    online_users[target_user].send(f"[{username}] {content}".encode("utf-8"))
                else:
                    client_socket.send(f"❌ {target_user} 不在线/不存在".encode("utf-8"))
            # 2. 好友申请
            elif msg_type == "friend_req":
                if target_user in online_users:
                    online_users[target_user].send(f"friend_req|{username}".encode("utf-8"))
                    client_socket.send(f"✅ 申请已发送给{target_user}".encode("utf-8"))
                else:
                    client_socket.send(f"❌ {target_user} 不在线/不存在".encode("utf-8"))
            # 3. 好友回复
            elif msg_type == "friend_reply":
                if target_user in online_users:
                    online_users[target_user].send(f"friend_reply|{username}|{content}".encode("utf-8"))
                else:
                    client_socket.send(f"❌ {target_user} 不在线/不存在".encode("utf-8"))
            # 4. 在线用户查询
            elif msg_type == "user_query":
                online_list = ",".join(online_users.keys())
                client_socket.send(f"user_list|{online_list}".encode("utf-8"))

    except Exception as e:
        if is_running:
            print(f"❌ {username or client_addr} 异常：{e}")
    finally:
        if username in online_users:
            del online_users[username]
        client_socket.close()
        print(f"🔌 {username or client_addr} 下线 | 在线：{list(online_users.keys())}")

# 优雅退出
def graceful_exit(signum, frame):
    global is_running
    print("\n📤 服务端退出中...")
    is_running = False
    # 关闭所有连接
    for sock in online_users.values():
        sock.close()
    if server_socket:
        server_socket.close()
    print("✅ 服务端已退出")
    sys.exit(0)

# 主函数（修复Ctrl+C）
def main():
    global server_socket
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    local_ip = get_local_ip()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"🚀 服务端启动 | 局域网IP：{local_ip}:{PORT}")
    print("💡 按Ctrl+C退出")

    while is_running:
        try:
            server_socket.settimeout(1.0)
            client_socket, client_addr = server_socket.accept()
            t = threading.Thread(target=handle_client, args=(client_socket, client_addr))
            t.daemon = True
            t.start()
        except socket.timeout:
            continue
        except Exception as e:
            if is_running:
                print(f"❌ 服务端异常：{e}")

if __name__ == "__main__":
    main()