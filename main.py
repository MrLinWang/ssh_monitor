#!/usr/bin/env python3
import paramiko
import time
import json
import os
import threading
from typing import Dict, Tuple, List
from datetime import datetime

P_PATH = os.path.dirname(os.path.abspath(__file__))

class SSHMonitor:
    def __init__(self, name: str, hostname: str, username: str, password: str = None, key_filename: str = None, port: int = 22):
        self.name = name
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.client = None
        self._lock = threading.Lock()

    def connect(self):
        """建立SSH连接"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                port=self.port
            )
            print(f"Successfully connected to {self.hostname}")
        except Exception as e:
            print(f"Failed to connect to {self.hostname}: {str(e)}")
            raise

    def disconnect(self):
        """关闭SSH连接"""
        if self.client:
            self.client.close()
            print(f"Disconnected from {self.hostname}")

    def get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"
        stdin, stdout, stderr = self.client.exec_command(cmd)
        cpu_usage = float(stdout.read().decode().strip())
        return cpu_usage

    def get_memory_usage(self) -> Dict[str, float]:
        """获取内存使用情况"""
        cmd = "free | grep Mem | awk '{print $2,$3,$4}'"
        stdin, stdout, stderr = self.client.exec_command(cmd)
        total, used, free = map(int, stdout.read().decode().strip().split())
        
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
        stdin, stdout, stderr = self.client.exec_command(cmd)
        disk_info = {}
        
        for line in stdout.readlines():
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
            return f"{self.name:<12} Error: {str(e)}"

class MultiServerMonitor:
    def __init__(self, config_file: str):
        self.monitors: List[SSHMonitor] = []
        self.load_config(config_file)
        self.running = True
        self._lock = threading.Lock()

    def load_config(self, config_file: str):
        """从配置文件加载服务器信息"""
        with open(config_file, 'r') as f:
            config = json.load(f)
            for server in config['servers']:
                monitor = SSHMonitor(
                    name=server['name'],
                    hostname=server['hostname'],
                    username=server['username'],
                    password=server.get('password'),
                    key_filename=server.get('key_filename'),
                    port=server.get('port', 22)
                )
                self.monitors.append(monitor)

    def connect_all(self):
        """连接所有服务器"""
        for monitor in self.monitors:
            try:
                monitor.connect()
            except Exception as e:
                print(f"Failed to connect to {monitor.name}: {str(e)}")

    def disconnect_all(self):
        """断开所有服务器连接"""
        for monitor in self.monitors:
            try:
                monitor.disconnect()
            except:
                pass

    def clear_screen(self):
        """清除屏幕内容"""
        print("\033[2J\033[H", end="")

    def print_header(self):
        """打印表头"""
        print("\nServer        CPU    Memory       Disk")
        print("             Usage   Used/Total    Used/Total")
        print("-" * 50)

    def monitor_all(self, interval: int = 5):
        """监控所有服务器"""
        try:
            while self.running:
                self.clear_screen()
                self.print_header()
                
                # 获取并显示所有服务器状态
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"Last Update: {current_time}\n")
                
                for monitor in self.monitors:
                    try:
                        status_line = monitor.format_status_line()
                        print(status_line)
                    except Exception as e:
                        print(f"{monitor.name:<12} Error: {str(e)}")
                
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        finally:
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
