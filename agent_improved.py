"""
改进版笔记分类 Agent
应用 encoder-decoder 结构和优化方案
解决报告中提到的问题：
1. DeepSeek-V3.2: 忽略目标目录，原地整理
2. Qwen-80B: 误解工具需求，文件改文件夹名
"""

from typing import TypedDict, List, Dict, Any, Annotated
import operator
import json
import time
import os
from pathlib import Path
from datetime import datetime

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
    files: List[Dict[str, Any]]  # 文件列表
    summaries: Dict[str, str]  # 文件摘要
    categories: Dict[str, Any]  # 分类体系
    file_categories: Dict[str, str]  # 文件分类映射
    operations: List[Dict[str, Any]]  # 操作记录
    errors: List[Dict[str, Any]]  # 错误记录
    progress: Dict[str, Any]  # 进度跟踪


# ==================== 工具包装器（增强版） ====================

@tool
def list_files_tool(directory_path: str) -> str:
    """获取指定目录下的所有文本文件列表"""
    result = TOOL_MAP["list_files"](directory_path)
    # 过滤只返回文本文件
    if result and isinstance(result, list) and len(result) > 0:
        if "files" in result[0]:
            text_files = []
            for file_info in result[0]["files"]:
                if file_info.get("name", "").endswith(('.txt', '.md', '.rst')):
                    text_files.append(file_info)
            result[0]["files"] = text_files
            result[0]["count"] = len(text_files)
    return json.dumps(result, ensure_ascii=False)


@tool
def read_file_tool(file_path: str, max_lines: int = 100) -> str:
    """读取文件内容并提取结构化信息"""
    try:
        content = TOOL_MAP["read_file"](file_path, max_lines)

        # 提取结构化信息
        lines = content.split('\n')
        title = "未知标题"
        summary = ""
        categories = []

        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("标题:"):
                title = line.replace("标题:", "").strip()
            elif line.startswith("【摘要】") or line.startswith("摘要:"):
                # 获取摘要内容
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("【"):
                        summary = next_line
                        break
            elif line.startswith("【分类】") or line.startswith("分类:"):
                # 获取分类
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line:
                        categories = [cat.strip() for cat in next_line.split(',')]
                        break

        result = {
            "success": True,
            "title": title,
            "summary": summary,
            "content_preview": content[:500] + "..." if len(content) > 500 else content,
            "categories": categories,
            "path": file_path,
            "filename": Path(file_path).name
        }

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
def create_directory_tool(dir_path: str) -> str:
    """创建新目录/文件夹（增强验证）"""
    try:
        path = Path(dir_path)

        # 检查是否在目标目录范围内
        target_root = Path.cwd() / "organized_notes"
        if not str(path).startswith(str(target_root)):
            return json.dumps({
                "success": False,
                "error": f"目录必须在目标目录范围内: {target_root}"
            })

        result = TOOL_MAP["create_directory"](dir_path)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
def move_file_tool(source_path: str, destination_path: str) -> str:
    """移动文件从源路径到目标路径（增强验证）"""
    try:
        src = Path(source_path)
        dst = Path(destination_path)

        # 验证源文件存在
        if not src.exists():
            return json.dumps({
                "success": False,
                "error": f"源文件不存在: {source_path}"
            })

        # 验证目标路径在目标目录内
        target_root = Path.cwd() / "organized_notes"
        if not str(dst).startswith(str(target_root)):
            return json.dumps({
                "success": False,
                "error": f"目标路径必须在目标目录内: {target_root}"
            })

        result = TOOL_MAP["move_file"](source_path, destination_path)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
def write_file_tool(file_path: str, content: str) -> str:
    """创建并写入文件内容"""
    result = TOOL_MAP["write_file"](file_path, content)
    return json.dumps(result, ensure_ascii=False)


