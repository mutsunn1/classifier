"""
测试改进版笔记分类 Agent
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime


def setup_test_environment():
    """设置测试环境"""
    print("="*60)
    print("设置测试环境")
    print("="*60)

    # 创建测试目录
    test_dirs = ["test_notes", "test_organized", "test_results"]

    for dir_path in test_dirs:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"清理目录: {dir_path}")

        os.makedirs(dir_path, exist_ok=True)
        print(f"创建目录: {dir_path}")

    # 创建测试笔记文件
    test_files = [
        {
            "name": "数学_微积分基础.txt",
            "content": """标题: 微积分基础
URL: https://example.com/calculus

【摘要】
微积分是数学的一个分支，主要研究变化率和累积量。

【正文】
微积分包括微分和积分两个主要部分。微分研究函数的瞬时变化率，积分研究函数的累积效应。

【分类】
数学, 计算"""
        },
        {
            "name": "物理_量子力学简介.txt",
            "content": """标题: 量子力学简介
URL: https://example.com/quantum

【摘要】
量子力学是描述微观粒子行为的物理学理论。

【正文】
量子力学与经典力学有根本区别，包括波粒二象性、不确定性原理等概念。

【分类】
物理, 科学"""
        },
        {
            "name": "计算机_人工智能概述.txt",
            "content": """标题: 人工智能概述
URL: https://example.com/ai

【摘要】
人工智能是计算机科学的一个分支，研究如何使机器具有智能。

【正文】
人工智能包括机器学习、深度学习、自然语言处理等多个子领域。

【分类】
计算机科学, 技术"""
        },
        {
            "name": "化学_有机化学基础.txt",
            "content": """标题: 有机化学基础
URL: https://example.com/organic_chemistry

【摘要】
有机化学是研究有机化合物的结构、性质、制备的化学分支。

【正文】
有机化合物主要含碳元素，包括烃类、醇类、酸类等。

【分类】
化学, 科学"""
        },
        {
            "name": "未分类_测试文件.txt",
            "content": """标题: 测试文件
URL: https://example.com/test

【摘要】
这是一个测试文件，内容不明确。

【正文】
12345 abcde 测试内容。

