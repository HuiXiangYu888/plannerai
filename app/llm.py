import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_chat_model(streaming: bool = False) -> ChatOpenAI:
    """获取 ChatOpenAI 模型实例。
    支持 DeepSeek（默认）和 OpenAI 兼容接口。
    环境变量优先级: DEEPSEEK_API_KEY > OPENAI_API_KEY > DASHSCOPE_API_KEY
    """
    api_key = (
        os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    if not api_key:
        raise RuntimeError("Missing API key. Set DEEPSEEK_API_KEY in your .env file.")

    base_url = (
        os.getenv("DEEPSEEK_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.deepseek.com/v1"
    )
    model_name = (
        os.getenv("DEEPSEEK_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "deepseek-chat"
    )

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        default_headers={"Authorization": f"Bearer {api_key}"},
        temperature=0.3,
        streaming=streaming,
    )
