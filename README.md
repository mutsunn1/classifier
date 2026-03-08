# 笔记自动整理 Agent

基于 LangGraph 的智能笔记分类整理工具，能够自动分析笔记内容，按学科分类归档，并生成索引文件。


## 配置 API Key

编辑 `config.py` 文件，填入你的 API Key:

```python
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
OPENAI_BASE_URL = "https://api.openai.com/v1"  # 可根据需要修改
OPENAI_MODEL = "gpt-4o-mini"  # 或其他支持的模型
```

## 使用方法

### 基本用法

```bash
# 使用默认路径（./notes -> ./organized_notes）
python agent.py

# 指定源目录和目标目录
python agent.py ./my_notes ./output
```

### 作为模块调用

```python
from agent import organize_notes

organize_notes(
    source_dir="./raw_notes",
    target_dir="./organized"
)
```


## 工具集说明

Agent 可使用的工具:

| 工具 | 功能 |
|------|------|
| `list_files` | 扫描目录文件列表 |
| `read_file` | 读取文件内容（默认前50行） |
| `create_directory` | 创建学科分类文件夹 |
| `move_file` | 移动文件到目标位置 |
| `write_file` | 创建 README.md 索引 |
| `rename_file` | 重命名文件 |

## 工作流程

1. **扫描** → 列出源目录所有文件
2. **分析** → 读取文件内容判断学科分类
3. **规划** → 确定分类方案和目录结构
4. **执行** → 创建文件夹、移动文件
5. **索引** → 生成 README.md 汇总文档