【分类】
"""
        }
    ]

    # 写入测试文件
    for file_info in test_files:
        file_path = os.path.join("test_notes", file_info["name"])
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_info["content"])
        print(f"创建测试文件: {file_info['name']}")

    print(f"\n✅ 创建了 {len(test_files)} 个测试文件")
    return "test_notes", "test_organized"


def test_tools():
    """测试工具函数"""
    print("\n" + "="*60)
    print("测试工具函数")
    print("="*60)

    # 导入工具
    from tools import TOOL_MAP

    # 测试 list_files
    print("测试 list_files...")
    result = TOOL_MAP["list_files"]("test_notes")
    print(f"  结果: {json.dumps(result, ensure_ascii=False)}")

    # 测试 read_file
    print("\n测试 read_file...")
    test_file = os.path.join("test_notes", "数学_微积分基础.txt")
    content = TOOL_MAP["read_file"](test_file, 10)
    print(f"  内容预览: {content[:200]}...")

    # 测试 create_directory
    print("\n测试 create_directory...")
    test_dir = "test_organized/数学"
    result = TOOL_MAP["create_directory"](test_dir)
    print(f"  结果: {json.dumps(result, ensure_ascii=False)}")

    # 测试 move_file
    print("\n测试 move_file...")
    source = test_file
    destination = os.path.join(test_dir, "数学_微积分基础.txt")
    result = TOOL_MAP["move_file"](source, destination)
    print(f"  结果: {json.dumps(result, ensure_ascii=False)}")

    # 测试 write_file
    print("\n测试 write_file...")
    test_index = "test_organized/README.md"
    content = "# 测试索引\n\n这是一个测试文件。"
    result = TOOL_MAP["write_file"](test_index, content)
    print(f"  结果: {json.dumps(result, ensure_ascii=False)}")

    print("\n✅ 工具函数测试完成")


def test_offline_classification():
    """离线分类测试（模拟 Encoder-Decoder 结构）"""
    print("\n" + "="*60)
    print("离线分类测试（模拟 Encoder-Decoder）")
    print("="*60)

    source_dir = "test_notes"
    target_dir = "test_organized"

    # 1. 扫描文件
    print("1️⃣ 扫描文件...")
    from tools import TOOL_MAP
    files_result = TOOL_MAP["list_files"](source_dir)
    files = files_result[0]["files"] if files_result[0]["success"] else []
    print(f"  找到 {len(files)} 个文件")

    # 2. 生成摘要（Encoder 阶段）
    print("\n2️⃣ 生成摘要（Encoder）...")
    summaries = {}
    for file_info in files:
        file_path = file_info["path"]
        content = TOOL_MAP["read_file"](file_path, 30)

        # 简单摘要提取
        lines = content.split('\n')
        summary = ""
        for i, line in enumerate(lines):
            if "【摘要】" in line and i + 1 < len(lines):
                summary = lines[i + 1].strip()
                break

        if not summary and len(lines) > 0:
            summary = lines[0].strip()[:100] + "..."

        summaries[file_path] = summary
        print(f"  {Path(file_path).name}: {summary}")

    # 3. 设计分类体系（Planner 阶段）
    print("\n3️⃣ 设计分类体系（Planner）...")
    categories = [
        {
            "name": "mathematics",
            "display_name": "数学",
            "description": "数学相关",
            "keywords": ["数学", "微积分", "计算"]
        },
        {
            "name": "physics",
            "display_name": "物理",
            "description": "物理学相关",
            "keywords": ["物理", "量子", "力学"]
        },
        {
            "name": "computer_science",
            "display_name": "计算机科学",
            "description": "计算机科学相关",
            "keywords": ["计算机", "人工智能", "编程"]
        },
        {
            "name": "chemistry",
            "display_name": "化学",
            "description": "化学相关",
            "keywords": ["化学", "有机", "化合物"]
        },
        {
            "name": "uncategorized",
            "display_name": "未分类",
            "description": "无法分类的文件",
            "keywords": []
        }
    ]

    print(f"  设计 {len(categories)} 个分类")

    # 4. 分类文件（Classifier 阶段）
    print("\n4️⃣ 分类文件（Classifier）...")
    file_categories = {}

    for file_path, summary in summaries.items():
        filename = Path(file_path).name

        # 简单关键词匹配
        best_match = "uncategorized"
        best_score = 0

        for category in categories:
            if category["name"] == "uncategorized":
                continue

            score = 0
            for keyword in category["keywords"]:
                if keyword in summary or keyword in filename:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = category["name"]

        file_categories[file_path] = best_match
        category_name = next((c["display_name"] for c in categories if c["name"] == best_match), best_match)
        print(f"  {filename} -> {category_name}")

    # 5. 执行分类（Executor 阶段）
    print("\n5️⃣ 执行分类（Executor）...")

    # 创建目录
    for category in categories:
        cat_dir = os.path.join(target_dir, category["name"])
        TOOL_MAP["create_directory"](cat_dir)
        print(f"  创建目录: {category['display_name']}")

    # 移动文件
    moved_files = []
    for file_path, category_name in file_categories.items():
        target_category = next((c for c in categories if c["name"] == category_name), categories[-1])
        target_dir_path = os.path.join(target_dir, target_category["name"])
        target_file_path = os.path.join(target_dir_path, Path(file_path).name)

        result = TOOL_MAP["move_file"](file_path, target_file_path)

        if result["success"]:
            moved_files.append({
                "source": file_path,
                "destination": result["to"],
                "category": target_category["display_name"]
            })
            print(f"  移动: {Path(file_path).name} -> {target_category['display_name']}")
        else:
            print(f"  移动失败: {Path(file_path).name} - {result['error']}")

    # 6. 生成索引
    print("\n6️⃣ 生成索引...")
    index_content = generate_test_index(moved_files, categories, source_dir, target_dir)
    index_path = os.path.join(target_dir, "README.md")

    TOOL_MAP["write_file"](index_path, index_content)
    print(f"  生成索引文件: {index_path}")

    # 7. 生成报告
    print("\n7️⃣ 生成报告...")
    report = {
        "test": "离线分类测试",
        "timestamp": datetime.now().isoformat(),
        "source_dir": source_dir,
        "target_dir": target_dir,
        "total_files": len(files),
        "moved_files": len(moved_files),
        "categories": len(categories),
        "file_categories": file_categories,
        "summaries": {Path(k).name: v[:50] + "..." for k, v in summaries.items()}
    }

    report_path = os.path.join("test_results", "offline_test_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  生成报告: {report_path}")

    # 显示结果
    print("\n" + "="*60)
    print("📊 测试结果")
    print("="*60)
    print(f"源目录: {source_dir}")
    print(f"目标目录: {target_dir}")
    print(f"处理文件: {len(moved_files)}/{len(files)}")

    # 分类统计
    from collections import Counter
    category_counts = Counter([f["category"] for f in moved_files])
    print("\n分类统计:")
    for category, count in category_counts.items():
        print(f"  {category}: {count} 个文件")

    # 验证结果
    verify_results(target_dir)


def generate_test_index(moved_files, categories, source_dir, target_dir):
    """生成测试索引文件"""
    # 按类别分组
    category_files = {}
    for category in categories:
        category_files[category["name"]] = []

    for file_info in moved_files:
        category_name = file_info["category"]
        for category in categories:
            if category["display_name"] == category_name:
                category_files[category["name"]].append(file_info)
                break
        else:
            category_files["uncategorized"].append(file_info)

    # 生成内容
    content = f"""# 测试索引文件

