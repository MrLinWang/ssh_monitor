#!/usr/bin/env python3
import paramiko
import time
import json
import os
import threading
from typing import Dict, Tuple, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

P_PATH = os.path.dirname(os.path.abspath(__file__))

# 配置日志记录器
def setup_logger():
    logger = logging.getLogger('ssh_monitor')
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    log_file = os.path.join(P_PATH, 'ssh_monitor.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()

class SSHMonitor:
    def __init__(self, name: str, hostname: str, username: str, password: str = None, 
                 key_filename: str = None, port: int = 22, timeout: int = 5):
        self.name = name
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.timeout = timeout
        self.client = None
        self._lock = threading.Lock()
        self.logger = logging.getLogger('ssh_monitor')

    def connect(self):
        """建立SSH连接"""
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            return

        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                port=self.port,
                timeout=self.timeout
            )
            self.logger.info(f"Successfully connected to {self.hostname}")
            print(f"Successfully connected to {self.hostname}")
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.hostname}: {str(e)}")
            raise

    def disconnect(self):
        """断开SSH连接"""
        if self.client:
            try:
                self.client.close()
                self.logger.info(f"Disconnected from {self.hostname}")
            except Exception as e:
                self.logger.error(f"Error disconnecting from {self.hostname}: {str(e)}")

    def execute_command(self, command: str) -> str:
        """执行SSH命令"""
        with self._lock:
            try:
                if not self.client or not self.client.get_transport() or not self.client.get_transport().is_active():
                    self.logger.warning(f"Connection lost to {self.hostname}, attempting to reconnect")
                    self.connect()
                
                stdin, stdout, stderr = self.client.exec_command(command)
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                
                if error:
                    self.logger.warning(f"Command '{command}' on {self.hostname} produced error: {error}")
                
                return output
            except Exception as e:
                self.logger.error(f"Error executing command '{command}' on {self.hostname}: {str(e)}")
                raise

    def get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"
        cpu_usage = float(self.execute_command(cmd))
        return cpu_usage

    def get_memory_usage(self) -> Dict[str, float]:
        """获取内存使用情况"""
        cmd = "free | grep Mem | awk '{print $2,$3,$4}'"
        total, used, free = map(int, self.execute_command(cmd).split())
        
        memory_info = {
            'total_mb': total / 1024,
            'used_mb': used / 1024,
            'free_mb': free / 1024,
            'usage_percent': (used / total) * 100
        }
        return memory_info

    def get_disk_usage(self) -> Dict[str, Dict[str, float]]:
        """获取磁盘使用情况"""
        cmd = "df -h | grep '^/dev'"
        disk_info = {}
        
        for line in self.execute_command(cmd).splitlines():
            parts = line.strip().split()
            if len(parts) >= 6:
                filesystem = parts[0]
                total = parts[1]
                used = parts[2]
                available = parts[3]
                usage_percent = float(parts[4].strip('%'))
                mount_point = parts[5]
                
                disk_info[mount_point] = {
                    'filesystem': filesystem,
                    'total': total,
                    'used': used,
                    'available': available,
                    'usage_percent': usage_percent
                }
        return disk_info

    def format_status_line(self) -> str:
        """格式化单行状态信息"""
        try:
            if not self.client or not self.client.get_transport() or not self.client.get_transport().is_active():
                return f"{self.name:<12} {'?':>4}    {'?':>5}/{'?':>5}GB    {'?'}/{'?'}"

            cpu_usage = self.get_cpu_usage()
            memory_usage = self.get_memory_usage()
            disk_usage = self.get_disk_usage()
            
            # 获取主要磁盘分区（根目录）的使用情况
            root_disk = disk_usage.get('/', disk_usage.get(list(disk_usage.keys())[0]))
            
            # 转换内存单位从MB到GB
            used_gb = memory_usage['used_mb'] / 1024
            total_gb = memory_usage['total_mb'] / 1024
            
            return (f"{self.name:<12} "
                   f"{cpu_usage:4.1f}%  "
                   f"{used_gb:5.1f}/{total_gb:.1f}GB  "
                   f"{root_disk['used']}/{root_disk['total']}")
        except Exception as e:
            self.logger.error(f"Error formatting status line for {self.name}: {str(e)}")
            return f"{self.name:<12} {'?':>4}    {'?':>5}/{'?':>5}GB    {'?'}/{'?'}"

