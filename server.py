import socket
import threading
import signal
import sys
import struct
import time

HOST = "0.0.0.0"
PORT = 8888
online_users = {}  # {用户名: 客户端socket}
is_running = True
lock = threading.Lock()


def handle_client(client_socket, client_addr):
    """处理客户端连接"""
    username = None
    try:
        client_socket.settimeout(5.0)
        username_data = client_socket.recv(1024).decode("utf-8").strip()
        if not username_data:
            raise Exception("未接收到用户名")
        username = username_data

        with lock:
            if username in online_users:
                client_socket.send("用户名已被占用".encode("utf-8"))
                client_socket.close()
                print(f"⚠️ {client_addr} 尝试使用重复用户名：{username}")
                return
            online_users[username] = client_socket

        print(f"✅ {username} 上线 | 地址：{client_addr} | 在线数：{len(online_users)}")
        client_socket.settimeout(300.0)

        while is_running:
            try:
                msg = client_socket.recv(1024).decode("utf-8").strip()
                if not msg:
                    break

                if msg.startswith("image|"):
                    parts = msg.split("|", 2)
                    if len(parts) >= 3:
                        target_user = parts[1]
                        img_filename = parts[2]
                        with lock:
                            if target_user in online_users:
                                online_users[target_user].send(f"image|{username}|{img_filename}".encode("utf-8"))
                                img_size_data = client_socket.recv(4)
                                if len(img_size_data) != 4:
                                    client_socket.send("图片大小数据不完整".encode("utf-8"))
                                    continue
                                online_users[target_user].send(img_size_data)
                                img_size = struct.unpack("!I", img_size_data)[0]

                                client_socket.settimeout(30.0)
                                online_users[target_user].settimeout(30.0)
                                recv_size = 0
                                while recv_size < img_size:
                                    recv_data = client_socket.recv(1024)
                                    if not recv_data:
                                        break
                                    online_users[target_user].send(recv_data)
                                    recv_size += len(recv_data)

                                if recv_size == img_size:
                                    client_socket.send("图片转发成功".encode("utf-8"))
                                else:
                                    client_socket.send("图片转发不完整".encode("utf-8"))
                                print(f"📷 {username} 向 {target_user} 发送图片：{img_filename}")
                            else:
                                client_socket.send(f"{target_user} 不在线/不存在".encode("utf-8"))
                        client_socket.settimeout(300.0)
                        if target_user in online_users:
                            online_users[target_user].settimeout(300.0)
                    continue

                parts = msg.split("|", 2)
                if len(parts) < 3:
                    client_socket.send("消息格式错误（类型|目标|内容）".encode("utf-8"))
                    continue

                msg_type, target, content = parts[0], parts[1], parts[2]

                if msg_type == "text":
                    with lock:
                        if target in online_users:
                            online_users[target].send(f"[{username}] {content}".encode("utf-8"))
                            client_socket.send("消息已发送".encode("utf-8"))
                        else:
                            client_socket.send(f"{target} 不在线/不存在".encode("utf-8"))
                elif msg_type == "friend_req":
                    with lock:
                        if target in online_users:
                            online_users[target].send(f"friend_req|{username}".encode("utf-8"))
                            client_socket.send("好友申请已发送".encode("utf-8"))
                        else:
                            client_socket.send(f"{target} 不在线/不存在".encode("utf-8"))
                elif msg_type == "friend_reply":
                    with lock:
                        if target in online_users:
                            online_users[target].send(f"friend_reply|{username}|{content}".encode("utf-8"))
                        else:
                            client_socket.send(f"{target} 不在线/不存在".encode("utf-8"))
                elif msg_type == "user_query":
                    with lock:
                        online_list = ",".join(online_users.keys())
                    client_socket.send(f"user_list|{online_list}".encode("utf-8"))
                elif msg_type == "offline":
                    break

            except socket.timeout:
                continue
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
        with lock:
            if username in online_users:
                del online_users[username]
        try:
            client_socket.close()
        except:
            pass
        if username:
            print(f"🔌 {username} 下线 | 在线数：{len(online_users)}")
        else:
            print(f"🔌 {client_addr} 下线")


def graceful_exit(signum, frame):
    """优雅退出服务端"""
    global is_running
    print("\n📤 服务端正在退出...")
    is_running = False

    with lock:
        for sock in online_users.values():
            try:
                sock.send("服务端即将关闭，连接断开".encode("utf-8"))
                time.sleep(0.1)
                sock.close()
            except:
                pass
        online_users.clear()

    print("✅ 服务端已安全退出")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(10)
        server_socket.settimeout(1.0)
    except Exception as e:
        print(f"❌ 服务端启动失败：{str(e)}")
        print(f"⚠️ 请检查端口{PORT}是否被占用，或使用管理员权限运行")
        sys.exit(1)

    local_ip = socket.gethostbyname(socket.gethostname())
    print(f"🚀 服务端启动成功 | 局域网IP：{local_ip}:{PORT}")
    print("💡 按 Ctrl+C 优雅退出")
    print("=" * 50)

    while is_running:
        try:
            client_socket, client_addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, client_addr), daemon=True).start()
        except socket.timeout:
            continue
        except Exception as e:
            if is_running:
                print(f"⚠️ 服务端监听异常：{str(e)}")
            continue