> 离线测试生成于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 概述

- **源目录**: `{source_dir}`
- **目标目录**: `{target_dir}`
- **总文件数**: {len(moved_files)}
- **分类数量**: {len(categories)}

## 分类目录

"""

    for category in categories:
        cat_name = category["name"]
        display_name = category["display_name"]
        description = category["description"]
        files = category_files.get(cat_name, [])

        content += f"\n### {display_name}\n"
        content += f"{description}\n\n"

        if files:
            content += f"**文件 ({len(files)} 个):**\n\n"
            for file_info in files:
                filename = Path(file_info["source"]).name
                rel_path = os.path.relpath(file_info["destination"], target_dir).replace("\\", "/")
                content += f"- [{filename}]({rel_path})\n"
        else:
            content += "*(暂无文件)*\n"

    content += f"""
## 统计信息

| 类别 | 文件数量 |
|------|----------|
"""

    for category in categories:
        cat_name = category["name"]
        display_name = category["display_name"]
        count = len(category_files.get(cat_name, []))
        content += f"| {display_name} | {count} |\n"

    content += f"| **总计** | **{len(moved_files)}** |\n"

    content += f"""
---

> 本文件由测试脚本生成
> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    return content


def verify_results(target_dir):
    """验证结果"""
    print("\n" + "="*60)
    print("验证结果")
    print("="*60)

    target_path = Path(target_dir)

    if not target_path.exists():
        print(f"❌ 目标目录不存在: {target_dir}")
        return

    # 检查目录结构
    print("检查目录结构:")
    subdirs = [d for d in target_path.iterdir() if d.is_dir()]

    if not subdirs:
        print("  ⚠️  没有找到分类目录")
    else:
        for subdir in subdirs:
            file_count = len(list(subdir.glob("*.txt")))
            print(f"  📁 {subdir.name}: {file_count} 个文件")

    # 检查索引文件
    index_file = target_path / "README.md"
    if index_file.exists():
        index_content = index_file.read_text(encoding='utf-8')
        print(f"\n✅ 索引文件存在: {index_file}")
        print(f"   大小: {len(index_content)} 字符")

        # 检查基本内容
        if "#" in index_content:
            print("   包含标题结构")
        if "|" in index_content:
            print("   包含表格")
    else:
        print(f"\n❌ 索引文件不存在: {index_file}")

    # 总文件数
    total_files = sum(len(list(d.glob("*.txt"))) for d in target_path.iterdir() if d.is_dir())
    print(f"\n📊 总文件数: {total_files}")


def test_improved_agent():
    """测试改进版 Agent（需要 API）"""
    print("\n" + "="*60)
    print("测试改进版 Agent（需要 API）")
    print("="*60)

    # 检查环境变量
    if not os.getenv("siliconflow1"):
        print("⚠️  警告: 未设置 siliconflow1 环境变量")
        print("将跳过在线测试")
        return

    try:
        # 导入改进版 Agent
        from agent_improved import organize_notes_improved

        print("运行改进版 Agent...")
        organize_notes_improved("test_notes", "test_organized_improved")

        # 验证结果
        verify_results("test_organized_improved")

    except ImportError as e:
        print(f"导入失败: {e}")
        print("请确保已安装依赖")
    except Exception as e:
        print(f"运行失败: {e}")
        import traceback
        traceback.print_exc()


def cleanup_test_environment():
    """清理测试环境"""
    print("\n" + "="*60)
    print("清理测试环境")
    print("="*60)

    test_dirs = ["test_notes", "test_organized", "test_organized_improved", "test_results"]

    for dir_path in test_dirs:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"清理目录: {dir_path}")
            except Exception as e:
                print(f"清理失败 {dir_path}: {e}")


def main():
    """主测试函数"""
    print("="*60)
    print("改进版笔记分类 Agent 测试")
    print("="*60)

    try:
        # 设置测试环境
        setup_test_environment()

        # 测试工具函数
        test_tools()

        # 离线分类测试
        test_offline_classification()

        # 测试改进版 Agent（可选）
        user_input = input("\n是否运行在线测试? (需要 API 密钥) (y/n): ").strip().lower()
        if user_input == 'y':
            test_improved_agent()

        # 清理（可选）
        user_input = input("\n是否清理测试环境? (y/n): ").strip().lower()
        if user_input == 'y':
            cleanup_test_environment()
        else:
            print("保留测试环境")

    except KeyboardInterrupt:
        print("\n测试被用户中断")
        cleanup_test_environment()
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        cleanup_test_environment()


if __name__ == "__main__":
    main()