@tool
def generate_summary_tool(content: str, max_length: int = 100) -> str:
    """为内容生成简洁摘要（Encoder 阶段）"""
    try:
        # 简单摘要生成逻辑
        lines = content.split('\n')

        # 尝试找到摘要部分
        summary = ""
        for i, line in enumerate(lines):
            if "【摘要】" in line or "摘要:" in line:
                # 取下一行作为摘要
                if i + 1 < len(lines):
                    summary = lines[i + 1].strip()
                    break

        # 如果没有找到摘要，使用第一段非空内容
        if not summary:
            for line in lines:
                line = line.strip()
                if line and len(line) > 20:  # 避免太短的标题行
                    summary = line
                    break

        # 如果还没有，使用开头部分
        if not summary:
            summary = content[:200].strip()

        # 精简到一句话
        import re
        sentences = re.split(r'[.!?。！？]', summary)
        if sentences:
            one_sentence = sentences[0].strip()
            if one_sentence:
                # 确保以句号结束
                if not one_sentence.endswith('.'):
                    one_sentence += '.'

                # 限制长度
                if len(one_sentence) > max_length:
                    one_sentence = one_sentence[:max_length-3] + '...'

                summary = one_sentence

        return json.dumps({
            "success": True,
            "summary": summary,
            "original_length": len(content),
            "summary_length": len(summary)
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# 工具列表
tools = [
    list_files_tool,
    read_file_tool,
    create_directory_tool,
    move_file_tool,
    write_file_tool,
    generate_summary_tool
]
tools_by_name = {t.name: t for t in tools}


# ==================== 初始化 LLM ====================
llm = ChatOpenAI(
    model=config.OPENAI_MODEL,
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_BASE_URL,
    temperature=0,
).bind_tools(tools)

# 小参数模型用于摘要生成（Encoder）
llm_small = ChatOpenAI(
    model="deepseek-chat",  # 小参数模型
    api_key=config.OPENAI_API_KEY,
    base_url="https://api.deepseek.com/v1",
    temperature=0,
)


# ==================== 节点函数 ====================

def encoder_node(state: AgentState) -> Dict:
    """Encoder 节点：为每个文件生成摘要"""
    print("\n" + "="*60)
    print("🔍 ENCODER 阶段：分析文件内容并生成摘要")
    print("="*60)

    files = state.get("files", [])
    if not files:
        return {"messages": [AIMessage(content="错误：没有可处理的文件")]}

    summaries = {}

    for file_info in files[:10]:  # 限制处理数量，避免上下文过长
        file_path = file_info.get("path", "")
        if not file_path:
            continue

        # 读取文件内容
        try:
            content_result = json.loads(read_file_tool.invoke({"file_path": file_path, "max_lines": 50}))
            if not content_result.get("success"):
                print(f"❌ 读取失败: {Path(file_path).name}")
                continue

            content = content_result.get("content_preview", "")

            # 生成摘要
            summary_result = json.loads(generate_summary_tool.invoke({"content": content, "max_length": 80}))
            if summary_result.get("success"):
                summaries[file_path] = summary_result["summary"]
                print(f"📋 {Path(file_path).name}: {summary_result['summary']}")
            else:
                print(f"❌ 摘要失败: {Path(file_path).name}")

        except Exception as e:
            print(f"❌ 处理失败 {Path(file_path).name}: {e}")

    return {
        "summaries": summaries,
        "messages": [AIMessage(content=f"已为 {len(summaries)} 个文件生成摘要")]
    }


def planner_node(state: AgentState) -> Dict:
    """规划节点：设计分类体系"""
    print("\n" + "="*60)
    print("📊 PLANNER 阶段：设计分类体系")
    print("="*60)

    summaries = state.get("summaries", {})
    if not summaries:
        return {"messages": [AIMessage(content="错误：没有可用的摘要")]}

    # 构建规划提示
    summary_text = "\n".join([f"- {Path(path).name}: {summary}"
                             for path, summary in summaries.items()])

    prompt = f"""你是一个笔记分类专家。请根据以下笔记摘要设计一个合理的分类体系：

文件摘要：
{summary_text}

请设计3-6个互斥的分类类别，要求：
1. 类别名称简洁明确（英文或拼音，避免特殊字符）
2. 每个类别有明确的主题范围
3. 避免过于宽泛的分类（如"学习资料"）
4. 考虑创建一个"未分类"类别

返回JSON格式：
{{
    "categories": [
        {{
            "name": "category_name",
            "display_name": "显示名称",
            "description": "类别描述",
            "keywords": ["关键词1", "关键词2"]
        }}
    ],
    "uncategorized_category": {{
        "name": "uncategorized",
        "display_name": "未分类",
        "description": "无法分类的文件"
    }}
}}"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])

        # 解析响应
        import re
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if json_match:
            plan = json.loads(json_match.group())

            # 验证计划
            if "categories" not in plan:
                plan["categories"] = []
            if "uncategorized_category" not in plan:
                plan["uncategorized_category"] = {
                    "name": "uncategorized",
                    "display_name": "未分类",
                    "description": "无法分类的文件"
                }

            print(f"✅ 设计分类体系: {[c['display_name'] for c in plan['categories']]}")
            return {"categories": plan}

    except Exception as e:
        print(f"❌ 规划失败: {e}")

    # 默认分类计划
    default_plan = {
        "categories": [
            {
                "name": "science",
                "display_name": "科学",
                "description": "自然科学相关",
                "keywords": ["物理", "化学", "生物", "天文", "地理"]
            },
            {
                "name": "technology",
                "display_name": "技术",
                "description": "技术和计算机科学",
                "keywords": ["计算机", "编程", "人工智能", "软件", "硬件"]
            },
            {
                "name": "mathematics",
                "display_name": "数学",
                "description": "数学和统计学",
                "keywords": ["数学", "统计", "计算", "公式", "定理"]
            }
        ],
        "uncategorized_category": {
            "name": "uncategorized",
            "display_name": "未分类",
            "description": "无法分类的文件"
        }
    }

    return {"categories": default_plan}


def classifier_node(state: AgentState) -> Dict:
    """分类节点：将文件分配到具体类别"""
    print("\n" + "="*60)
    print("🏷️  CLASSIFIER 阶段：分配文件到类别")
    print("="*60)

    summaries = state.get("summaries", {})
    categories = state.get("categories", {}).get("categories", [])

    if not summaries or not categories:
        return {"messages": [AIMessage(content="错误：缺少摘要或分类信息")]}

    # 为每个文件分配类别
    file_categories = {}

    for file_path, summary in summaries.items():
        filename = Path(file_path).name

        # 简单分类逻辑（基于关键词匹配）
        best_match = "uncategorized"
        best_score = 0

        for category in categories:
            score = 0
            keywords = category.get("keywords", [])

            for keyword in keywords:
                if keyword.lower() in summary.lower():
                    score += 1

            if score > best_score:
                best_score = score
                best_match = category["name"]

        # 如果找到匹配且分数足够高
        if best_match != "uncategorized" and best_score >= 1:
            file_categories[file_path] = best_match
            print(f"📄 {filename} -> {best_match}")
        else:
            file_categories[file_path] = "uncategorized"
            print(f"📄 {filename} -> 未分类")

    return {
        "file_categories": file_categories,
        "messages": [AIMessage(content=f"已完成 {len(file_categories)} 个文件的分类")]
    }


def executor_node(state: AgentState) -> Dict:
    """执行节点：创建目录、移动文件、生成索引"""
    print("\n" + "="*60)
    print("🚀 EXECUTOR 阶段：执行分类操作")
    print("="*60)

    source_dir = state.get("source_dir", "./notes")
    target_dir = state.get("target_dir", "./organized_notes")
    categories = state.get("categories", {}).get("categories", [])
    uncategorized = state.get("categories", {}).get("uncategorized_category", {})
    file_categories = state.get("file_categories", {})

    # 1. 创建目标目录
    print("📂 创建目录结构...")
    create_directory_tool.invoke({"dir_path": target_dir})

    # 创建分类目录
    all_categories = categories + [uncategorized]
    for category in all_categories:
        cat_dir = os.path.join(target_dir, category["name"])
        result = json.loads(create_directory_tool.invoke({"dir_path": cat_dir}))

        if result.get("success"):
            created = "（新建）" if result.get("created", True) else "（已存在）"
            print(f"  ✓ {category.get('display_name', category['name'])} {created}")
        else:
            print(f"  ✗ {category['name']}: {result.get('error', '未知错误')}")

    # 2. 移动文件
    print("\n📄 移动文件...")
    moved_files = []

    for file_path, category_name in file_categories.items():
        # 找到对应的类别信息
        target_category = uncategorized
        for cat in all_categories:
            if cat["name"] == category_name:
                target_category = cat
                break

        # 构建目标路径
        target_dir_path = os.path.join(target_dir, target_category["name"])
        target_file_path = os.path.join(target_dir_path, Path(file_path).name)

        # 移动文件
        result = json.loads(move_file_tool.invoke({
            "source_path": file_path,
            "destination_path": target_file_path
        }))

        if result.get("success"):
            moved_files.append({
                "source": file_path,
                "destination": result.get("to", target_file_path),
                "category": target_category.get("display_name", category_name)
            })
            action = result.get("action", "moved")
            action_text = "移动" if action == "moved" else "重命名并移动"
            print(f"  ✓ {Path(file_path).name} -> {target_category.get('display_name', category_name)} ({action_text})")
        else:
            print(f"  ✗ {Path(file_path).name}: {result.get('error', '未知错误')}")

    # 3. 生成索引文件
    print("\n📝 生成索引文件...")
    index_content = generate_index_content(state, moved_files)
    index_path = os.path.join(target_dir, "README.md")

    write_result = json.loads(write_file_tool.invoke({
        "file_path": index_path,
        "content": index_content
    }))

    if write_result.get("success"):
        print(f"✅ 索引文件已生成: {index_path}")
    else:
        print(f"❌ 生成索引失败: {write_result.get('error', '未知错误')}")

    return {
        "moved_files": moved_files,
        "index_path": index_path if write_result.get("success") else None,
        "messages": [AIMessage(content=f"执行完成: 移动 {len(moved_files)} 个文件")]
    }


def generate_index_content(state: AgentState, moved_files: List[Dict]) -> str:
    """生成索引文件内容"""
    source_dir = state.get("source_dir", "./notes")
    target_dir = state.get("target_dir", "./organized_notes")
    categories = state.get("categories", {}).get("categories", [])
    uncategorized = state.get("categories", {}).get("uncategorized_category", {})

    # 按类别分组
    category_files = {}
    for category in categories:
        category_files[category["name"]] = []
    category_files["uncategorized"] = []

    for file_info in moved_files:
        dest_path = file_info.get("destination", "")
        category_name = file_info.get("category", "")

        # 找到对应的类别
        for category in categories:
            if category["display_name"] == category_name:
                category_files[category["name"]].append(file_info)
                break
        else:
            if category_name == uncategorized.get("display_name", "未分类"):
                category_files["uncategorized"].append(file_info)

    # 生成内容
    content = f"""# 笔记分类索引

> 自动生成于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 📋 概述

- **源目录**: `{source_dir}`
- **目标目录**: `{target_dir}`
- **总处理文件**: {len(moved_files)}
- **分类类别**: {len(categories)} 个
- **生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 📁 分类目录

"""

    # 每个类别的详情
    for category in categories:
        cat_name = category["name"]
        display_name = category.get("display_name", cat_name)
        description = category.get("description", "")
        files = category_files.get(cat_name, [])

        content += f"\n### {display_name}\n"
        content += f"{description}\n\n"

        if files:
            content += f"**文件 ({len(files)} 个):**\n\n"
            for file_info in files:
                filename = Path(file_info["source"]).name
                rel_path = os.path.relpath(
                    file_info["destination"],
                    target_dir
                ).replace("\\", "/")
                content += f"- [{filename}]({rel_path})\n"
        else:
            content += "*(暂无文件)*\n"

    # 未分类文件
    uncat_files = category_files.get("uncategorized", [])
    content += f"\n### {uncategorized.get('display_name', '未分类')}\n"
    content += f"{uncategorized.get('description', '无法分类的文件')}\n\n"

    if uncat_files:
        content += f"**文件 ({len(uncat_files)} 个):**\n\n"
        for file_info in uncat_files:
            filename = Path(file_info["source"]).name
            rel_path = os.path.relpath(
                file_info["destination"],
                target_dir
            ).replace("\\", "/")
            content += f"- [{filename}]({rel_path})\n"
    else:
        content += "*(暂无文件)*\n"

    # 统计信息
    content += f"""
## 📊 统计信息

| 类别 | 文件数量 | 比例 |
|------|----------|------|
"""

    total_files = len(moved_files)
    for category in categories:
        cat_name = category["name"]
        display_name = category.get("display_name", cat_name)
        count = len(category_files.get(cat_name, []))
        percentage = (count / total_files * 100) if total_files > 0 else 0
        content += f"| {display_name} | {count} | {percentage:.1f}% |\n"

    uncat_count = len(category_files.get("uncategorized", []))
    uncat_percentage = (uncat_count / total_files * 100) if total_files > 0 else 0
    content += f"| {uncategorized.get('display_name', '未分类')} | {uncat_count} | {uncat_percentage:.1f}% |\n"
    content += f"| **总计** | **{total_files}** | **100%** |\n"

    content += f"""
---

> 本索引由改进版笔记分类 Agent 自动生成
> 生成脚本: `agent_improved.py`
> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    return content


def agent_node(state: AgentState) -> Dict:
    """主 Agent 节点：协调整个流程"""
    print("\n🤖 AGENT 节点：协调分类流程")

    # 根据当前状态决定下一步
    current_step = state.get("progress", {}).get("step", "start")

    if current_step == "start":
        # 第一步：列出文件
        print("1️⃣ 扫描源目录...")
        files_result = json.loads(list_files_tool.invoke({"directory_path": state["source_dir"]}))

        if files_result and isinstance(files_result, list) and len(files_result) > 0:
            if files_result[0].get("success"):
                files = files_result[0].get("files", [])
                print(f"✅ 找到 {len(files)} 个文件")
                return {
                    "files": files,
                    "progress": {"step": "files_listed"},
                    "messages": [AIMessage(content=f"扫描完成，找到 {len(files)} 个文件")]
                }
            else:
                error_msg = files_result[0].get("error", "未知错误")
                print(f"❌ 扫描失败: {error_msg}")
                return {"messages": [AIMessage(content=f"扫描失败: {error_msg}")]}

    return {"messages": [AIMessage(content="流程完成")]}


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

        # 工具执行后添加短暂延迟
        time.sleep(0.5)

    return {"messages": tool_messages}


def should_continue(state: AgentState) -> str:
    """决定是继续工具执行还是结束"""
    last_message = state["messages"][-1]

    # 如果没有工具调用，表示任务完成
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return "end"

    return "continue"


# ==================== 构建改进的 LangGraph ====================

def build_improved_workflow():
    """构建改进的工作流"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("encoder", encoder_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("tools", tool_node)

    # 设置入口点
    workflow.set_entry_point("agent")

    # 路由逻辑
    def route_after_agent(state: AgentState):
        step = state.get("progress", {}).get("step", "start")

        if step == "start":
            return "agent"
        elif step == "files_listed":
            return "encoder"
        elif step == "encoder_done":
            return "planner"
        elif step == "planner_done":
            return "classifier"
        elif step == "classifier_done":
            return "executor"
        else:
            return "end"

    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "agent": "agent",
            "encoder": "encoder",
            "planner": "planner",
            "classifier": "classifier",
            "executor": "executor",
            "end": END
        }
    )

    # 连接其他节点
    workflow.add_edge("encoder", "planner")
    workflow.add_edge("planner", "classifier")
    workflow.add_edge("classifier", "executor")
    workflow.add_edge("executor", END)

    # 工具调用条件边
    workflow.add_conditional_edges(
        "tools",
        should_continue,
        {"continue": "tools", "end": END}
    )

    return workflow.compile(checkpointer=MemorySaver())


# ==================== 运行入口 ====================

def organize_notes_improved(source_dir: str = "./notes", target_dir: str = "./organized_notes"):
    """
    改进版整理笔记主函数

    Args:
        source_dir: 源笔记目录
        target_dir: 整理后的目标目录
    """
    # 确保源目录存在
    if not Path(source_dir).exists():
        print(f"错误: 源目录不存在: {source_dir}")
        return

    # 初始化状态
    initial_state = {
        "messages": [],
        "source_dir": source_dir,
        "target_dir": target_dir,
        "files": [],
        "summaries": {},
        "categories": {},
        "file_categories": {},
        "operations": [],
        "errors": [],
        "progress": {"step": "start"}
    }

    # 配置（用于检查点）
    config_dict = {"configurable": {"thread_id": "note_organizer_improved"}}

    print("="*60)
    print("🤖 改进版笔记分类 Agent")
    print("="*60)
    print(f"[源目录] {source_dir}")
    print(f"[目标目录] {target_dir}")
    print("-" * 50)

    # 构建并运行工作流
    try:
        app = build_improved_workflow()

        # 运行工作流
        final_state = app.invoke(initial_state, config_dict)

        print("-" * 50)
        print("🎉 分类完成!")
        print("="*60)

        # 显示结果摘要
        moved_files = final_state.get("moved_files", [])
        index_path = final_state.get("index_path")

        if moved_files:
            print(f"📊 统计信息:")
            from collections import Counter
            category_counts = Counter([f["category"] for f in moved_files])
            for category, count in category_counts.items():
                print(f"  {category}: {count} 个文件")

        if index_path and Path(index_path).exists():
            print(f"📝 索引文件: {index_path}")
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"  大小: {len(content)} 字符")

        print(f"\n🎯 总处理文件: {len(moved_files)}")
        print("="*60)

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys

    # 支持命令行参数
    source = sys.argv[1] if len(sys.argv) > 1 else "./notes"
    target = sys.argv[2] if len(sys.argv) > 2 else "./organized_notes"

    organize_notes_improved(source, target)