class MultiServerMonitor:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.monitors: List[SSHMonitor] = []
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.running = True
        self.logger = logging.getLogger('ssh_monitor')
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.logger.info(f"Loading configuration from {self.config_file}")
            
            global_config = config.get('global', {})
            default_username = global_config.get('username')
            default_password = global_config.get('password')
            default_key_filename = global_config.get('key_filename')
            default_port = global_config.get('port', 22)
            default_timeout = global_config.get('timeout', 5)

            # 展开key_filename中的~为实际的家目录路径
            if default_key_filename and '~' in default_key_filename:
                default_key_filename = os.path.expanduser(default_key_filename)

            servers = config.get('servers', [])
            self.logger.info(f"Found {len(servers)} servers in configuration")

            for server in servers:
                # 处理每个服务器的key_filename
                key_filename = server.get('key_filename', default_key_filename)
                if key_filename and '~' in key_filename:
                    key_filename = os.path.expanduser(key_filename)

                monitor = SSHMonitor(
                    name=server['name'],
                    hostname=server['hostname'],
                    username=server.get('username', default_username),
                    password=server.get('password', default_password),
                    key_filename=key_filename,
                    port=server.get('port', default_port),
                    timeout=server.get('timeout', default_timeout)
                )
                self.monitors.append(monitor)
                self.logger.debug(f"Added monitor for server {server['name']}")
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise

    def connect_all(self):
        """并行连接所有服务器"""
        def connect_server(monitor):
            try:
                monitor.connect()
                return True
            except Exception as e:
                self.logger.error(f"Failed to connect to {monitor.name}: {str(e)}")
                return False

        futures = []
        for monitor in self.monitors:
            futures.append(self.executor.submit(connect_server, monitor))
        
        # 等待所有连接完成
        for future in as_completed(futures):
            future.result()

    def disconnect_all(self):
        """断开所有服务器连接"""
        self.logger.info("Disconnecting from all servers")
        for monitor in self.monitors:
            try:
                monitor.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting from {monitor.name}: {str(e)}")

    def clear_line(self):
        """清除当前行"""
        print('\r\033[K', end='')

    def move_cursor(self, lines: int):
        """移动光标上下n行"""
        if lines > 0:
            print(f'\033[{lines}B', end='')  # 向下移动
        else:
            print(f'\033[{-lines}A', end='')  # 向上移动

    def clear_screen(self):
        """清除屏幕内容"""
        if not hasattr(self, '_first_clear'):
            print("\033[2J\033[H", end="")
            self._first_clear = True
        else:
            # 移动到开头并清除之后的所有行
            print("\033[H", end="")

    def print_header(self):
        """打印表头"""
        print("\nServer        CPU    Memory       Disk")
        print("             Usage   Used/Total    Used/Total")
        print("-" * 50)

    def get_server_status(self, monitor: SSHMonitor) -> Tuple[str, str]:
        """获取单个服务器状态"""
        return monitor.name, monitor.format_status_line()

    def monitor_all(self, interval: int = 1):
        """监控所有服务器"""
        try:
            while self.running:
                self.clear_screen()
                self.print_header()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"Last Update: {current_time}\n")

                # 并行获取所有服务器状态
                server_status = {}  # 用于存储状态和保持顺序
                futures_dict = {}  # 用于跟踪future和monitor的关系
                
                for monitor in self.monitors:
                    future = self.executor.submit(self.get_server_status, monitor)
                    futures_dict[future] = monitor

                # 收集结果
                for future in as_completed(futures_dict):
                    monitor = futures_dict[future]
                    _, status = future.result()
                    server_status[monitor] = status

                # 按照原始顺序显示结果
                for monitor in self.monitors:
                    if monitor in server_status:
                        print(server_status[monitor])

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        finally:
            print('\033[?25h', end='')  # 恢复光标
            self.disconnect_all()

def main():
    config_file = os.path.join(P_PATH, "config.json")
    
    multi_monitor = MultiServerMonitor(config_file)
    try:
        multi_monitor.connect_all()
        multi_monitor.monitor_all(interval=1)
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    finally:
        multi_monitor.disconnect_all()

if __name__ == "__main__":
    main()
