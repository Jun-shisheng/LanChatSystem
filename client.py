import socket
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import json
import os
import sys
import struct
import time  # 新增：解决文件备份重名

# 基础配置
SERVER_PORT = 8888
client_socket = None
current_username = ""
is_running = True
exit_flag = False  # 新增：退出标记，避免多线程冲突

# 数据存储
chat_records = {}  # {好友/临时用户: [消息列表]}
current_chat_target = ""
friends_list = []  # 正式好友
temp_users = []  # 临时会话用户
FRIENDS_FILE = "friends.json"
CHAT_RECORDS_FILE = "chat_records.json"
image_cache = {}  # 缓存图片对象（防止垃圾回收）

# 图片弹窗窗口
image_popup = None
image_label = None


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
    """初始化文件（修复备份重名）"""
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default_content, f)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
    except:
        # 给备份文件加时间戳，避免重名
        timestamp = int(time.time())
        backup_path = f"{file_path}.bak.{timestamp}"
        if os.path.exists(file_path):
            os.rename(file_path, backup_path)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default_content, f)


# ---------------------- 好友/临时用户管理 ----------------------
def save_friends():
    """保存正式好友列表"""
    if exit_flag:  # 退出时跳过（避免文件操作冲突）
        return
    init_file(FRIENDS_FILE, {})
    with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[current_username] = list(set(friends_list))
    with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_friends():
    """加载正式好友列表"""
    global friends_list
    friends_list = []
    init_file(FRIENDS_FILE, {})
    try:
        with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        friends_list = list(set(data.get(current_username, [])))
        load_chat_records()
        for user in friends_list + temp_users:
            if user not in chat_records:
                chat_records[user] = []
        update_friend_list()
    except:
        friends_list = []


def update_friend_list():
    """更新通讯录UI"""
    friend_listbox.delete(0, tk.END)
    for friend in sorted(friends_list):
        friend_listbox.insert(tk.END, friend)
    for temp_user in sorted(temp_users):
        if temp_user not in friends_list:
            friend_listbox.insert(tk.END, f"{temp_user} (临时)")


# ---------------------- 聊天记录管理 ----------------------
def save_chat_records():
    """保存聊天记录"""
    if exit_flag:  # 退出时跳过
        return
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


# ---------------------- 图片处理 ----------------------
def resize_image(image_path, max_width=150, max_height=150):
    """调整图片大小+缓存"""
    if image_path in image_cache:
        return image_cache[image_path]["img"], image_cache[image_path]["tk_img"]

    img = Image.open(image_path)
    width, height = img.size
    scale = min(max_width / width, max_height / height, 1)
    new_size = (int(width * scale), int(height * scale))
    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
    tk_img = ImageTk.PhotoImage(resized_img)
    image_cache[image_path] = {"img": resized_img, "tk_img": tk_img}
    return resized_img, tk_img


def show_image_popup(image_path):
    """弹窗显示完整图片"""
    global image_popup, image_label
    if image_popup:
        image_popup.destroy()

    image_popup = tk.Toplevel(root)
    image_popup.title("查看图片")
    image_popup.geometry("800x600")
    image_popup.protocol("WM_DELETE_WINDOW", lambda: image_popup.destroy())  # 修复弹窗关闭

    try:
        img = Image.open(image_path)
        max_width = 750
        max_height = 550
        width, height = img.size
        scale = min(max_width / width, max_height / height, 1)
        new_size = (int(width * scale), int(height * scale))
        resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(resized_img)

        image_label = tk.Label(image_popup, image=img_tk)
        image_label.image = img_tk
        image_label.pack(padx=10, pady=10)

        tk.Button(image_popup, text="关闭", command=image_popup.destroy).pack(pady=5)
    except Exception as e:
        messagebox.showerror("错误", f"图片加载失败：{str(e)}")
        image_popup.destroy()


