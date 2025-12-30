import socket
import threading
import tkinter as tk
from tkinter import messagebox
import json
import os
from pypinyin import lazy_pinyin
import sys

# 核心配置
SERVER_PORT = 8888
client_socket = None
current_username = ""
is_running = True

# 新增：全局变量声明（解决input_entry引用问题）
input_entry = None  # 消息输入框全局变量
username_entry = None
target_entry = None
chat_text = None
friend_listbox = None
connect_btn = None
send_btn = None
friend_req_btn = None

# 通讯录配置
FRIENDS_FILE = "E:\\LanChatSystem\\friends.json"
friends_list = []


# ---------------------- 自动获取本地IP ----------------------
def get_local_ip():
    """自动获取当前电脑的局域网IPv4地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        try:
            import netifaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr["addr"]
                        if not ip.startswith("127.") and not ip.startswith("169.254."):
                            return ip
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr["addr"]
                        if not ip.startswith("127."):
                            return ip
        except:
            pass
        return "127.0.0.1"


# ---------------------- 通讯录工具函数 ----------------------
def init_friends_file():
    """初始化通讯录文件"""
    if not os.path.exists(FRIENDS_FILE):
        with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def load_friends():
    """加载通讯录（按拼音排序）"""
    global friends_list
    if not os.path.exists(FRIENDS_FILE):
        init_friends_file()
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    friends_list = data.get(current_username, [])
    # 拼音首字母排序
    friends_list = sorted(friends_list, key=lambda x: lazy_pinyin(x)[0][0])
    update_friend_list()


def save_friends():
    """保存通讯录到文件"""
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[current_username] = friends_list
    with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_friend_list():
    """更新通讯录GUI显示"""
    friend_listbox.delete(0, tk.END)
    for friend in friends_list:
        friend_listbox.insert(tk.END, friend)


# ---------------------- 核心功能函数 ----------------------
def recv_msg():
    """接收服务端消息"""
    while is_running:
        try:
            client_socket.settimeout(1.0)
            msg = client_socket.recv(1024).decode("utf-8")
            if msg:
                # 处理好友申请
                if msg.startswith("friend_req|"):
                    req_sender = msg.split("|")[1]
                    res = messagebox.askyesno("好友申请", f"{req_sender} 请求添加你为好友，是否同意？")
                    reply = "同意" if res else "拒绝"
                    client_socket.send(f"friend_reply|{req_sender}|{reply}".encode("utf-8"))
                    # 同意则添加到通讯录
                    if res:
                        if req_sender not in friends_list:
                            friends_list.append(req_sender)
                            friends_list = sorted(friends_list, key=lambda x: lazy_pinyin(x)[0][0])
                            save_friends()
                            update_friend_list()
                            messagebox.showinfo("成功", f"已添加{req_sender}为好友！")
                # 处理好友回复
                elif msg.startswith("friend_reply|"):
                    parts = msg.split("|")
                    reply_sender = parts[1]
                    reply_result = parts[2]
                    if reply_result == "同意":
                        if reply_sender not in friends_list:
                            friends_list.append(reply_sender)
                            friends_list = sorted(friends_list, key=lambda x: lazy_pinyin(x)[0][0])
                            save_friends()
                            update_friend_list()
                            messagebox.showinfo("成功", f"{reply_sender} 同意了你的好友申请！")
                    else:
                        messagebox.showinfo("提示", f"{reply_sender} 拒绝了你的好友申请！")
                # 普通消息/系统提示
                else:
                    chat_text.config(state=tk.NORMAL)
                    chat_text.insert(tk.END, f"{msg}\n")
                    chat_text.config(state=tk.DISABLED)
                    chat_text.see(tk.END)
        except socket.timeout:
            continue
        except Exception as e:
            if is_running:
                messagebox.showerror("错误", f"与服务端断开连接：{e}")
            break


def send_msg():
    """发送文字消息"""
    target_user = target_entry.get().strip()
    content = input_entry.get().strip()
    if not target_user or not content:
        messagebox.warning("提示", "目标用户名和消息内容不能为空！")
        return

    try:
        msg = f"text|{target_user}|{content}"
        client_socket.send(msg.encode("utf-8"))
        input_entry.delete(0, tk.END)
        # 显示自己发送的消息
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"[我] {content}\n")
        chat_text.config(state=tk.DISABLED)
        chat_text.see(tk.END)
    except Exception as e:
        messagebox.showerror("错误", f"消息发送失败：{e}")


def send_friend_req():
    """发起好友申请"""
    target_user = target_entry.get().strip()
    if not target_user or target_user == current_username:
        messagebox.warning("提示", "目标用户名无效！")
        return
    try:
        msg = f"friend_req|{target_user}|apply"
        client_socket.send(msg.encode("utf-8"))
    except Exception as e:
        messagebox.showerror("错误", f"发送好友申请失败：{e}")


def connect_server(server_ip):
    """连接服务端（接收动态IP参数）"""
    global client_socket, current_username
    current_username = username_entry.get().strip()
    if not current_username:
        messagebox.warning("提示", "请输入用户名！")
        return

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_ip, SERVER_PORT))
        client_socket.send(current_username.encode("utf-8"))
        messagebox.showinfo("成功", f"连接服务端 {server_ip}:{SERVER_PORT} 成功！")

        # 启动接收线程
        recv_thread = threading.Thread(target=recv_msg)
        recv_thread.daemon = True
        recv_thread.start()

        # 启用功能按钮
        connect_btn.config(state=tk.DISABLED)
        send_btn.config(state=tk.NORMAL)
        friend_req_btn.config(state=tk.NORMAL)
        # 加载通讯录
        load_friends()
    except Exception as e:
        messagebox.showerror("错误", f"连接服务端 {server_ip}:{SERVER_PORT} 失败：{e}")


# ---------------------- 优雅退出 ----------------------
def on_closing():
    """窗口关闭时的优雅退出"""
    global is_running, client_socket
    if messagebox.askokcancel("退出", "确定要退出吗？"):
        is_running = False
        # 关闭socket连接
        if client_socket:
            try:
                client_socket.close()
                print("✅ 客户端Socket已关闭")
            except:
                pass
        # 销毁窗口并退出
        root.destroy()
        sys.exit(0)


# ---------------------- 图形界面 ----------------------
def main():
    global root

    root = tk.Tk()
    root.title("局域网简易聊天客户端")
    root.geometry("600x500")
    root.resizable(False, False)

    # 绑定窗口关闭事件
    root.protocol("WM_DELETE_WINDOW", on_closing)
    # 初始化通讯录文件
    init_friends_file()

    # 1. 服务端IP输入区（自动填充本地IP）
    tk.Label(root, text="服务端IP：").place(x=20, y=10)
    server_ip_entry = tk.Entry(root, width=20)
    server_ip_entry.insert(0, get_local_ip())  # 默认填充自动识别的IP
    server_ip_entry.place(x=80, y=10)

    # 2. 用户名输入区
    tk.Label(root, text="用户名：").place(x=20, y=40)
    global username_entry
    username_entry = tk.Entry(root, width=20)
    username_entry.place(x=80, y=40)
    # 连接按钮（传服务端IP参数）
    global connect_btn
    connect_btn = tk.Button(root, text="连接服务端", command=lambda: connect_server(server_ip_entry.get().strip()))
    connect_btn.place(x=250, y=38)

    # 3. 目标用户输入区
    tk.Label(root, text="目标用户：").place(x=20, y=80)
    global target_entry
    target_entry = tk.Entry(root, width=20)
    target_entry.place(x=80, y=80)
    # 好友申请按钮
    global friend_req_btn
    friend_req_btn = tk.Button(root, text="发起好友申请", command=send_friend_req, state=tk.DISABLED)
    friend_req_btn.place(x=250, y=78)

    # 4. 聊天记录显示区
    global chat_text
    chat_text = tk.Text(root, state=tk.DISABLED, width=55, height=22)
    chat_text.place(x=20, y=110)

    # 5. 消息输入区
    global input_entry
    input_entry = tk.Entry(root, width=45)
    input_entry.place(x=20, y=450)
    global send_btn
    send_btn = tk.Button(root, text="发送", command=send_msg, state=tk.DISABLED)
    send_btn.place(x=430, y=448)

    # 6. 通讯录显示区（右侧）
    tk.Label(root, text="通讯录（按字母排序）").place(x=480, y=20)
    global friend_listbox
    friend_listbox = tk.Listbox(root, width=18, height=22)
    friend_listbox.place(x=480, y=50)

    # 选中好友自动填充目标用户
    def select_friend(event):
        try:
            selected = friend_listbox.get(friend_listbox.curselection())
            target_entry.delete(0, tk.END)
            target_entry.insert(0, selected)
        except:
            pass

    friend_listbox.bind("<<ListboxSelect>>", select_friend)

    # 启动GUI主循环
    root.mainloop()


if __name__ == "__main__":
    main()