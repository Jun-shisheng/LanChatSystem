import socket
import threading
import tkinter as tk
from tkinter import messagebox
import json
import os
import sys

# 核心配置
SERVER_PORT = 8888
client_socket = None
current_username = ""
is_running = True

# 全局UI变量
root = None
username_entry = None
target_entry = None
input_entry = None
chat_text = None
friend_listbox = None
connect_btn = None
send_btn = None
friend_req_btn = None
query_btn = None
chat_title_label = None  # 新增：聊天对象标题

# 新增：聊天记录管理（按好友存储）
chat_records = {}  # 格式：{好友名: ["消息1", "消息2"]}
current_chat_target = ""  # 当前聊天对象

# 通讯录配置
FRIENDS_FILE = "friends.json"
friends_list = []


# 自动获取本地IP
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"


# 通讯录核心函数
def init_friends_file():
    if not os.path.exists(FRIENDS_FILE):
        with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False)


def load_friends():
    global friends_list, chat_records
    init_friends_file()
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    friends_list = data.get(current_username, [])
    friends_list = sorted(friends_list)
    # 初始化聊天记录（新好友默认空记录）
    for friend in friends_list:
        if friend not in chat_records:
            chat_records[friend] = []
    update_friend_list()


def save_friends():
    init_friends_file()
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[current_username] = friends_list
    with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def update_friend_list():
    friend_listbox.delete(0, tk.END)
    for friend in friends_list:
        friend_listbox.insert(tk.END, friend)


# 新增：切换聊天对象
def switch_chat_target(target_friend):
    global current_chat_target
    # 更新当前聊天对象
    current_chat_target = target_friend
    # 更新标题和目标输入框
    chat_title_label.config(text=f"当前聊天：{target_friend}")
    target_entry.delete(0, tk.END)
    target_entry.insert(0, target_friend)
    # 清空当前聊天框，加载该好友的历史记录
    chat_text.config(state=tk.NORMAL)
    chat_text.delete(1.0, tk.END)
    if target_friend in chat_records:
        for record in chat_records[target_friend]:
            chat_text.insert(tk.END, f"{record}\n")
    chat_text.config(state=tk.DISABLED)
    chat_text.see(tk.END)


# 新增：添加聊天记录
def add_chat_record(sender, content, is_self=False):
    # 格式化消息
    if is_self:
        msg_format = f"[我] {content}"
    else:
        msg_format = f"[{sender}] {content}"

    # 存储到对应好友的聊天记录
    if sender in chat_records:
        chat_records[sender].append(msg_format)
    else:
        chat_records[sender] = [msg_format]

    # 如果当前正在聊这个好友，实时显示
    if current_chat_target == sender:
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"{msg_format}\n")
        chat_text.config(state=tk.DISABLED)
        chat_text.see(tk.END)


# 核心功能函数（修改消息接收逻辑）
def recv_msg():
    global friends_list
    while is_running:
        try:
            client_socket.settimeout(3000.0)
            msg = client_socket.recv(1024).decode("utf-8")
            if msg:
                # 好友申请
                if msg.startswith("friend_req|"):
                    req_sender = msg.split("|")[1]
                    if not isinstance(friends_list, list):
                        friends_list = []
                    if messagebox.askyesno("好友申请", f"{req_sender} 请求加好友？"):
                        client_socket.send(f"friend_reply|{req_sender}|同意".encode("utf-8"))
                        if req_sender not in friends_list:
                            friends_list.append(req_sender)
                            friends_list = sorted(friends_list)
                            chat_records[req_sender] = []  # 初始化新好友聊天记录
                            save_friends()
                            update_friend_list()
                            messagebox.showinfo("成功", f"已添加{req_sender}为好友")
                    else:
                        client_socket.send(f"friend_reply|{req_sender}|拒绝".encode("utf-8"))
                # 好友回复
                elif msg.startswith("friend_reply|"):
                    parts = msg.split("|")
                    sender = parts[1]
                    res = parts[2]
                    if res == "同意":
                        if sender not in friends_list:
                            friends_list.append(sender)
                            friends_list = sorted(friends_list)
                            chat_records[sender] = []  # 初始化新好友聊天记录
                            save_friends()
                            update_friend_list()
                            messagebox.showinfo("成功", f"{sender} 同意加好友")
                    else:
                        messagebox.showinfo("提示", f"{sender} 拒绝加好友")
                # 在线用户查询结果
                elif msg.startswith("user_list|"):
                    online_list = msg.split("|")[1].split(",") if msg.split("|")[1] else []
                    msgbox_text = "当前在线用户：\n" + "\n".join(online_list) if online_list else "暂无在线用户"
                    messagebox.showinfo("在线用户", msgbox_text)
                # 普通消息（按发送方分聊天窗口）
                else:
                    # 解析发送方（格式：[user1] 你好）
                    if msg.startswith("[") and "]" in msg:
                        sender = msg[1:msg.index("]")]
                        content = msg[msg.index("]") + 2:]
                        # 添加到对应好友的聊天记录
                        add_chat_record(sender, content, is_self=False)
                    else:
                        # 系统提示（直接显示）
                        chat_text.config(state=tk.NORMAL)
                        chat_text.insert(tk.END, f"{msg}\n")
                        chat_text.config(state=tk.DISABLED)
                        chat_text.see(tk.END)
        except socket.timeout:
            continue
        except Exception as e:
            if is_running:
                messagebox.showerror("错误", f"连接断开：{e}")
            break


