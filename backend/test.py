"""A股取数快速自检。

直连 ak.stock_zh_a_hist(东方财富) 在「出口 IP 在境外 / 全局代理(TUN)」时会
握手失败: SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC。这里改走项目取数管线,
自动在 腾讯 -> 东财 -> 新浪 -> Yahoo 之间兜底, 并复用本地 SQLite 缓存。
逐个数据源的连通性诊断见 test_a_data.py。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services import data  # 导入即会剔除泄漏的本地代理

df = data.get_history("a", "000001", "2017-03-01", "2023-10-22")
print(f"{len(df)} rows")
print(df.tail())
