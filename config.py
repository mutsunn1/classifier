"""配置文件 - 统一管理 API Key
使用方法：直接在此处填写你的 API Key
"""
import os


OPENAI_API_KEY = os.getenv("siliconflow1", "")  # 从环境变量获取 API Key，确保安全性
OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"
OPENAI_MODEL = "Qwen/Qwen3.5-27B" 

# import os
# OPENAI_API_KEY = os.getenv("siliconflow1", "")
# OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"
# OPENAI_MODEL = "deepseek-ai/DeepSeek-V3.2"
