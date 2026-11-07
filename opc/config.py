"""全局配置：路径与模型连接。"""
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

# 默认使用本机 Magpie 中配置的 SophNet；可选择 MiMo 兼容端点。
LLM_PROVIDER = os.environ.get('OPC_LLM_PROVIDER', 'magpie').lower()
MAGPIE_BASE = os.environ.get('OPC_MAGPIE_BASE_URL', 'http://127.0.0.1:3425').rstrip('/')
MAGPIE_TOKEN = os.environ.get('OPC_MAGPIE_TOKEN', 'magpie')
MAGPIE_ACTOR_TOKEN = os.environ.get('OPC_MAGPIE_ACTOR_TOKEN', 'magpie')
API_BASE = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
MODEL = os.environ.get('OPC_MODEL', 'mimo-v2.6-pro' if LLM_PROVIDER == 'mimo' else 'sophnet/DeepSeek-V4.1-Flash-1017')

for d in (KNOWLEDGE_DIR, HUB_DIR, LOG_DIR, OUTPUT_DIR):
    os.makedirs(d, exist_ok=True)
