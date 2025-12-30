import socket
import threading
import signal
import sys

# 核心配置
HOST = "0.0.0.0"  # 监听所有网卡
PORT = 8888
online_users = {}  # {用户名: 客户端套接字}
server_socket = None
is_running = True  # 运行标志，控制主循环


# ---------------------- 自动获取本地IP ----------------------
def get_local_ip():
    """自动获取当前电脑的局域网IPv4地址（兼容所有网络环境）"""
    try:
        # 方案1：通过UDP连接公网DNS获取（优先）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        # 方案2：遍历网卡（备用，无需依赖netifaces）
        local_ip = "127.0.0.1"
        try:
            # 遍历所有可用网卡
            for addr in socket.getaddrinfo(socket.gethostname(), None):
                ip = addr[4][0]
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    local_ip = ip
                    break
        except:
            pass
        return local_ip


# ---------------------- 客户端连接处理 ----------------------
def handle_client(client_socket, client_addr):
    """处理单个客户端的消息交互"""
    username = None
    try:
        # 设置客户端socket超时，避免recv阻塞
        client_socket.settimeout(1.0)

        # 接收客户端用户名
        username = client_socket.recv(1024).decode("utf-8")
        if not username or not is_running:
            raise Exception("用户名为空或服务端已退出")

        # 记录在线用户
        online_users[username] = client_socket
        print(f"✅ {username} ({client_addr}) 上线 | 在线用户：{list(online_users.keys())}")

        # 持续处理客户端消息
        while is_running:
            try:
                msg = client_socket.recv(1024).decode("utf-8")
                if not msg:
                    break  # 客户端断开连接

                # 解析消息：类型|目标|内容
                try:
                    msg_type, target_user, content = msg.split("|", 2)
                except ValueError:
                    err_msg = "❌ 消息格式错误（正确格式：类型|目标|内容）"
                    client_socket.send(err_msg.encode("utf-8"))
                    print(f"❌ {username} 消息格式错误：{msg}")
                    continue

                # 文字消息转发
                if msg_type == "text":
                    if target_user in online_users:
                        online_users[target_user].send(f"[{username}] {content}".encode("utf-8"))
                        print(f"📤 转发消息：{username} → {target_user}：{content}")
                    else:
                        client_socket.send(f"❌ 发送失败：{target_user} 不在线".encode("utf-8"))

                # 好友申请转发
                elif msg_type == "friend_req":
                    if target_user in online_users:
                        online_users[target_user].send(f"friend_req|{username}".encode("utf-8"))
                        client_socket.send(f"✅ 好友申请已发送给{target_user}".encode("utf-8"))
                        print(f"📤 转发好友申请：{username} → {target_user}")
                    else:
                        client_socket.send(f"❌ 好友申请失败：{target_user} 不在线".encode("utf-8"))

                # 好友回复转发
                elif msg_type == "friend_reply":
                    if target_user in online_users:
                        online_users[target_user].send(f"friend_reply|{username}|{content}".encode("utf-8"))
                        print(f"📤 转发好友回复：{username} → {target_user}：{content}")
                    else:
                        client_socket.send(f"❌ 好友回复失败：{target_user} 不在线".encode("utf-8"))

            except socket.timeout:
                continue  # 超时后继续循环，检测is_running
            except Exception as e:
                print(f"❌ {username} 消息处理异常：{e}")
                break

    except Exception as e:
        if is_running:
            print(f"❌ {username if username else client_addr} 连接异常：{e}")
    finally:
        # 清理客户端连接
        if username in online_users:
            del online_users[username]
        try:
            client_socket.close()
        except:
            pass
        print(f"🔌 {username if username else client_addr} 下线 | 在线用户：{list(online_users.keys())}")


# ---------------------- 优雅退出处理 ----------------------
def graceful_exit(signum, frame):
    """捕获Ctrl+C信号，优雅退出服务端"""
    global is_running, server_socket
    print("\n📤 服务端开始优雅退出...")
    is_running = False  # 停止所有循环

    # 关闭所有客户端连接
    for username, sock in list(online_users.items()):
        try:
            sock.send("⚠️ 服务端已关闭，连接即将断开".encode("utf-8"))
            sock.close()
            print(f"🔌 已关闭 {username} 连接")
        except:
            pass

    # 关闭服务端socket
    if server_socket:
        try:
            server_socket.close()
            print("✅ 服务端Socket已关闭")
        except:
            pass

    print("✅ 服务端已完全退出")
    sys.exit(0)


# ---------------------- 主函数（核心修复Ctrl+C） ----------------------
def main():
    global server_socket
    # 注册退出信号（Ctrl+C/SIGINT、系统终止/SIGTERM）
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    # 自动获取本地局域网IP
    local_ip = get_local_ip()
    print(f"📌 自动识别当前局域网IP：{local_ip}")

    # 创建服务端Socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 端口复用：避免重启服务端时端口占用
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)  # 最大监听5个连接
    print(f"🚀 服务端启动成功 | 监听地址：{HOST}:{PORT} | 局域网访问地址：{local_ip}:{PORT}")
    print("💡 按Ctrl+C可优雅退出服务端")

    # 主循环（修复Ctrl+C无响应：强制每次循环设置超时）
    while is_running:
        try:
            # 关键：强制设置1秒超时，让accept()不永久阻塞
            server_socket.settimeout(1.0)
            client_socket, client_addr = server_socket.accept()
            # 为每个客户端启动独立守护线程
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_addr))
            client_thread.daemon = True  # 主线程退出时子线程自动退出
            client_thread.start()
        except socket.timeout:
            continue  # 超时后继续循环，检测is_running状态
        except Exception as e:
            if is_running:
                print(f"❌ 服务端异常：{e}")


if __name__ == "__main__":
    main()