def send_image():
    """发送图片"""
    target = target_entry.get().strip()
    if not target:
        messagebox.showwarning("提示", "请选择目标用户")
        return

    file_path = filedialog.askopenfilename(
        title="选择图片",
        filetypes=[("Image Files", "*.jpg *.jpeg *.png *.gif *.bmp")]
    )
    if not file_path:
        return

    try:
        img_filename = os.path.basename(file_path)
        msg_header = f"image|{target}|{img_filename}"
        client_socket.send(msg_header.encode("utf-8"))

        img_size = os.path.getsize(file_path)
        client_socket.send(struct.pack("!I", img_size))

        client_socket.settimeout(30.0)
        with open(file_path, "rb") as f:
            sent_size = 0
            while sent_size < img_size and not exit_flag:
                send_data = f.read(1024)
                if not send_data:
                    break
                client_socket.send(send_data)
                sent_size += len(send_data)

        resized_img, img_tk = resize_image(file_path)
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, "[我] 发送图片：\n")
        img_index = chat_text.image_create(tk.END, image=img_tk)
        chat_text.insert(tk.END, "\n")
        chat_text.config(state=tk.DISABLED)

        chat_records[target].append(f"[图片]我:{file_path}")
        threading.Thread(target=save_chat_records, daemon=True).start()
        messagebox.showinfo("成功", "图片发送完成")

    except socket.timeout:
        messagebox.showerror("发送失败", "图片传输超时")
    except Exception as e:
        messagebox.showerror("发送失败", f"图片发送失败：{str(e)}")
    finally:
        if not exit_flag:
            client_socket.settimeout(3.0)


def recv_image(img_filename, img_size, sender):
    """接收图片"""
    try:
        if not os.path.exists("recv_images"):
            os.makedirs("recv_images")
        save_path = os.path.join("recv_images", img_filename)

        client_socket.settimeout(30.0)
        with open(save_path, "wb") as f:
            recv_size = 0
            while recv_size < img_size and not exit_flag:
                recv_data = client_socket.recv(1024)
                if not recv_data:
                    break
                f.write(recv_data)
                recv_size += len(recv_data)

        if recv_size != img_size:
            os.remove(save_path)
            messagebox.showerror("接收失败", "图片接收不完整")
            return

        resized_img, img_tk = resize_image(save_path)
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"[{sender}] 发送图片：\n")
        img_index = chat_text.image_create(tk.END, image=img_tk)
        chat_text.insert(tk.END, "\n")
        chat_text.config(state=tk.DISABLED)

        chat_records[sender].append(f"[图片]{sender}:{save_path}")
        threading.Thread(target=save_chat_records, daemon=True).start()

        # 修复图片点击绑定
        tag_name = f"img_{sender}_{len(chat_records[sender]) - 1}"
        img_line_start = chat_text.index(f"end-2l linestart")
        img_line_end = chat_text.index(f"end-1l lineend")
        chat_text.tag_add(tag_name, img_line_start, img_line_end)
        chat_text.tag_bind(tag_name, "<Button-1>", lambda e, p=save_path: show_image_popup(p))

        if sender not in friends_list and sender not in temp_users:
            temp_users.append(sender)
            update_friend_list()

    except socket.timeout:
        messagebox.showerror("接收失败", "图片接收超时")
    except Exception as e:
        messagebox.showerror("接收失败", f"图片接收失败：{str(e)}")
    finally:
        if not exit_flag:
            client_socket.settimeout(3.0)