# 发送消息（修改：关联当前聊天对象）
def send_msg():
    target = target_entry.get().strip()
    content = input_entry.get().strip()
    if not target or not content:
        messagebox.warning("提示", "目标/内容不能为空")
        return
    if target not in friends_list:
        messagebox.warning("提示", "仅可向通讯录好友发送消息！")
        return
    try:
        client_socket.send(f"text|{target}|{content}".encode("utf-8"))
        input_entry.delete(0, tk.END)
        # 添加到当前好友的聊天记录
        add_chat_record(target, content, is_self=True)
    except Exception as e:
        messagebox.showerror("错误", f"发送失败：{e}")


# 发起好友申请
def send_friend_req():
    target = target_entry.get().strip()
    if not target or target == current_username:
        messagebox.warning("提示", "目标无效")
        return
    try:
        client_socket.send(f"friend_req|{target}|apply".encode("utf-8"))
    except Exception as e:
        messagebox.showerror("错误", f"申请失败：{e}")


# 查询在线用户
def query_online_users():
    try:
        client_socket.send("user_query|none|none".encode("utf-8"))
    except Exception as e:
        messagebox.showerror("错误", f"查询失败：{e}")


# 连接服务端
def connect_server(server_ip):
    global client_socket, current_username
    current_username = username_entry.get().strip()
    if not current_username:
        messagebox.warning("提示", "请输入用户名")
        return
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_ip, SERVER_PORT))
        client_socket.send(current_username.encode("utf-8"))
        messagebox.showinfo("成功", f"连接 {server_ip}:{SERVER_PORT} 成功")

        # 启动接收线程
        t = threading.Thread(target=recv_msg)
        t.daemon = True
        t.start()

        # 启用功能按钮
        connect_btn.config(state=tk.DISABLED)
        send_btn.config(state=tk.NORMAL)
        friend_req_btn.config(state=tk.NORMAL)
        query_btn.config(state=tk.NORMAL)
        load_friends()
    except Exception as e:
        messagebox.showerror("错误", f"连接失败：{e}")


# 优雅退出
def on_closing():
    if messagebox.askokcancel("退出", "确定退出？"):
        global is_running
        is_running = False
        if client_socket:
            client_socket.close()
        root.destroy()
        sys.exit(0)


# 极简UI（新增聊天切换功能）
def main():
    global root, username_entry, target_entry, input_entry, chat_text, friend_listbox
    global connect_btn, send_btn, friend_req_btn, query_btn, chat_title_label

    # 主窗口
    root = tk.Tk()
    root.title("局域网聊天系统")
    root.geometry("600x480")
    root.resizable(False, False)
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 1. 服务端IP + 用户名（顶部）
    tk.Label(root, text="服务端IP：").place(x=10, y=10)
    server_ip_entry = tk.Entry(root, width=15)
    server_ip_entry.insert(0, get_local_ip())
    server_ip_entry.place(x=70, y=10)

    tk.Label(root, text="用户名：").place(x=200, y=10)
    username_entry = tk.Entry(root, width=15)
    username_entry.place(x=250, y=10)

    connect_btn = tk.Button(root, text="连接", command=lambda: connect_server(server_ip_entry.get().strip()))
    connect_btn.place(x=380, y=8)

    # 2. 目标用户 + 功能按钮（上中）
    tk.Label(root, text="目标用户：").place(x=10, y=40)
    target_entry = tk.Entry(root, width=15)
    target_entry.place(x=70, y=40)

    query_btn = tk.Button(root, text="查在线", command=query_online_users, state=tk.DISABLED)
    query_btn.place(x=200, y=38)

    friend_req_btn = tk.Button(root, text="加好友", command=send_friend_req, state=tk.DISABLED)
    friend_req_btn.place(x=270, y=38)

    # 3. 聊天标题（新增：显示当前聊天对象）
    chat_title_label = tk.Label(root, text="当前聊天：未选择好友", font=("微软雅黑", 10, "bold"))
    chat_title_label.place(x=10, y=70)

    # 4. 聊天框（中间）
    chat_text = tk.Text(root, state=tk.DISABLED, width=68, height=18)
    chat_text.place(x=10, y=95)

    # 5. 输入框 + 发送按钮（底部）
    input_entry = tk.Entry(root, width=60)
    input_entry.place(x=10, y=430)

    send_btn = tk.Button(root, text="发送", command=send_msg, state=tk.DISABLED)
    send_btn.place(x=460, y=428)

    # 6. 通讯录（右侧）
    tk.Label(root, text="通讯录", font=("微软雅黑", 10, "bold")).place(x=510, y=10)
    friend_listbox = tk.Listbox(root, width=12, height=23)
    friend_listbox.place(x=510, y=35)

    # 新增：点击通讯录切换聊天对象
    def select_friend(event):
        try:
            selected_indices = friend_listbox.curselection()
            if selected_indices:
                index = selected_indices[0]  # 修复：curselection()返回元组，用[0]取索引
                selected_friend = friend_listbox.get(index)
                switch_chat_target(selected_friend)
        except Exception as e:
            print(f"切换聊天对象异常：{e}")

    friend_listbox.bind("<<ListboxSelect>>", select_friend)

    root.mainloop()


if __name__ == "__main__":
    main()