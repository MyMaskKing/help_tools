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
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.datetime.now().strftime("%A")
    task_count = len(tasks)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>今日待办任务</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{ 
                font-family: 'Roboto', 'Microsoft YaHei', Arial, sans-serif; 
                line-height: 1.6; 
                color: #333; 
                background-color: #f9f9f9;
                padding: 10px; 
            }}
            
            .container {{ 
                max-width: 800px; 
                margin: 0 auto; 
                background-color: #ffffff;
                border-radius: 10px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            
            .header {{
                background: linear-gradient(135deg, #0078d7, #0053a6);
                color: white;
                padding: 20px;
                position: relative;
            }}
            
            .header h1 {{ 
                margin-bottom: 10px; 
                font-size: 22px;
                font-weight: 500;
            }}
            
            .date-info {{
                display: flex;
                align-items: center;
                margin-bottom: 5px;
                font-size: 14px;
                opacity: 0.9;
            }}
            
            .date-info .dot {{
                display: inline-block;
                margin: 0 8px;
                width: 4px;
                height: 4px;
                border-radius: 50%;
                background-color: rgba(255, 255, 255, 0.6);
                vertical-align: middle;
            }}
            
            .task-summary {{
                background-color: white;
                border-radius: 5px;
                padding: 8px 12px;
                margin-top: 15px;
                display: inline-block;
                font-size: 14px;
                font-weight: 500;
                color: #0078d7;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            
            .content {{
                padding: 20px;
            }}
            
            .no-tasks {{ 
                color: #888; 
                font-style: italic;
                text-align: center;
                padding: 40px 0;
                background-color: #f8f9fa;
                border-radius: 6px;
            }}
            
            .no-tasks i {{
                display: block;
                font-size: 40px;
                margin-bottom: 10px;
                color: #ccc;
            }}
            
            table {{ 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 20px;
                border-radius: 6px;
                overflow: hidden;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
                table-layout: fixed;
            }}
            
            thead {{
                background-color: #f2f7fd;
            }}
            
            th {{ 
                padding: 12px 15px; 
                text-align: left; 
                font-weight: 500;
                color: #0078d7;
                border-bottom: 1px solid #eaeaea;
            }}
            
            td {{ 
                padding: 12px 15px; 
                text-align: left; 
                border-bottom: 1px solid #eaeaea;
                vertical-align: middle;
            }}
            
            tr:last-child td {{
                border-bottom: none;
            }}
            
            tr:hover {{ 
                background-color: #f8f9fa; 
            }}
            
            .task-content {{
                font-weight: 400;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            
            /* 在手机屏幕上允许任务内容在必要时折行 */
            @media (max-width: 600px) {{
                .task-content {{
                    white-space: normal;
                    word-break: break-word;
                }}
                
                .task-content-wrapper {{
                    display: block;
                    max-width: 100%;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }}
                
                table {{
                    font-size: 14px;
                }}
                
                th, td {{
                    padding: 10px;
                }}
                
                .action-col {{
                    width: auto !important;
                }}
                
                a {{
                    padding: 6px 10px !important;
                }}
            }}
            
            .index-col {{
                width: 40px;
                text-align: center;
                color: #888;
                font-weight: 500;
            }}
            
            a {{ 
                color: #0078d7; 
                text-decoration: none;
                padding: 8px 15px;
                background-color: #f0f7ff;
                border-radius: 4px;
                transition: all 0.2s ease;
                display: inline-block;
                font-size: 14px;
                white-space: nowrap;
            }}
            
            a:hover {{ 
                background-color: #e1efff;
                text-decoration: none;
            }}
            
            .action-col {{
                width: 120px;
                text-align: center;
            }}
            
            .footer {{ 
                margin-top: 20px; 
                padding: 15px 0;
                font-size: 13px; 
                color: #888;
                text-align: center;
                border-top: 1px solid #eaeaea;
            }}
            
            .icon {{
                font-size: 16px;
                margin-right: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>今日待办任务</h1>
                <div class="date-info">
                    <span>{today}</span>
                    <span class="dot"></span>
                    <span>{weekday}</span>
                </div>
                <div class="task-summary">
                    共 {task_count} 项待办
                </div>
            </div>
            
            <div class="content">
    """
    
    if not tasks or len(tasks) == 0:
        html += """
                <div class="no-tasks">
                    <i>✓</i>
                    <p>今天没有待办任务，好好休息吧！</p>
                </div>
        """
    else:
        html += """
                <table>
                    <thead>
                        <tr>
                            <th class="index-col">#</th>
                            <th>任务内容</th>
                            <th class="action-col">操作</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for i, task in enumerate(tasks):
            task_name = task.get("task_name", "")
            task_link = task.get("task_link", "")
            
            html += f"""
                        <tr>
                            <td class="index-col">{i+1}</td>
                            <td>
                                <div class="task-content-wrapper">
                                    <span class="task-content">{task_name}</span>
                                </div>
                            </td>
                            <td class="action-col">
            """
            
            if task_link:
                html += f'<a href="{task_link}" target="_blank"><span class="icon">➔</span>查看</a>'
            else:
                html += '<span style="color:#ccc;">无链接</span>'
            
            html += """
                            </td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
        """
    
    html += """
                <div class="footer">
                    <p>此邮件由WPS云文档自动发送，请勿回复。</p>
                </div>
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