# ---------------------- 聊天核心功能 ----------------------
def switch_chat_target(target):
    """切换聊天对象"""
    global current_chat_target
    if not target or exit_flag:
        return

    if " (临时)" in target:
        target = target.replace(" (临时)", "")
        if target not in temp_users and target not in friends_list:
            temp_users.append(target)

    current_chat_target = target
    chat_title.config(text=f"当前聊天：{target}")
    target_entry.delete(0, tk.END)
    target_entry.insert(0, target)

    chat_text.config(state=tk.NORMAL)
    chat_text.delete(1.0, tk.END)
    for record in chat_records.get(target, []):
        if record.startswith("[图片]"):
            parts = record.split(":", 1)
            sender = parts[0][4:]
            img_path = parts[1]
            if os.path.exists(img_path):
                chat_text.insert(tk.END, f"[{sender}] 发送图片：\n")
                resized_img, img_tk = resize_image(img_path)
                img_index = chat_text.image_create(tk.END, image=img_tk)
                chat_text.insert(tk.END, "\n")

                tag_name = f"img_load_{len(chat_text.tag_names())}"
                img_line_start = chat_text.index(f"end-2l linestart")
                img_line_end = chat_text.index(f"end-1l lineend")
                chat_text.tag_add(tag_name, img_line_start, img_line_end)
                chat_text.tag_bind(tag_name, "<Button-1>", lambda e, p=img_path: show_image_popup(p))
        else:
            chat_text.insert(tk.END, f"{record}\n")
    chat_text.config(state=tk.DISABLED)


def add_chat_record(sender, content, is_self=False):
    """添加文字记录"""
    if exit_flag:
        return
    msg = f"[我] {content}" if is_self else f"[{sender}] {content}"
    if sender not in chat_records:
        chat_records[sender] = []
    chat_records[sender].append(msg)

    if current_chat_target == sender:
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"{msg}\n")
        chat_text.config(state=tk.DISABLED)

    threading.Thread(target=save_chat_records, daemon=True).start()


def recv_msg():
    """接收消息线程"""
    global friends_list, temp_users
    while is_running and not exit_flag:
        try:
            if not client_socket or exit_flag:
                break
            client_socket.settimeout(3.0)
            msg = client_socket.recv(1024).decode("utf-8").strip()
            if not msg:
                continue

            if msg.startswith("image|"):
                parts = msg.split("|", 2)
                if len(parts) >= 3:
                    sender = parts[1]
                    img_filename = parts[2]
                    img_size_data = client_socket.recv(4)
                    if len(img_size_data) != 4:
                        continue
                    img_size = struct.unpack("!I", img_size_data)[0]
                    recv_image(img_filename, img_size, sender)
                continue

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
            elif msg.startswith("friend_reply|"):
                parts = msg.split("|")
                if len(parts) >= 3:
                    sender = parts[1]
                    res = parts[2]
                    if res == "同意":
                        if sender not in friends_list:
                            friends_list.append(sender)
                            if sender in temp_users:
                                temp_users.remove(sender)
                            save_friends()
                            update_friend_list()
                            messagebox.showinfo("成功", f"{sender} 同意添加你为好友")
                    else:
                        messagebox.showinfo("提示", f"{sender} 拒绝添加你为好友")
            elif msg.startswith("user_list|"):
                online_list = msg.split("|")[1].split(",") if len(msg.split("|")) > 1 else []
                online_list = [x.strip() for x in online_list if x.strip() and x != current_username]
                msg_text = "当前在线用户：\n"
                for user in sorted(online_list):
                    if user in friends_list:
                        msg_text += f"• {user}（好友）\n"
                    else:
                        msg_text += f"• {user}（可发起临时会话）\n"
                messagebox.showinfo("在线用户", msg_text if online_list else "暂无在线用户")
            else:
                if "[" in msg and "]" in msg:
                    sender = msg[1:msg.index("]")]
                    content = msg[msg.index("]") + 2:]
                    if sender not in friends_list and sender not in temp_users:
                        temp_users.append(sender)
                        update_friend_list()
                    add_chat_record(sender, content)
                    switch_chat_target(sender)
                else:
                    chat_text.config(state=tk.NORMAL)
                    chat_text.insert(tk.END, f"{msg}\n")
                    chat_text.config(state=tk.DISABLED)

        except socket.timeout:
            continue
        except ConnectionResetError:
            if is_running and not exit_flag:
                messagebox.showerror("连接错误", "与服务端的连接已断开")
            break
        except Exception as e:
            if is_running and not exit_flag:
                print(f"⚠️ 消息接收异常：{str(e)}")
            break

    if not exit_flag:
        send_btn.config(state=tk.DISABLED)
        add_friend_btn.config(state=tk.DISABLED)
        query_btn.config(state=tk.DISABLED)
        send_img_btn.config(state=tk.DISABLED)


