"""Agent Service 配置:数据源、脱敏、服务端口。"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("OPC_SERVICE_DATA", os.path.join(BASE_DIR, "service", "data"))

# 本机 Excel 数据(暂代 MySQL);接 MySQL 后切换 adapter,上层接口不变
EXCEL_PATH = os.environ.get(
    "OPC_EXCEL_PATH",
    "/Users/petercheng/Desktop/Junction/素材/社群用户基础数据D1879_D3323_修复.xlsx",
)
DB_PATH = os.environ.get("OPC_DB_PATH", os.path.join(DATA_DIR, "opsie.db"))

HOST = os.environ.get("OPC_SERVICE_HOST", "127.0.0.1")
PORT = int(os.environ.get("OPC_SERVICE_PORT", "8080"))

# 生成能力开关:测试/流程验证默认用确定性模板,联调时置 on 走 MiMo
LLM_ENABLED = os.environ.get("OPC_SERVICE_LLM", "off") == "on"

# 画像阈值(OPSIE 5.1,可被负责人调整;默认值先定死,保证口径一致)
ACTIVITY_DAYS_THRESHOLD = 5      # 近7日活跃天数下限
ACTIVITY_MINUTES_THRESHOLD = 15  # 日均阅读时长下限(分钟)
INTENT_SIGNALS_HIGH = 2          # 近3日推进信号达 2 项 → 高意向
