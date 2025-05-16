#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import requests

def generate_html_content(data_df, title="今日待办任务", display_fields=None, additional_note=None):
    """
    根据数据动态生成HTML邮件内容
    :param data_df: 数据DataFrame
    :param title: 邮件标题
    :param display_fields: 需要显示的字段列表，如果为None则显示所有字段
    :param additional_note: 补充说明内容，支持HTML格式
    :return: HTML内容
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 将英文星期转换为中文格式
    weekday_num = datetime.datetime.now().weekday()
    weekday_map = {
        0: "周一",
        1: "周二", 
        2: "周三",
        3: "周四",
        4: "周五",
        5: "周六",
        6: "周日"
    }
    weekday = weekday_map[weekday_num]
    
    # 如果没有指定显示字段，则使用所有字段
    if display_fields is None:
        display_fields = list(data_df.columns)
    
    # 确保所有指定的字段都存在于DataFrame中
    valid_fields = [field for field in display_fields if field in data_df.columns]
    
    task_count = len(data_df)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
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
            
            .cell-content {{
                font-weight: 400;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            
            /* 在手机屏幕上允许内容在必要时折行 */
            @media (max-width: 600px) {{
                .cell-content {{
                    white-space: normal;
                    word-break: break-word;
                }}
                
                .cell-wrapper {{
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
            
            /* 补充说明区域样式 */
            .additional-note {{
                margin-top: 30px;
                padding: 15px 20px;
                background-color: #f8f9fa;
                border-radius: 8px;
                border-left: 4px solid #0078d7;
            }}
            
            .additional-note a {{
                display: inline;
                padding: 0;
                background: none;
                color: #0078d7;
                font-weight: 500;
                text-decoration: underline;
            }}
            
            .additional-note a:hover {{
                text-decoration: underline;
                background: none;
                opacity: 0.8;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
                <div class="date-info">
                    <span>{today}</span>
                    <span class="dot"></span>
                    <span>{weekday}</span>
                </div>
                <div class="task-summary">
                    共 {task_count} 项数据
                </div>
            </div>
            
            <div class="content">
    """
    
    if task_count == 0:
        html += """
                <div class="no-tasks">
                    <i>✓</i>
                    <p>没有数据，好好休息吧！</p>
                </div>
        """
    else:
        html += """
                <table>
                    <thead>
                        <tr>
                            <th class="index-col">#</th>
        """
        
        # 添加表头
        for field in valid_fields:
            html += f'<th>{field}</th>'
        
        html += """
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # 添加表格内容
        for i, (_, row) in enumerate(data_df.iterrows()):
            html += f"""
                        <tr>
                            <td class="index-col">{i+1}</td>
            """
            
            for field in valid_fields:
                value = str(row.get(field, ""))
                html += f"""
                            <td>
                                <div class="cell-wrapper">
                                    <span class="cell-content">{value}</span>
                                </div>
                            </td>
                """
            
            html += """
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
        """
    
    # 添加补充说明区域（如果有的话）
    if additional_note:
        html += f"""
                <div class="additional-note">
                    {additional_note}
                </div>
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

def send_mail(content, subject, to_addr, mail_url="https://hook.us2.make.com/q038hvl170pplyjjw7of4n4ugj4v85ik"):
    """
    通过HTTP POST请求发送邮件
    :param content: 邮件HTML内容
    :param subject: 邮件主题
    :param to_addr: 收件人地址
    :param mail_url: 邮件服务URL
    :return: 是否发送成功
    """
    try:
        # 构建邮件数据
        mail_data = {
            "subject": subject,
            "content": content,
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
            print(f"邮件发送成功: {subject}")
            return True
        else:
            print(f"邮件发送失败，状态码: {response.status_code}, 响应: {response.text}")
            return False
    except Exception as e:
        print(f"邮件发送出错: {str(e)}")
        return False

def build_query_condition(conditions):
    """
    构建查询条件
    :param conditions: 条件列表，每个条件是一个字典，包含field、op和values字段
    :return: 查询条件字典
    """
    return {
        "mode": "AND",
        "criteria": conditions
    }

def main():
    """主函数"""
    try:
        # 获取今天日期
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # ============ 这里定义查询条件 ============
        # 示例：查询今日待办任务
        conditions = [
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
                "values": ["0"]  # 使用0表示False
            }
        ]
        
        # 构建查询条件
        query_conditions = build_query_condition(conditions)
        
        # 在WPS脚本环境中，直接使用dbt函数查询数据
        print("开始查询数据表记录")
        records_df = dbt(sheet_name="成功日记(数据表)",condition=query_conditions)
        
        # ============ 这里定义显示哪些字段 ============
        # 如果为None，则显示所有字段
        display_fields = ["今天要做什么事"]  # 只显示任务内容
        
        # ============ 这里定义邮件标题 ============
        email_title = "今日待办任务"
        
        # ============ 这里定义补充说明内容 ============
        # 如果不需要补充说明，设置为None
        additional_note = """
        <p>➡️如果您今天还没有写成功日记的话，快去添加吧！</p>
        <p>⭐你应该72小时内完成你想做的的，否则就会失去做的斗志！</p>
        <br>
        <p>📋<a href="https://web.wps.cn/wo/sl/v317YHKz?app_id=1Cdn5GV4vlkQfZ2SbnB32v" target="_blank">添加成功日记</a></p>
        <p>🎊<a href="https://web.wps.cn/wo/sl/v36Eucp?app_id=3dYIUhHwuh1ig7XqGoB2fg" target="_blank">日记视图</a></p>
        <p>☄️<a href="https://www.kdocs.cn/wo/sl/v11ogNz0" target="_blank">日记仪表盘</a></p>
        """
        
        # 生成HTML内容
        html_content = generate_html_content(
            records_df, 
            title=email_title,
            display_fields=display_fields,
            additional_note=additional_note
        )
        
        # 发送邮件
        subject = f"【{email_title}】{today} - 共{len(records_df)}项"
        result = send_mail(
            html_content,
            subject,
            "your_email@163.com"  # 使用你的实际收件人邮箱
        )
        
        if result:
            print(f"邮件发送成功，共{len(records_df)}项数据")
        else:
            print("邮件发送失败")
    except Exception as e:
        print(f"执行过程中出错: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main() 