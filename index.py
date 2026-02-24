import smtplib
import time
import threading
from typing import List, Tuple
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

# 线程锁，保证统计数据安全
lock = threading.Lock()
# 全局统计结果
result_stats = {
    "success_count": 0,
    "fail_count": 0,
    "total_sent": 0
}

def read_html_file(file_path: str) -> str | None:
    """读取HTML文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ 找不到HTML文件：{file_path}")
        return None
    except Exception as e:
        print(f"❌ 读取HTML文件失败：{e}")
        return None

def send_single_email(
    sender_email: str,
    sender_auth_code: str,
    receiver_email: str,
    subject: str,
    content: str,
    content_type: str = 'plain',
    smtp_server: str = 'smtp.qq.com',
    smtp_port: int = 465
) -> bool:
    """
    发送单封邮件（原子操作）
    :return: 发送成功返回True，失败返回False
    """
    if not content:
        print(f"❌ 收件人 {receiver_email}：邮件内容为空，跳过发送")
        return False

    try:
        # 构建邮件对象
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email  # 兼容QQ邮箱校验
        msg['To'] = Header(receiver_email, 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')

        # 添加统一的邮件内容
        content_part = MIMEText(content, content_type, 'utf-8')
        msg.attach(content_part)

        # 连接服务器并发送（自动关闭连接）
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_auth_code)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return True
    except smtplib.SMTPException as e:
        print(f"❌ 收件人 {receiver_email}（发件人 {sender_email}）：SMTP错误 - {e}")
        return False
    except Exception as e:
        print(f"❌ 收件人 {receiver_email}（发件人 {sender_email}）：发送失败 - {e}")
        return False

def sender_worker(
    sender_info: Tuple[str, str],
    receivers: List[str],
    repeat_times: int,  # 对每个收件人的重复发送次数
    subject: str,
    content: str,
    content_type: str,
    send_interval: int,  # 同一发件人发送间隔（秒）
    smtp_server: str,
    smtp_port: int
):
    """
    单个发件人的发送线程工作函数
    :param sender_info: 元组(发件人邮箱, 授权码)
    :param receivers: 收件人列表
    :param repeat_times: 对每个收件人的重复发送次数
    """
    sender_email, sender_auth = sender_info
    print(f"\n📧 发件人 {sender_email} 开始工作：需给 {len(receivers)} 个收件人各发送 {repeat_times} 封相同邮件")

    # 遍历每个收件人
    for receiver_idx, receiver in enumerate(receivers):
        # 对单个收件人重复发送指定次数
        for repeat_idx in range(repeat_times):
            # 发送单封邮件
            success = send_single_email(
                sender_email=sender_email,
                sender_auth_code=sender_auth,
                receiver_email=receiver,
                subject=subject,
                content=content,
                content_type=content_type,
                smtp_server=smtp_server,
                smtp_port=smtp_port
            )

            # 线程安全更新统计
            with lock:
                result_stats["total_sent"] += 1
                if success:
                    result_stats["success_count"] += 1
                    print(f"✅ 发件人 {sender_email} | 收件人 {receiver} | 第 {repeat_idx+1}/{repeat_times} 封：发送成功")
                else:
                    result_stats["fail_count"] += 1
                    print(f"❌ 发件人 {sender_email} | 收件人 {receiver} | 第 {repeat_idx+1}/{repeat_times} 封：发送失败")

            # 同一收件人重复发送的间隔（最后一次不等待）
            if repeat_idx < repeat_times - 1:
                time.sleep(send_interval)
        
        # 不同收件人之间的间隔（最后一个收件人不等待）
        if receiver_idx < len(receivers) - 1:
            time.sleep(send_interval)

    print(f"\n📤 发件人 {sender_email} 发送任务完成！")

def batch_repeat_send_emails():
    """主函数：批量配置 + 多线程重复发送相同邮件"""
    print("===== QQ邮箱多线程批量重复发送工具 =====\n")

    # 1. 批量配置发件人（支持多个）
    print("===== 配置发件人（支持多个） =====")
    print("请输入发件人信息（每行格式：邮箱,授权码，输入空行结束）：")
    sender_list = []
    while True:
        sender_input = input("> ").strip()
        if not sender_input:
            break
        if ',' not in sender_input:
            print("❌ 格式错误，请输入：邮箱,授权码")
            continue
        email, auth = sender_input.split(',', 1)
        sender_list.append((email.strip(), auth.strip()))
    
    if not sender_list:
        print("❌ 未配置任何发件人，程序退出")
        return

    # 2. 批量配置收件人
    print("\n===== 配置收件人（支持多个） =====")
    print("请输入收件人邮箱（每行一个，输入空行结束）：")
    receiver_list = []
    while True:
        receiver = input("> ").strip()
        if not receiver:
            break
        if '@' not in receiver:
            print("⚠️ 邮箱格式疑似错误，是否继续添加？(y/n)")
            if input().strip().lower() != 'y':
                continue
        receiver_list.append(receiver)
    
    if not receiver_list:
        print("❌ 未配置任何收件人，程序退出")
        return

    # 3. 配置重复发送次数（对每个收件人）
    while True:
        try:
            repeat_times = int(input("\n===== 配置重复发送次数 =====\n请输入对每个收件人的重复发送次数（≥1）：").strip())
            if repeat_times < 1:
                print("❌ 次数必须≥1，请重新输入")
                continue
            break
        except ValueError:
            print("❌ 请输入有效的数字（如：5）")

    # 4. 配置统一的邮件内容
    print("\n===== 配置统一邮件内容（所有重复邮件内容相同） =====")
    print("请选择邮件内容类型：")
    print("1 - 纯文本内容")
    print("2 - HTML文件内容")
    content_choice = input("输入数字选择（1/2）：").strip()

    content = ""
    content_type = 'plain'
    if content_choice == '2':
        html_path = input("请输入HTML文件绝对路径：").strip()
        content = read_html_file(html_path)
        content_type = 'html'
        if not content:
            print("❌ HTML文件读取失败，切换为纯文本模式")
            content = input("请输入纯文本邮件内容：").strip()
            content_type = 'plain'
    else:
        content = input("请输入纯文本邮件内容：").strip()
    
    if not content:
        print("❌ 邮件内容不能为空，程序退出")
        return

    # 5. 基础配置（主题、SMTP、间隔）
    email_subject = input("\n请输入邮件主题：").strip() or "批量重复发送邮件"
    smtp_server = input("请输入SMTP服务器（默认：smtp.qq.com）：").strip() or "smtp.qq.com"
    try:
        smtp_port = int(input("请输入SMTP端口（默认：465）：").strip() or 465)
    except ValueError:
        smtp_port = 465

    # 配置发送间隔（避免被风控）
    while True:
        try:
            send_interval = int(input("\n请输入发送间隔（秒，建议≥5）：").strip() or 5)
            if send_interval < 0:
                print("❌ 间隔时间不能为负数，默认设为5秒")
                send_interval = 5
            break
        except ValueError:
            print("❌ 请输入有效的数字，默认设为5秒")
            send_interval = 5

    # 6. 启动多线程发送
    print(f"\n===== 开始批量重复发送任务 =====")
    print(f"发件人数量：{len(sender_list)}")
    print(f"收件人数量：{len(receiver_list)}")
    print(f"每个收件人重复发送：{repeat_times} 封")
    print(f"发送间隔：{send_interval} 秒/封")
    print(f"预计总发送量：{len(sender_list) * len(receiver_list) * repeat_times} 封")

    # 重置统计结果
    global result_stats
    result_stats = {"success_count": 0, "fail_count": 0, "total_sent": 0}

    # 创建并启动线程（每个发件人一个线程）
    threads = []
    for sender_info in sender_list:
        thread = threading.Thread(
            target=sender_worker,
            args=(
                sender_info,
                receiver_list,
                repeat_times,
                email_subject,
                content,
                content_type,
                send_interval,
                smtp_server,
                smtp_port
            ),
            name=f"Sender-{sender_info[0]}"
        )
        threads.append(thread)
        thread.start()
        print(f"🚀 线程 {thread.name} 已启动")

    # 等待所有线程完成
    for thread in threads:
        thread.join()
        print(f"🔚 线程 {thread.name} 已结束")

    # 输出最终统计
    print("\n===== 批量重复发送任务全部完成 ======")
    print(f"总发送数量：{result_stats['total_sent']}")
    print(f"成功数量：{result_stats['success_count']}")
    print(f"失败数量：{result_stats['fail_count']}")
    print(f"成功率：{result_stats['success_count']/max(result_stats['total_sent'], 1)*100:.2f}%")

if __name__ == "__main__":
    batch_repeat_send_emails()
    