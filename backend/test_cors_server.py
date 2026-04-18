#!/usr/bin/env python3
"""
简化的测试服务器，专门用于解决CORS问题
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Owlangs Test Server")

# 添加CORS中间件 - 允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: Optional[bool] = False

class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None

class UserInfo(BaseModel):
    username: str
    email: Optional[str] = None
    role: str = "user"

@app.get("/")
async def root():
    return {"message": "Owlangs Test Server is running"}

@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """模拟登录接口"""
    # 简单的模拟验证
    if request.username == "admin" and request.password == "Changeme":
        return LoginResponse(
            success=True,
            message="Login successful",
            token="mock_token_12345"
        )
    else:
        return LoginResponse(
            success=False,
            message="Invalid username or password"
        )

@app.get("/auth/user")
async def get_user_info():
    """获取用户信息"""
    return {
        "id": "1",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin"
    }

@app.get("/auth/app-config")
async def get_app_config():
    """获取应用配置，包括AI平台信息"""
    return {
        "ui_texts": {
            "platform_categories": {
                "us_platforms": "🇺🇸 美国平台",
                "china_platforms": "🇨🇳 中国平台",
                "europe_platforms": "🇪🇺 欧洲平台",
                "japan_platforms": "🇯🇵 日本平台",
                "korea_platforms": "🇰🇷 韩国平台",
                "other_platforms": "🌍 其他平台"
            },
            "platform_info": {
                "platform_description": "平台简介",
                "apply_api_key": "申请API密钥: ",
                "click_to_apply": "点击申请",
                "platform_management": "AI Platform Management",
                "platform_management_description": "Manage AI platform configurations and API keys. Platform settings are loaded from platforms.json, while API keys are managed separately in secrets.json for security."
            },
            "platform_specs": {
                "model": "Model",
                "max_tokens": "Max Tokens",
                "temperature": "Temperature",
                "recommended": "Recommended"
            },
            "action_buttons": {
                "test": "Test",
                "save": "Save",
                "test_connection": "Test Connection"
            },
            "status_messages": {
                "configured": "Configured",
                "connection_successful": "Connection successful!",
                "connection_failed": "Connection failed!",
                "api_key_saved": "API key saved!"
            }
        },
        "default_platform": "deepseek",
        "ai_platforms": {
            "openai": {
                "name": "OpenAI",
                "url": "https://api.openai.com/v1/",
                "model": "gpt-4o",
                "max_tokens": 128000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "Industry-leading LLM with exceptional multilingual translation capabilities",
                "description": "OpenAI's GPT series represents the cutting-edge of large language models, delivering superior performance in translation tasks across multiple language pairs with high accuracy and strong contextual understanding.",
                "token_link": "https://platform.openai.com/api-keys",
                "platform_type": "llm"
            },
            "azure": {
                "name": "Azure OpenAI",
                "url": "https://your-resource.openai.azure.com/",
                "model": "gpt-4o-mini",
                "max_tokens": 128000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "Enterprise-grade GPT service with high availability and security",
                "description": "Microsoft Azure's OpenAI service provides enterprise-grade GPT models with enhanced security, compliance, and high availability, making it ideal for business-critical translation applications.",
                "token_link": "https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/overview"
            },
            "anthropic": {
                "name": "Anthropic Claude",
                "url": "https://api.anthropic.com",
                "model": "claude-3-sonnet",
                "max_tokens": 200000,
                "temperature": 0.3,
                "recommended_tokens": 50000,
                "performance_note": "擅长复杂推理和长文档处理，翻译质量优秀",
                "description": "Anthropic开发的Claude系列模型，在长文本处理和复杂推理方面表现突出，特别适合处理长文档的翻译任务。",
                "token_link": "https://console.anthropic.com/"
            },
            "google": {
                "name": "Google Gemini",
                "url": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-pro",
                "max_tokens": 32000,
                "temperature": 0.3,
                "recommended_tokens": 16000,
                "performance_note": "谷歌多模态模型，多语言支持好，性价比高",
                "description": "Google开发的多模态大语言模型，在多语言理解和生成方面表现优秀，支持100多种语言，翻译速度快。",
                "token_link": "https://makersuite.google.com/app/apikey"
            },
            "deepseek": {
                "name": "DeepSeek",
                "url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "max_tokens": 64000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "国产优秀模型，中英文翻译表现突出，性价比高",
                "description": "深度求索开发的DeepSeek系列模型，在中文理解和生成方面表现优秀，中英文翻译质量高，价格实惠。",
                "token_link": "https://platform.deepseek.com/api_keys"
            },
            "dashscope": {
                "name": "Alibaba DashScope",
                "url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-turbo",
                "max_tokens": 8000,
                "temperature": 0.3,
                "recommended_tokens": 4000,
                "performance_note": "阿里通义千问，中文处理能力强，响应速度快",
                "description": "阿里巴巴开发的通义千问系列模型，在中文文本处理方面表现优秀，支持多语言翻译，特别适合中文相关任务。",
                "token_link": "https://dashscope.console.aliyun.com/apiKey"
            },
            "zhipu": {
                "name": "Zhipu AI",
                "url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4-flash",
                "max_tokens": 128000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "清华智谱AI，学术背景强，中英文翻译质量高",
                "description": "清华大学背景的智谱AI开发的GLM系列模型，在学术文本和正式文档翻译方面表现优秀，中英文翻译质量高。",
                "token_link": "https://open.bigmodel.cn/usercenter/apikeys"
            },
            "baidu": {
                "name": "Baidu ERNIE",
                "url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
                "model": "ernie-bot",
                "max_tokens": 32000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "百度文心一言，中文理解能力强，多模态支持",
                "description": "百度开发的文心一言系列模型，在中文理解和生成方面表现优秀，支持多模态处理，适合中文相关翻译任务。",
                "token_link": "https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application"
            },
            "moonshot": {
                "name": "Moonshot AI",
                "url": "https://api.moonshot.cn/v1",
                "model": "moonshot-v1-8k",
                "max_tokens": 8000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "月之暗面，专注长文本处理，翻译质量稳定",
                "description": "月之暗面开发的Moonshot系列模型，专注于长文本处理，在长文档翻译方面表现稳定，支持多种语言对。",
                "token_link": "https://platform.moonshot.cn/console/api-keys"
            },
            "hunyuan": {
                "name": "Hunyuan",
                "url": "https://api.hunyuan.cloud.tencent.com/v1",
                "model": "hunyuan-lite",
                "max_tokens": 32000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "腾讯混元，企业级模型，稳定可靠",
                "description": "腾讯开发的混元系列模型，企业级AI服务，在稳定性和可靠性方面表现优秀，适合大规模翻译任务。",
                "token_link": "https://cloud.tencent.com/product/hunyuan"
            },
            "volcengine_ark": {
                "name": "VolcEngine ARK (豆包)",
                "url": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "doubao-seed-1-6-flash-250715",
                "max_tokens": 128000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "ByteDance's multimodal AI with excellent Chinese language capabilities",
                "description": "ByteDance's Doubao series represents a cutting-edge multimodal AI platform with exceptional Chinese language understanding and generation capabilities, supporting multilingual translation with specialized optimization for Chinese language tasks.",
                "token_link": "https://console.volcengine.com/ark"
            },
            "groq": {
                "name": "Groq",
                "url": "https://api.groq.com/openai/v1",
                "model": "llama3-70b-8192",
                "max_tokens": 8192,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "美国AI加速器，推理速度快，性价比高",
                "description": "Groq提供高性能AI推理服务，基于开源模型，推理速度快，成本低，适合大规模翻译任务。",
                "token_link": "https://console.groq.com/keys"
            },
            "mistral": {
                "name": "Mistral AI",
                "url": "https://api.mistral.ai/v1",
                "model": "mistral-large-latest",
                "max_tokens": 32000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "法国AI公司，欧洲语言处理优秀",
                "description": "法国Mistral AI开发的大语言模型，在欧洲语言处理方面表现优秀，支持多语言翻译，特别适合欧洲语言对。",
                "token_link": "https://console.mistral.ai/api-keys/"
            },
            "cohere": {
                "name": "Cohere",
                "url": "https://api.cohere.com/v1",
                "model": "command-r-plus",
                "max_tokens": 128000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "加拿大-美国AI公司，专注企业级应用",
                "description": "Cohere专注于企业级AI应用，在文本理解和生成方面表现优秀，支持多语言翻译，适合企业级翻译需求。",
                "token_link": "https://dashboard.cohere.ai/api-keys"
            },
            "xai": {
                "name": "xAI",
                "url": "https://api.x.ai/v1",
                "model": "grok-2",
                "max_tokens": 128000,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "马斯克创立的AI公司，Grok模型",
                "description": "Elon Musk创立的xAI公司开发的Grok系列模型，在推理和对话方面表现优秀，支持多语言翻译。",
                "token_link": "https://console.x.ai/"
            },
            "local": {
                "name": "Local (OpenAI API)",
                "url": "",
                "model": "",
                "max_tokens": 4096,
                "temperature": 0.3,
                "recommended_tokens": None,
                "performance_note": "Use any service that exposes OpenAI-style /chat/completions; fill in base URL, model name, and API key.",
                "description": "Connect to any AI service compatible with the OpenAI Chat Completions API. Provide the base URL, model name, and API key from your provider.",
                "token_link": "Obtain API key from your provider"
            },
            "aleph_alpha": {
                "name": "Aleph Alpha (Germany)",
                "url": "https://api.aleph-alpha.com",
                "model": "luminous-extended",
                "max_tokens": 2048,
                "temperature": 0.3,
                "recommended_tokens": 1000,
                "performance_note": "德国AI公司，欧洲语言处理能力强",
                "description": "德国Aleph Alpha公司开发的Luminous系列模型，在欧洲语言处理方面表现优秀，特别适合德语、法语等欧洲语言翻译。",
                "token_link": "https://app.aleph-alpha.com/"
            },
            "rinna": {
                "name": "Rinna (Japan)",
                "url": "https://api.rinna.co.jp",
                "model": "rinna-japanese-gpt2-medium",
                "max_tokens": 1024,
                "temperature": 0.3,
                "recommended_tokens": 512,
                "performance_note": "日本AI公司，日语处理能力优秀",
                "description": "日本Rinna公司开发的日语专用AI模型，在日语理解和生成方面表现优秀，特别适合日语相关翻译任务。",
                "token_link": "https://rinna.co.jp/"
            },
            "naver": {
                "name": "Naver HyperClova (Korea)",
                "url": "https://clova-api.navercorp.com",
                "model": "hyperclova-3.0",
                "max_tokens": 8192,
                "temperature": 0.3,
                "recommended_tokens": 4000,
                "performance_note": "韩国NAVER公司，韩语处理能力优秀",
                "description": "韩国NAVER公司开发的HyperClova系列模型，在韩语理解和生成方面表现优秀，特别适合韩语相关翻译任务。",
                "token_link": "https://clova.ai/",
                "platform_type": "llm"
            },
            "mineru": {
                "name": "MinerU",
                "url": "https://mineru.net/api/v4",
                "model": "vlm",
                "max_tokens": 0,
                "temperature": 0.0,
                "recommended_tokens": None,
                "performance_note": "高级文档解析和转换服务，支持OCR功能",
                "description": "MinerU是一个强大的文档解析服务，可以将各种文档格式（PDF、Word、PowerPoint等）转换为结构化的markdown格式，具有高精度和OCR支持。",
                "token_link": "https://mineru.net/",
                "platform_type": "parser",
                "api_endpoints": {
                    "upload": "/file-urls/batch",
                    "result": "/extract-results/batch"
                }
            },
        }
    }

@app.get("/auth/app-config/raw-secrets")
async def get_secrets_config():
    """获取敏感配置，包括API密钥"""
    return {
        "platform_api_keys": {
            "deepseek": {
                "key": "sk-dd06eed4dbee4cbbbab1b7b0e920a079",
                "configured": True
            },
            "openai": {
                "key": "your-openai-api-key",
                "configured": False
            },
            "azure": {
                "key": "your-azure-api-key-here",
                "configured": False
            },
            "anthropic": {
                "key": "your-anthropic-api-key-here",
                "configured": False
            },
            "google": {
                "key": "your-google-api-key-here",
                "configured": False
            },
            "dashscope": {
                "key": "your-dashscope-api-key-here",
                "configured": False
            },
            "zhipu": {
                "key": "your-zhipu-api-key-here",
                "configured": False
            },
            "baidu": {
                "key": "your-baidu-api-key-here",
                "configured": False
            },
            "moonshot": {
                "key": "your-moonshot-api-key-here",
                "configured": False
            },
            "hunyuan": {
                "key": "your-hunyuan-api-key-here",
                "configured": False
            },
            "volcengine_ark": {
                "key": "your-volcengine-api-key-here",
                "configured": False
            },
            "groq": {
                "key": "your-groq-api-key-here",
                "configured": False
            },
            "mistral": {
                "key": "your-mistral-api-key-here",
                "configured": False
            },
            "cohere": {
                "key": "your-cohere-api-key-here",
                "configured": False
            },
            "xai": {
                "key": "your-xai-api-key-here",
                "configured": False
            },
            "local": {
                "key": "your-local-api-key-here",
                "configured": False
            },
            "aleph_alpha": {
                "key": "your-aleph-alpha-api-key-here",
                "configured": False
            },
            "rinna": {
                "key": "your-rinna-api-key-here",
                "configured": False
            },
            "naver": {
                "key": "your-naver-api-key-here",
                "configured": False
            },
            "mineru": {
                "key": "your-mineru-token-here",
                "configured": False
            },
        }
    }

@app.put("/auth/app-config")
async def update_app_config(config: dict):
    """更新应用配置"""
    print(f"Updating app config: {config}")
    return {"success": True, "message": "Configuration updated successfully"}

@app.post("/auth/app-config/setting")
async def update_single_setting(request: dict):
    """更新单个设置"""
    print(f"Updating setting: {request}")
    return {"success": True, "message": "Setting updated successfully"}

@app.post("/auth/test-ai-platform")
async def test_ai_platform(request: dict):
    """测试AI平台连接"""
    platform = request.get("platform", "")
    api_key = request.get("api_key", "")
    
    print(f"Testing AI platform: {platform} with API key: {'***' if api_key else 'None'}")
    
    # 模拟测试结果
    if api_key and len(api_key) > 10:
        return {
            "success": True,
            "message": f"Connection to {platform} successful!",
            "platform": platform
        }
    else:
        return {
            "success": False,
            "message": f"Connection to {platform} failed: Invalid API key",
            "platform": platform
        }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "message": "Server is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8800)
