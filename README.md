# 开发工具合集

这是一个包含多个实用开发工具的集合项目。每个工具都是独立的，可以根据需要单独使用。

## 项目结构

```
.
├── .cursor/                # Cursor IDE配置
│   └── rules/             # Cursor规则文件
├── wps/                   # WPS任务邮件提醒工具
│   ├── README.md         # 工具说明文档
│   └── 官方文档.md        # WPS API文档
├── ClashVerge/           # ClashVerge代理组管理工具
│   ├── README.md         # 工具说明文档
│   └── add_proxy_group.js # 代理组配置脚本
├── config.json           # 全局配置文件
└── design.md            # 项目设计文档
```

## 工具列表

### 1. WPS任务邮件提醒工具
- 位置：`wps/`
- 功能：自动查询WPS云文档中的待办任务并发送邮件提醒
- 详情：[查看文档](wps/README.md)

### 2. ClashVerge代理组管理工具
- 位置：`ClashVerge/`
- 功能：自动化管理ClashVerge的代理组配置
- 详情：[查看文档](ClashVerge/README.md)

## 开发规范

- 每个工具都是独立的，有自己的配置和文档
- 遵循统一的代码风格和文档格式
- 保持工具之间的低耦合性
- 提供详细的配置说明和使用文档

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 更新日志

### v1.0.0 (2024-05-16)
- 初始版本发布
- 添加WPS任务邮件提醒工具
- 添加ClashVerge代理组管理工具

## 许可证

MIT License 