import socket
import threading
import tkinter as tk
from tkinter import messagebox
import json
import os
import sys

# 基础配置
SERVER_PORT = 8888
client_socket = None
current_username = ""
is_running = True

# 数据存储
chat_records = {}  # {好友: [消息列表]}
current_chat_target = ""
friends_list = []
FRIENDS_FILE = "friends.json"
CHAT_RECORDS_FILE = "chat_records.json"


def get_local_ip():
    """获取本地IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def init_file(file_path, default_content):
    """初始化文件（不存在则创建，格式错误则重建）"""
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default_content, f)
    # 验证文件格式
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
    except:
        os.rename(file_path, f"{file_path}.bak")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default_content, f)


def save_friends():
    """保存好友列表（去重）"""
    init_file(FRIENDS_FILE, {})
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 去重后保存
    data[current_username] = list(set(friends_list))
    with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_friends():
    """加载好友列表（去重）"""
    global friends_list
    friends_list = []
    init_file(FRIENDS_FILE, {})
    try:
        with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 去重
        friends_list = list(set(data.get(current_username, [])))
        load_chat_records()
        # 初始化新好友的聊天记录
        for friend in friends_list:
            if friend not in chat_records:
                chat_records[friend] = []
        update_friend_list()
    except:
        friends_list = []


def update_friend_list():
    """更新通讯录UI"""
    friend_listbox.delete(0, tk.END)
    for friend in sorted(friends_list):
        friend_listbox.insert(tk.END, friend)


def save_chat_records():
    """保存聊天记录"""
    init_file(CHAT_RECORDS_FILE, {})
    with open(CHAT_RECORDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[current_username] = chat_records
    with open(CHAT_RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_chat_records():
    """加载聊天记录"""
    global chat_records
    chat_records = {}
    init_file(CHAT_RECORDS_FILE, {})
    try:
        with open(CHAT_RECORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        chat_records = data.get(current_username, {})
    except:
        chat_records = {}


def switch_chat_target(target):
    """切换聊天对象"""
    global current_chat_target
    if not target:
        return
    current_chat_target = target
    # 更新标题和目标输入框
    chat_title.config(text=f"当前聊天：{target}")
    target_entry.delete(0, tk.END)
    target_entry.insert(0, target)
    # 加载历史记录
    chat_text.config(state=tk.NORMAL)
    chat_text.delete(1.0, tk.END)
    for msg in chat_records.get(target, []):
        chat_text.insert(tk.END, f"{msg}\n")
    chat_text.config(state=tk.DISABLED)


def add_chat_record(sender, content, is_self=False):
    """添加聊天记录（自动保存）"""
    msg = f"[我] {content}" if is_self else f"[{sender}] {content}"
    # 确保好友的聊天记录存在
    if sender not in chat_records:
        chat_records[sender] = []
    chat_records[sender].append(msg)
    # 实时显示（当前聊天对象）
    if current_chat_target == sender:
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"{msg}\n")
        chat_text.config(state=tk.DISABLED)
    # 异步保存（避免UI卡顿）
    threading.Thread(target=save_chat_records, daemon=True).start()


def recv_msg():
    """接收消息线程（捕获所有异常，避免刷屏）"""
    global friends_list
    while is_running:
        try:
            if not client_socket:
                break
            client_socket.settimeout(3.0)  # 短超时，及时响应退出
            msg = client_socket.recv(1024).decode("utf-8").strip()
            if not msg:
                continue

            # 好友申请
            if msg.startswith("friend_req|"):
                req_user = msg.split("|")[1]
                if messagebox.askyesno("好友申请", f"{req_user} 请求添加你为好友？"):
                    client_socket.send(f"friend_reply|{req_user}|同意".encode("utf-8"))
                    if req_user not in friends_list:
                        friends_list.append(req_user)
                        save_friends()
                        update_friend_list()
                        messagebox.showinfo("成功", f"已添加{req_user}为好友")
                else:
                    client_socket.send(f"friend_reply|{req_user}|拒绝".encode("utf-8"))
            # 好友回复
            elif msg.startswith("friend_reply|"):
                parts = msg.split("|")
                if len(parts) >= 3:
                    sender = parts[1]
                    res = parts[2]
                    if res == "同意":
                        if sender not in friends_list:
                            friends_list.append(sender)
                            save_friends()
                            update_friend_list()
                            messagebox.showinfo("成功", f"{sender} 同意添加你为好友")
                    else:
                        messagebox.showinfo("提示", f"{sender} 拒绝添加你为好友")
            # 在线用户查询结果
            elif msg.startswith("user_list|"):
                online_list = msg.split("|")[1].split(",") if len(msg.split("|")) > 1 else []
                online_list = [x for x in online_list if x.strip()]
                messagebox.showinfo("在线用户", "\n".join(online_list) if online_list else "暂无在线用户")
            # 普通消息
            else:
                if "[" in msg and "]" in msg:
                    sender = msg[1:msg.index("]")]
                    content = msg[msg.index("]") + 2:]
                    add_chat_record(sender, content)
                    switch_chat_target(sender)
                else:
                    # 系统提示
                    chat_text.config(state=tk.NORMAL)
                    chat_text.insert(tk.END, f"{msg}\n")
                    chat_text.config(state=tk.DISABLED)

        except socket.timeout:
            continue  # 超时不报错，继续等待
        except ConnectionResetError:
            if is_running:
                messagebox.showerror("连接错误", "与服务端的连接已断开")
            break
        except Exception as e:
            # 仅在运行中显示关键异常（避免退出后刷屏）
            if is_running:
                print(f"⚠️ 消息接收异常：{str(e)}")
            break
    # 连接断开后禁用按钮
    send_btn.config(state=tk.DISABLED)
    add_friend_btn.config(state=tk.DISABLED)
    query_btn.config(state=tk.DISABLED)


def send_msg():
    """发送消息（验证好友+目标）"""
    target = target_entry.get().strip()
    content = input_entry.get().strip()
    if not target or not content:
        messagebox.showwarning("提示", "目标用户和消息内容不能为空")
        return
    if target not in friends_list:
        messagebox.showerror("错误", "该用户不是你的好友，无法发送消息")
        return

    # 自动切换到目标聊天窗口
    switch_chat_target(target)
    try:
        client_socket.send(f"text|{target}|{content}".encode("utf-8"))
        input_entry.delete(0, tk.END)
        add_chat_record(target, content, is_self=True)
    except Exception as e:
        messagebox.showerror("发送失败", f"消息发送失败：{str(e)}")


def connect_server():
    """连接服务端（验证用户名+IP）"""
    global current_username, client_socket
    current_username = username_entry.get().strip()
    server_ip = server_ip_entry.get().strip()

    if not current_username:
        messagebox.showwarning("提示", "请输入用户名")
        return
    if not server_ip:
        messagebox.showwarning("提示", "请输入服务端IP")
        return

    try:
        # 关闭旧连接（如果存在）
        if client_socket:
            client_socket.close()

        # 创建新连接
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(10.0)  # 连接超时10秒
        client_socket.connect((server_ip, SERVER_PORT))
        client_socket.send(current_username.encode("utf-8"))

        # 启动接收线程
        threading.Thread(target=recv_msg, daemon=True).start()

        # 启用功能按钮
        connect_btn.config(state=tk.DISABLED)
        send_btn.config(state=tk.NORMAL)
        add_friend_btn.config(state=tk.NORMAL)
        query_btn.config(state=tk.NORMAL)

        # 加载本地数据
        load_friends()
        messagebox.showinfo("成功", "已连接到服务端")
    except socket.timeout:
        messagebox.showerror("连接失败", "连接超时，请检查服务端是否启动")
    except ConnectionRefusedError:
        messagebox.showerror("连接失败", "服务端拒绝连接，请检查IP和端口")
    except Exception as e:
        messagebox.showerror("连接失败", f"连接异常：{str(e)}")


def on_close():
    """退出客户端（安全清理）"""
    global is_running
    if messagebox.askokcancel("退出", "确定要退出吗？"):
        is_running = False
        # 主动发送离线通知
        if client_socket:
            try:
                client_socket.send(f"offline|{current_username}".encode("utf-8"))
                client_socket.close()
            except:
                pass
        # 保存本地数据
        save_friends()
        save_chat_records()
        # 关闭窗口
        root.destroy()
        sys.exit(0)


# ===================== UI初始化 =====================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("简易聊天工具")
    root.geometry("600x480")
    root.resizable(False, False)
    root.protocol("WM_DELETE_WINDOW", on_close)

    # 1. 顶部：IP+用户名
    tk.Label(root, text="服务端IP：").place(x=10, y=10)
    server_ip_entry = tk.Entry(root, width=15)
    server_ip_entry.insert(0, get_local_ip())
    server_ip_entry.place(x=70, y=10)

    tk.Label(root, text="用户名：").place(x=200, y=10)
    username_entry = tk.Entry(root, width=15)
    username_entry.place(x=250, y=10)

    connect_btn = tk.Button(root, text="连接", command=connect_server)
    connect_btn.place(x=380, y=8)

    # 2. 中部：目标用户+功能按钮
    tk.Label(root, text="目标用户：").place(x=10, y=40)
    target_entry = tk.Entry(root, width=15)
    target_entry.place(x=70, y=40)

    query_btn = tk.Button(root, text="查在线", state=tk.DISABLED,
                          command=lambda: client_socket.send("user_query|none|none".encode("utf-8")))
    query_btn.place(x=200, y=38)

    add_friend_btn = tk.Button(root, text="加好友", state=tk.DISABLED,
                               command=lambda: client_socket.send(f"friend_req|{target_entry.get().strip()}|apply".encode("utf-8")))
    add_friend_btn.place(x=270, y=38)

    # 3. 聊天标题
    chat_title = tk.Label(root, text="当前聊天：未选择好友")
    chat_title.place(x=10, y=70)

    # 4. 聊天框
    chat_text = tk.Text(root, state=tk.DISABLED, width=68, height=18)
    chat_text.place(x=10, y=95)

    # 5. 底部：输入框+发送
    input_entry = tk.Entry(root, width=60)
    input_entry.place(x=10, y=430)

    send_btn = tk.Button(root, text="发送", state=tk.DISABLED, command=send_msg)
    send_btn.place(x=460, y=428)

    # 6. 右侧：通讯录
    tk.Label(root, text="通讯录").place(x=510, y=10)
    friend_listbox = tk.Listbox(root, width=12, height=23)
    friend_listbox.place(x=510, y=35)
    # 点击通讯录切换聊天
    friend_listbox.bind("<<ListboxSelect>>",
                        lambda e: switch_chat_target(friend_listbox.get(friend_listbox.curselection())))

    root.mainloop()