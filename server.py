import socket
import threading
import signal
import sys

HOST = "0.0.0.0"
PORT = 8888
online_users = {}  # 在线用户：{用户名: 客户端socket}
is_running = True
lock = threading.Lock()  # 线程安全锁


def handle_client(client_socket, client_addr):
    """处理单个客户端连接（彻底解决连接异常）"""
    username = None
    try:
        # 1. 接收用户名（设置超时，避免阻塞）
        client_socket.settimeout(5.0)  # 5秒内未发送用户名则断开
        username_data = client_socket.recv(1024).decode("utf-8").strip()
        if not username_data:
            raise Exception("未接收到用户名")
        username = username_data

        # 2. 检查用户名是否重复
        with lock:
            if username in online_users:
                client_socket.send("用户名已被占用".encode("utf-8"))
                client_socket.close()
                print(f"⚠️ {client_addr} 尝试使用重复用户名：{username}")
                return
            online_users[username] = client_socket

        print(f"✅ {username} 上线 | 地址：{client_addr} | 在线数：{len(online_users)}")
        client_socket.settimeout(300.0)  # 5分钟空闲超时

        # 3. 消息循环（捕获连接异常后直接退出）
        while is_running:
            try:
                msg = client_socket.recv(1024).decode("utf-8").strip()
                if not msg:
                    break  # 客户端主动断开

                # 解析消息
                parts = msg.split("|", 2)
                if len(parts) < 3:
                    client_socket.send("消息格式错误（类型|目标|内容）".encode("utf-8"))
                    continue

                msg_type, target, content = parts[0], parts[1], parts[2]

                # 文字消息
                if msg_type == "text":
                    with lock:
                        if target in online_users:
                            online_users[target].send(f"[{username}] {content}".encode("utf-8"))
                            client_socket.send("消息已发送".encode("utf-8"))
                        else:
                            client_socket.send(f"{target} 不在线/不存在".encode("utf-8"))
                # 好友申请
                elif msg_type == "friend_req":
                    with lock:
                        if target in online_users:
                            online_users[target].send(f"friend_req|{username}".encode("utf-8"))
                            client_socket.send("好友申请已发送".encode("utf-8"))
                        else:
                            client_socket.send(f"{target} 不在线/不存在".encode("utf-8"))
                # 好友回复
                elif msg_type == "friend_reply":
                    with lock:
                        if target in online_users:
                            online_users[target].send(f"friend_reply|{username}|{content}".encode("utf-8"))
                        else:
                            client_socket.send(f"{target} 不在线/不存在".encode("utf-8"))
                # 在线查询
                elif msg_type == "user_query":
                    with lock:
                        online_list = ",".join(online_users.keys())
                    client_socket.send(f"user_list|{online_list}".encode("utf-8"))
                # 离线通知
                elif msg_type == "offline":
                    break  # 收到离线通知，主动退出循环

            except socket.timeout:
                continue  # 空闲超时，继续等待
            except ConnectionResetError:
                print(f"🔌 {username} 连接被客户端重置")
                break
            except Exception as e:
                print(f"⚠️ {username} 消息处理异常：{str(e)}")
                break

    except socket.timeout:
        print(f"⏱️ {client_addr} 用户名接收超时")
    except Exception as e:
        print(f"❌ {client_addr} 连接初始化异常：{str(e)}")
    finally:
        # 强制清理在线用户（无论任何异常）
        with lock:
            if username in online_users:
                del online_users[username]
        # 关闭客户端socket
        try:
            client_socket.close()
        except:
            pass
        # 仅在有用户名时打印下线信息
        if username:
            print(f"🔌 {username} 下线 | 在线数：{len(online_users)}")
        else:
            print(f"🔌 {client_addr} 下线")


def graceful_exit(signum, frame):
    """优雅退出服务端"""
    global is_running
    print("\n📤 服务端正在退出...")
    is_running = False

    # 关闭所有在线客户端
    with lock:
        for sock in online_users.values():
            try:
                sock.send("服务端即将关闭，连接断开".encode("utf-8"))
                sock.close()
            except:
                pass
        online_users.clear()

    print("✅ 服务端已安全退出")
    sys.exit(0)


if __name__ == "__main__":
    # 注册信号处理（Ctrl+C退出）
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    # 创建服务端socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 允许端口复用
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)   # 开启保活

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(10)  # 最大同时监听10个连接
        server_socket.settimeout(1.0)  # 非阻塞监听
    except Exception as e:
        print(f"❌ 服务端启动失败：{str(e)}")
        print(f"⚠️ 请检查端口{PORT}是否被占用，或使用管理员权限运行")
        sys.exit(1)

    # 获取本地IP
    local_ip = socket.gethostbyname(socket.gethostname())
    print(f"🚀 服务端启动成功 | 局域网IP：{local_ip}:{PORT}")
    print("💡 按 Ctrl+C 优雅退出")
    print("=" * 50)

    # 主循环（接受客户端连接）
    while is_running:
        try:
            client_socket, client_addr = server_socket.accept()
            # 启动客户端处理线程
            threading.Thread(target=handle_client, args=(client_socket, client_addr), daemon=True).start()
        except socket.timeout:
            continue  # 监听超时，继续循环
        except Exception as e:
            if is_running:
                print(f"⚠️ 服务端监听异常：{str(e)}")
            continue