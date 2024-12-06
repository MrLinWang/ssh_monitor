# SSH Server Resource Monitor

一个基于Python的多服务器资源监控工具，通过SSH协议实时监控多台远程服务器的CPU、内存和磁盘使用情况。

## 功能特点

- 多服务器并行监控
- 实时更新资源使用状态
- 支持SSH密码和密钥认证
- 可配置的连接超时
- 详细的日志记录
- 平滑的终端显示
- 可自定义服务器配置

## 安装

1. 克隆仓库：
```bash
git clone <repository_url>
cd ssh_monitor
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 配置

在运行程序前，需要创建配置文件。你可以复制示例配置文件并修改：

```bash
cp config.json.example config.json
```

配置文件格式说明：

```json
{
    "global": {
        "username": "your_username",     # 默认用户名
        "password": null,                # 默认密码（如果使用密钥认证则为null）
        "key_filename": "~/.ssh/id_rsa", # 默认SSH密钥路径
        "port": 22,                      # 默认SSH端口
        "timeout": 5                     # 默认连接超时时间（秒）
    },
    "servers": [
        {
            "name": "server1",           # 服务器显示名称
            "hostname": "192.168.1.100"  # 服务器IP或域名
        },
        {
            "name": "server2",
            "hostname": "192.168.1.101",
            "port": 2222,                # 可选：覆盖全局配置
            "timeout": 10                # 可选：覆盖全局配置
        }
    ]
}
```

## 使用方法

1. 运行监控程序：
```bash
python main.py
```

2. 查看日志：
```bash
tail -f ssh_monitor.log
```

## 显示说明

监控界面包含以下信息：
- 服务器名称
- CPU使用率（%）
- 内存使用情况（已用/总量，GB）
- 根分区磁盘使用情况（已用/总量）

示例输出：
```
Server        CPU    Memory       Disk
             Usage   Used/Total   Used/Total
------------------------------------------
server1      25.3%   4.5/16.0GB   50G/100G
server2      15.7%   8.2/32.0GB   80G/200G
```

## 错误处理

- 如果服务器连接失败，对应行将显示问号（?）
- 详细的错误信息会记录在ssh_monitor.log文件中
- 程序会自动尝试重新连接断开的服务器

## 注意事项

1. 确保具有对目标服务器的SSH访问权限
2. 建议使用SSH密钥认证以提高安全性
3. 合理设置超时时间，避免因网络问题影响显示
4. 监控大量服务器时，注意系统资源使用

## 日志记录

程序会自动创建ssh_monitor.log文件，记录：
- 连接尝试和结果
- 命令执行情况
- 错误和异常信息
- 配置加载过程

## 退出程序

按Ctrl+C可以安全退出程序，程序会自动断开所有SSH连接。