def send_msg():
    """发送文字消息"""
    target = target_entry.get().strip()
    content = input_entry.get().strip()
    if not target or not content:
        messagebox.showwarning("提示", "目标用户和消息内容不能为空")
        return

    if target not in friends_list and target not in temp_users:
        temp_users.append(target)
        update_friend_list()

    switch_chat_target(target)

    try:
        client_socket.send(f"text|{target}|{content}".encode("utf-8"))
        input_entry.delete(0, tk.END)
        add_chat_record(target, content, is_self=True)
    except Exception as e:
        messagebox.showerror("发送失败", f"消息发送失败：{str(e)}")


def connect_server():
    """连接服务端"""
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
        if client_socket:
            client_socket.close()

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(10.0)
        client_socket.connect((server_ip, SERVER_PORT))
        client_socket.send(current_username.encode("utf-8"))

        threading.Thread(target=recv_msg, daemon=True).start()

        connect_btn.config(state=tk.DISABLED)
        send_btn.config(state=tk.NORMAL)
        add_friend_btn.config(state=tk.NORMAL)
        query_btn.config(state=tk.NORMAL)
        send_img_btn.config(state=tk.NORMAL)

        load_friends()
        messagebox.showinfo("成功", "已连接到服务端")
    except socket.timeout:
        messagebox.showerror("连接失败", "连接超时，请检查服务端是否启动")
    except ConnectionRefusedError:
        messagebox.showerror("连接失败", "服务端拒绝连接，请检查IP和端口")
    except Exception as e:
        messagebox.showerror("连接失败", f"连接异常：{str(e)}")


def on_close():
    """修复退出逻辑（优雅退出）"""
    global is_running, exit_flag, client_socket
    if exit_flag:
        return

    if messagebox.askokcancel("退出", "确定要退出吗？"):
        exit_flag = True  # 标记退出，停止所有线程
        is_running = False

        # 关闭图片弹窗
        if image_popup:
            image_popup.destroy()

        # 关闭socket连接
        if client_socket:
            try:
                client_socket.send(f"offline|{current_username}".encode("utf-8"))
                time.sleep(0.1)  # 确保消息发送完成
                client_socket.close()
            except:
                pass

        # 保存数据（非阻塞）
        try:
            save_friends()
            save_chat_records()
        except:
            pass

        # 强制退出
        root.after(100, root.destroy)  # 避免UI卡死
        sys.exit(0)


# ---------------------- UI初始化 ----------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("简易聊天工具（终极版）")
    root.geometry("650x520")
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
                               command=lambda: client_socket.send(
                                   f"friend_req|{target_entry.get().strip()}|apply".encode("utf-8")))
    add_friend_btn.place(x=270, y=38)

    send_img_btn = tk.Button(root, text="发图片", state=tk.DISABLED, command=send_image)
    send_img_btn.place(x=340, y=38)

    # 3. 聊天标题
    chat_title = tk.Label(root, text="当前聊天：未选择好友")
    chat_title.place(x=10, y=70)

    # 4. 聊天框
    chat_text = tk.Text(root, state=tk.DISABLED, width=73, height=18)
    chat_text.place(x=10, y=95)

    # 5. 底部：输入框+发送
    input_entry = tk.Entry(root, width=65)
    input_entry.place(x=10, y=470)

    send_btn = tk.Button(root, text="发送", state=tk.DISABLED, command=send_msg)
    send_btn.place(x=500, y=468)

    # 6. 右侧：通讯录
    tk.Label(root, text="通讯录").place(x=560, y=10)
    friend_listbox = tk.Listbox(root, width=15, height=25)
    friend_listbox.place(x=560, y=35)
    friend_listbox.bind("<<ListboxSelect>>",
                        lambda e: switch_chat_target(friend_listbox.get(friend_listbox.curselection())))

    root.mainloop()