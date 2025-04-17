#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import datetime
import requests
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_html_content(tasks):
    """
    生成HTML邮件内容
    :param tasks: 任务列表
    :return: HTML内容
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>今日待办任务</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #0078d7; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
            .no-tasks { color: #888; font-style: italic; }
            a { color: #0078d7; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .footer { margin-top: 30px; font-size: 12px; color: #888; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>今日待办任务</h1>
            <p>日期: """ + datetime.datetime.now().strftime("%Y-%m-%d") + """</p>
    """
    
    if not tasks or len(tasks) == 0:
        html += """
            <p class="no-tasks">今天没有待办任务，好好休息吧！</p>
        """
    else:
        html += """
            <table>
                <tr>
                    <th>序号</th>
                    <th>任务内容</th>
                    <th>操作</th>
                </tr>
        """
        
        for i, task in enumerate(tasks):
            task_name = task.get("task_name", "")
            task_link = task.get("task_link", "")
            
            html += f"""
                <tr>
                    <td>{i+1}</td>
                    <td>{task_name}</td>
                    <td>
            """
            
            if task_link:
                html += f'<a href="{task_link}" target="_blank">查看详情</a>'
            
            html += """
                    </td>
                </tr>
            """
        
        html += """
            </table>
        """
    
    html += """
            <div class="footer">
                <p>此邮件由WPS云文档自动发送，请勿回复。</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def send_mail_post(email_content, mail_subject, to_addr, mail_url="https://hook.us2.make.com/q038hvl170pplyjjw7of4n4ugj4v85ik"):
    """
    通过HTTP POST请求发送邮件
    :param email_content: 邮件HTML内容
    :param mail_subject: 邮件主题
    :param to_addr: 收件人地址
    :param mail_url: 邮件服务URL
    :return: 是否发送成功
    """
    try:
        # 构建邮件数据
        mail_data = {
            "subject": mail_subject,
            "content": email_content,
            "to": to_addr,
            "contentType": "text/html"
        }
        
        # 发送请求
        response = requests.post(
            mail_url,
            json=mail_data,
            headers={
                "Content-Type": "application/json"
            }
        )
        
        # 检查响应
        if response.status_code == 200:
            logger.info(f"邮件发送成功: {mail_subject}")
            return True
        else:
            logger.error(f"邮件发送失败，状态码: {response.status_code}, 响应: {response.text}")
            return False
    except Exception as e:
        logger.error(f"邮件发送出错: {str(e)}")
        return False

def main():
    """主函数"""
    try:
        # 获取今天日期
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 构建查询条件 - 使用DBT函数的条件格式
        query_conditions = {
            "mode": "AND",
            "criteria": [
                {
                    "field": "日期",
                    "op": "Equals",
                    "values": [
                        {
                            "dynamicType": "today",
                            "type": "DynamicSimple"
                        }
                    ]
                },
                {
                    "field": "任务标识",
                    "op": "Equals",
                    "values": ["1"]
                },
                {
                    "field": "完成状态",
                    "op": "Equals",
                    "values": ["0"]  # 使用0表示False，根据WPS文档的说明
                }
            ]
        }
        
        # 在WPS脚本环境中，直接使用dbt函数查询数据
        logger.info("开始查询数据表记录")
        records_df = dbt(condition=query_conditions)
        
        # 提取任务信息
        task_field_name = "今天要做什么事"
        task_link_field = "当前数据的链接"
        
        tasks = []
        # 遍历DataFrame的行，提取任务信息
        for index, row in records_df.iterrows():
            task = {
                "task_name": row.get(task_field_name, ""),
                "task_link": row.get(task_link_field, "")
            }
            tasks.append(task)
        
        logger.info(f"查询到{len(tasks)}条待办任务")
        
        # 生成HTML内容
        html_content = generate_html_content(tasks)
        
        # 发送邮件
        subject = f"【今日待办任务】{today} - 共{len(tasks)}项"
        result = send_mail_post(
            html_content,
            subject,
            "your_email@163.com"  # 使用你的实际收件人邮箱
        )
        
        if result:
            logger.info(f"邮件发送成功，共{len(tasks)}项任务")
        else:
            logger.error("邮件发送失败")
    except Exception as e:
        logger.error(f"执行过程中出错: {str(e)}")

if __name__ == "__main__":
    main() 