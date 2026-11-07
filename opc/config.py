"""全局配置:路径与 MiMo API 连接。"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MATERIAL_DIR = os.environ.get(
    "OPC_MATERIAL_DIR", "/Users/petercheng/Desktop/Junction/素材"
)
KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")
HUB_DIR = os.path.join(ROOT, "hub")
LOG_DIR = os.path.join(ROOT, "logs")
OUTPUT_DIR = os.path.join(ROOT, "output")

LOG_FILE = os.path.join(LOG_DIR, "07-log.md")

# MiMo API(Anthropic 兼容端点)
API_BASE = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
MODEL = os.environ.get("OPC_MODEL", "mimo-v2.6-pro")

for d in (KNOWLEDGE_DIR, HUB_DIR, LOG_DIR, OUTPUT_DIR):
    os.makedirs(d, exist_ok=True)
