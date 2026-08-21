import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fast_agent import FastAgent

# 1. 路径与配置初始化
BASE_DIR = Path("D:/fast-agent-main/fast-agent-main")
HOME_DIR = BASE_DIR / ".fast-agent"
CONFIG_PATH = HOME_DIR / "fast-agent.yaml"

# 创建 FastAgent 实例
fast = FastAgent(
    "codesys-assistant-api",
    config_path=str(CONFIG_PATH),
    home=str(HOME_DIR),
    parse_cli_args=False,
)

# 2. 定义助手（Agent）
@fast.agent(
    name="codesys_helper",
    instruction="你是一个 CODESYS 自动化专家助手。请使用中文回答。你拥有操作本地 CODESYS 的能力。当用户询问项目信息、变量、代码生成或逻辑诊断时，请务必调用 codesys MCP 服务器中的工具。",
    servers=["codesys"],
    default=True,
)
async def agent_definition():
    pass

# 3. 数据模型
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class StatusResponse(BaseModel):
    backend: str
    mcp_ready: bool
    active_servers: List[str]

# 4. 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[*] 正在初始化 FastAgent 引擎...")
    async with fast.run() as agents:
        app.state.agents = agents
        print("[+] 引擎已就绪，等待连接。")
        yield
    print("[*] 正在关闭引擎...")

app = FastAPI(lifespan=lifespan)

# 5. 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. 路由接口
@app.get("/")
async def serve_index():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    if not hasattr(app.state, "agents") or app.state.agents is None:
        return StatusResponse(backend="offline", mcp_ready=False, active_servers=[])
    
    try:
        # 获取当前挂载到 agent 的服务器列表 (需要 await)
        servers = await app.state.agents.list_attached_mcp_servers("codesys_helper")
        return StatusResponse(
            backend="online",
            mcp_ready="codesys" in servers,
            active_servers=servers
        )
    except Exception as e:
        print(f"Status check error: {e}")
        return StatusResponse(backend="online", mcp_ready=False, active_servers=[])

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not hasattr(app.state, "agents") or app.state.agents is None:
        raise HTTPException(status_code=503, detail="系统正在启动中，请稍候...")
    
    try:
        # 发送消息给 Agent
        result = await app.state.agents.send(req.message)
        return ChatResponse(response=str(result))
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
