"""
笔记自动整理 Agent
"""
from typing import TypedDict, List, Dict, Any, Annotated
import operator
import json
import time

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from openai import RateLimitError

import config
from tools import TOOL_MAP


# ==================== 定义状态 ====================
class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[List[Dict], operator.add]  # 对话历史
    source_dir: str  # 源目录
    target_dir: str  # 目标目录
    plan: Dict[str, Any]  # 整理计划
    executed: List[str]  # 已执行的操作


# ==================== 工具包装器 ====================
# 将本地工具函数包装为 LangChain 工具

@tool
def list_files(directory_path: str) -> str:
    """获取指定目录下的所有文件列表"""
    result = TOOL_MAP["list_files"](directory_path)
    return json.dumps(result, ensure_ascii=False)


@tool
def read_file(file_path: str, max_lines: int = 50) -> str:
    """读取文件内容，默认最多读取前50行用于分析"""
    result = TOOL_MAP["read_file"](file_path, max_lines)
    return result


@tool
def create_directory(dir_path: str) -> str:
    """创建新目录/文件夹"""
    result = TOOL_MAP["create_directory"](dir_path)
    return json.dumps(result, ensure_ascii=False)


@tool
def move_file(source_path: str, destination_path: str) -> str:
    """移动文件从源路径到目标路径"""
    result = TOOL_MAP["move_file"](source_path, destination_path)
    return json.dumps(result, ensure_ascii=False)


@tool
def write_file(file_path: str, content: str) -> str:
    """创建并写入文件内容"""
    result = TOOL_MAP["write_file"](file_path, content)
    return json.dumps(result, ensure_ascii=False)


@tool
def rename_file(file_path: str, new_name: str) -> str:
    """重命名文件"""
    result = TOOL_MAP["rename_file"](file_path, new_name)
    return json.dumps(result, ensure_ascii=False)


# 工具列表
tools = [list_files, read_file, create_directory, move_file, write_file, rename_file]
tools_by_name = {t.name: t for t in tools}


# ==================== 初始化 LLM ====================
llm = ChatOpenAI(
    model=config.OPENAI_MODEL,
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_BASE_URL,
    temperature=0,
).bind_tools(tools)


# ==================== 节点函数 ====================

def agent_node(state: AgentState) -> Dict:
    """Agent 思考节点 - 决定下一步操作（带重试机制）"""
    from langchain_core.messages import SystemMessage, HumanMessage
    
    messages = state["messages"]
    
    # 如果是第一轮，添加系统提示和用户指令
    if len(messages) == 0:
        system_prompt = f"""你是一个专业的笔记整理助手。你的任务是：
1. 扫描目录 "{state['source_dir']}" 中的所有文件
2. 读取每个文件的前50行内容，分析其学科分类（如：数学、计算机科学、文学、物理、历史等）
3. 创建对应的学科文件夹在 "{state['target_dir']}" 目录下
4. 将文件移动到对应学科文件夹
5. 最后生成一个 README.md 索引文件，列出所有分类和文件

请按照以下步骤执行：
1. 先用 list_files 扫描源目录
2. 用 read_file 读取每个文件内容分析分类（每次只读取一个文件）
3. 用 create_directory 创建学科文件夹
4. 用 move_file 移动文件到对应文件夹
5. 用 write_file 创建 README.md

重要提示：
- 处理多个文件时，请逐个处理，每完成一个文件操作后等待工具返回结果
- 由于 API 速率限制，请不要一次性发起多个操作
"""
        user_prompt = f"请开始整理笔记：扫描目录 {state['source_dir']}，将整理结果放入 {state['target_dir']}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
    
    # 添加重试机制处理速率限制
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            return {"messages": [response]}
        except RateLimitError as e:
            wait_time = 2 ** attempt  # 指数退避: 1, 2, 4, 8, 16 秒
            print(f"[警告] API 速率限制，等待 {wait_time} 秒后重试... ({attempt + 1}/{max_retries})")
            time.sleep(wait_time)
    
    raise Exception("API 速率限制，已达到最大重试次数")


def tool_node(state: AgentState) -> Dict:
    """工具执行节点"""
    last_message = state["messages"][-1]
    
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return {"messages": []}
    
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # 执行工具
        tool_result = tools_by_name[tool_name].invoke(tool_args)
        
        tool_messages.append(ToolMessage(
            content=str(tool_result),
            name=tool_name,
            tool_call_id=tool_call["id"]
        ))
        
        # 工具执行后添加短暂延迟，避免触发 API 速率限制
        time.sleep(0.5)
    
    return {"messages": tool_messages}


def should_continue(state: AgentState) -> str:
    """决定是继续工具执行还是结束"""
    last_message = state["messages"][-1]
    
    # 如果没有工具调用，表示任务完成
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return "end"
    
    return "continue"


# ==================== 构建 LangGraph ====================

# 创建状态图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

# 添加边
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",
        "end": END
    }
)
workflow.add_edge("tools", "agent")

# 编译图（使用内存检查点）
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)


# ==================== 运行入口 ====================

def organize_notes(source_dir: str = "./notes", target_dir: str = "./organized_notes"):
    """
    整理笔记主函数
    
    Args:
        source_dir: 源笔记目录
        target_dir: 整理后的目标目录
    """
    # 确保源目录存在
    from pathlib import Path
    if not Path(source_dir).exists():
        print(f"错误: 源目录不存在: {source_dir}")
        return
    
    # 初始化状态
    initial_state = {
        "messages": [],
        "source_dir": source_dir,
        "target_dir": target_dir,
        "plan": {},
        "executed": []
    }
    
    # 配置（用于检查点）
    config_dict = {"configurable": {"thread_id": "note_organizer"}}
    
    print(f"[开始] 整理笔记...")
    print(f"[源目录] {source_dir}")
    print(f"[目标目录] {target_dir}")
    print("-" * 50)
    
    # 运行 Agent
    for event in app.stream(initial_state, config_dict):
        for node, output in event.items():
            if "messages" in output:
                for msg in output["messages"]:
                    if hasattr(msg, 'content') and msg.content:
                        if hasattr(msg, 'name'):
                            print(f"[工具] [{msg.name}]: {msg.content[:200]}...")
                        elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tc in msg.tool_calls:
                                print(f"[Agent] 调用: {tc['name']}({tc['args']})")
    
    print("-" * 50)
    print("[完成] 整理完成！")
    print(f"[提示] 请查看 {target_dir}/README.md 了解整理结果")


if __name__ == "__main__":
    import sys
    
    # 支持命令行参数
    source = sys.argv[1] if len(sys.argv) > 1 else "./notes"
    target = sys.argv[2] if len(sys.argv) > 2 else "./organized_notes"
    
    organize_notes(source, target)
