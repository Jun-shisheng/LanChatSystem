import socket
import threading
import signal  # 新增：捕获退出信号
import sys  # 新增：退出程序

# 核心配置
HOST = "0.0.0.0"
PORT = 8888
online_users = {}
server_socket = None  # 全局server socket，方便关闭
is_running = True  # 运行标志，控制主循环


# 处理单个客户端
def handle_client(client_socket, client_addr):
    username = None
    try:
        username = client_socket.recv(1024).decode("utf-8")
        if not username or not is_running:
            raise Exception("用户名为空/服务端退出")
        online_users[username] = client_socket
        print(f"✅ {username} ({client_addr}) 上线 | 在线：{list(online_users.keys())}")

        while is_running:  # 用运行标志控制循环
            msg = client_socket.recv(1024).decode("utf-8")
            if not msg:
                break

            try:
                msg_type, target_user, content = msg.split("|", 2)
            except ValueError:
                print(f"❌ 消息格式错误：{msg}")
                client_socket.send("❌ 消息格式错误".encode("utf-8"))
                continue

            # 文字消息
            if msg_type == "text":
                if target_user in online_users:
                    online_users[target_user].send(f"[{username}] {content}".encode("utf-8"))
                else:
                    client_socket.send(f"❌ {target_user} 不在线".encode("utf-8"))
            # 好友申请
            elif msg_type == "friend_req":
                if target_user in online_users:
                    online_users[target_user].send(f"friend_req|{username}".encode("utf-8"))
                    client_socket.send(f"✅ 申请已发送给{target_user}".encode("utf-8"))
                else:
                    client_socket.send(f"❌ {target_user} 不在线".encode("utf-8"))
            # 好友回复
            elif msg_type == "friend_reply":
                if target_user in online_users:
                    online_users[target_user].send(f"friend_reply|{username}|{content}".encode("utf-8"))
                else:
                    client_socket.send(f"❌ {target_user} 不在线".encode("utf-8"))

    except Exception as e:
        print(f"❌ {username if username else client_addr} 异常：{e}")
    finally:
        # 清理客户端连接
        if username in online_users:
            del online_users[username]
        client_socket.close()
        print(f"🔌 {username if username else client_addr} 下线 | 在线：{list(online_users.keys())}")


# 优雅退出函数
def graceful_exit(signum, frame):
    global is_running, server_socket
    print("\n📤 服务端开始优雅退出...")
    is_running = False  # 停止循环

    # 关闭所有客户端连接
    for username, sock in online_users.items():
        sock.close()
        print(f"🔌 关闭{username}连接")

    # 关闭服务端socket
    if server_socket:
        server_socket.close()
        print("✅ 服务端socket已关闭")

    print("✅ 服务端已完全退出")
    sys.exit(0)


# 主函数
def main():
    global server_socket
    # 注册退出信号（Ctrl+C）
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    # 创建server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"🚀 服务端启动：{HOST}:{PORT} | 按Ctrl+C退出")

    # 主循环（用is_running控制）
    while is_running:
        try:
            # 设置超时，避免永久阻塞（关键！）
            server_socket.settimeout(1.0)
            client_socket, client_addr = server_socket.accept()
            # 启动客户端线程（守护线程）
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_addr))
            client_thread.daemon = True
            client_thread.start()
        except socket.timeout:
            continue  # 超时后继续循环，检测is_running
        except Exception as e:
            if is_running:
                print(f"❌ 服务端异常：{e}")


if __name__ == "__main__":
    main()