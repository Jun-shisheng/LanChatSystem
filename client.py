import socket
import threading
import tkinter as tk
from tkinter import messagebox
import json
import os
from pypinyin import lazy_pinyin
import sys  # 新增

# 配置
SERVER_IP = "10.17.157.181"  # 替换为你的IP
SERVER_PORT = 8888
client_socket = None
current_username = ""
is_running = True  # 运行标志

# 通讯录配置
FRIENDS_FILE = "E:\\LanChatSystem\\friends.json"
friends_list = []


# ---------------------- 核心函数 ----------------------
def recv_msg():
    while is_running:
        try:
            # 设置超时，避免阻塞
            client_socket.settimeout(1.0)
            msg = client_socket.recv(1024).decode("utf-8")
            if msg:
                # 处理好友申请
                if msg.startswith("friend_req|"):
                    req_sender = msg.split("|")[1]
                    res = messagebox.askyesno("好友申请", f"{req_sender} 请求加好友？")
                    reply = "同意" if res else "拒绝"
                    client_socket.send(f"friend_reply|{req_sender}|{reply}".encode("utf-8"))
                    if res:
                        if req_sender not in friends_list:
                            friends_list.append(req_sender)
                            friends_list = sorted(friends_list, key=lambda x: lazy_pinyin(x)[0][0])
                            save_friends()
                            update_friend_list()
                            messagebox.showinfo("成功", f"已添加{req_sender}")
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
                            messagebox.showinfo("成功", f"{reply_sender} 同意加好友")
                    else:
                        messagebox.showinfo("提示", f"{reply_sender} 拒绝加好友")
                # 普通消息
                else:
                    chat_text.config(state=tk.NORMAL)
                    chat_text.insert(tk.END, f"{msg}\n")
                    chat_text.config(state=tk.DISABLED)
                    chat_text.see(tk.END)
        except socket.timeout:
            continue
        except Exception as e:
            if is_running:
                messagebox.showerror("错误", f"与服务端断开：{e}")
            break


def send_msg():
    target_user = target_entry.get().strip()
    content = input_entry.get().strip()
    if not target_user or not content:
        messagebox.warning("提示", "目标/内容不能为空！")
        return
    try:
        msg = f"text|{target_user}|{content}"
        client_socket.send(msg.encode("utf-8"))
        input_entry.delete(0, tk.END)
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"[我] {content}\n")
        chat_text.config(state=tk.DISABLED)
        chat_text.see(tk.END)
    except Exception as e:
        messagebox.showerror("错误", f"发送失败：{e}")


def send_friend_req():
    target_user = target_entry.get().strip()
    if not target_user or target_user == current_username:
        messagebox.warning("提示", "目标无效！")
        return
    try:
        client_socket.send(f"friend_req|{target_user}|apply".encode("utf-8"))
    except Exception as e:
        messagebox.showerror("错误", f"申请失败：{e}")


def connect_server():
    global client_socket, current_username
    current_username = username_entry.get().strip()
    if not current_username:
        messagebox.warning("提示", "请输入用户名！")
        return
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((SERVER_IP, SERVER_PORT))
        client_socket.send(current_username.encode("utf-8"))
        messagebox.showinfo("成功", "连接服务端！")

        # 启动接收线程（守护线程）
        recv_thread = threading.Thread(target=recv_msg)
        recv_thread.daemon = True
        recv_thread.start()

        # 启用按钮
        connect_btn.config(state=tk.DISABLED)
        send_btn.config(state=tk.NORMAL)
        friend_req_btn.config(state=tk.NORMAL)
        load_friends()
    except Exception as e:
        messagebox.showerror("错误", f"连接失败：{e}")


# ---------------------- 通讯录函数 ----------------------
def init_friends_file():
    if not os.path.exists(FRIENDS_FILE):
        with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def load_friends():
    global friends_list
    if not os.path.exists(FRIENDS_FILE):
        init_friends_file()
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    friends_list = data.get(current_username, [])
    friends_list = sorted(friends_list, key=lambda x: lazy_pinyin(x)[0][0])
    update_friend_list()


def save_friends():
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[current_username] = friends_list
    with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_friend_list():
    friend_listbox.delete(0, tk.END)
    for f in friends_list:
        friend_listbox.insert(tk.END, f)


def select_friend(event):
    try:
        selected = friend_listbox.get(friend_listbox.curselection())
        target_entry.delete(0, tk.END)
        target_entry.insert(0, selected)
    except:
        pass


# ---------------------- 优雅退出 ----------------------
def on_closing():
    """窗口关闭时的处理函数"""
    global is_running, client_socket
    if messagebox.askokcancel("退出", "确定要退出吗？"):
        is_running = False
        # 关闭socket
        if client_socket:
            try:
                client_socket.close()
                print("✅ 客户端socket已关闭")
            except:
                pass
        # 销毁窗口+退出程序
        root.destroy()
        sys.exit(0)


# ---------------------- GUI ----------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("局域网聊天客户端")
    root.geometry("600x500")
    root.resizable(False, False)

    # 绑定窗口关闭事件（关键！）
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 初始化通讯录
    init_friends_file()

    # 1. 用户名区域
    tk.Label(root, text="用户名：").place(x=20, y=20)
    username_entry = tk.Entry(root, width=20)
    username_entry.place(x=80, y=20)
    connect_btn = tk.Button(root, text="连接服务端", command=connect_server)
    connect_btn.place(x=250, y=18)

    # 2. 目标用户区域
    tk.Label(root, text="目标用户：").place(x=20, y=60)
    target_entry = tk.Entry(root, width=20)
    target_entry.place(x=80, y=60)
    friend_req_btn = tk.Button(root, text="发起好友申请", command=send_friend_req, state=tk.DISABLED)
    friend_req_btn.place(x=250, y=58)

    # 3. 聊天框
    chat_text = tk.Text(root, state=tk.DISABLED, width=55, height=22)
    chat_text.place(x=20, y=90)

    # 4. 输入区域
    input_entry = tk.Entry(root, width=45)
    input_entry.place(x=20, y=450)
    send_btn = tk.Button(root, text="发送", command=send_msg, state=tk.DISABLED)
    send_btn.place(x=430, y=448)

    # 5. 通讯录
    tk.Label(root, text="通讯录（按字母排序）").place(x=480, y=20)
    friend_listbox = tk.Listbox(root, width=18, height=22)
    friend_listbox.place(x=480, y=50)
    friend_listbox.bind("<<ListboxSelect>>", select_friend)

    # 启动主循环
    root.mainloop()