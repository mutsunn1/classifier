"""文件操作工具集"""
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any


def list_files(directory_path: str) -> List[Dict[str, Any]]:
    """获取指定目录下的所有文件列表"""
    files = []
    try:
        path = Path(directory_path)
        if not path.exists():
            return [{"success": False, "error": f"目录不存在: {directory_path}"}]
        
        for item in path.iterdir():
            if item.is_file():
                files.append({
                    "name": item.name,
                    "path": str(item),
                    "size": item.stat().st_size
                })
        return [{"success": True, "files": files}]
    except Exception as e:
        return [{"success": False, "error": str(e)}]


def read_file(file_path: str, max_lines: int = 50) -> str:
    """读取文件内容，默认最多读取前 N 行"""
    try:
        path = Path(file_path)
        if not path.exists():
            return f"错误: 文件不存在 {file_path}"
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[:max_lines]
            content = ''.join(lines)
            # 如果文件被截断，添加提示
            if len(f.readlines()) > max_lines:
                content += "\n... [文件内容已截断]"
            return content
    except Exception as e:
        return f"读取错误: {str(e)}"


def create_directory(dir_path: str) -> Dict[str, Any]:
    """创建目录"""
    try:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(path)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def move_file(source_path: str, destination_path: str) -> Dict[str, Any]:
    """移动文件"""
    try:
        src = Path(source_path)
        dst = Path(destination_path)
        
        if not src.exists():
            return {"success": False, "error": f"源文件不存在: {source_path}"}
        
        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果目标已存在，添加数字后缀
        counter = 1
        original_dst = dst
        while dst.exists():
            stem = original_dst.stem
            suffix = original_dst.suffix
            dst = original_dst.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        
        shutil.move(str(src), str(dst))
        return {"success": True, "from": source_path, "to": str(dst)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(file_path: str, content: str) -> Dict[str, Any]:
    """写入文件"""
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "path": str(path)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename_file(file_path: str, new_name: str) -> Dict[str, Any]:
    """重命名文件"""
    try:
        src = Path(file_path)
        if not src.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        dst = src.parent / new_name
        
        # 如果目标已存在，添加数字后缀
        counter = 1
        original_dst = dst
        while dst.exists():
            stem = original_dst.stem
            suffix = original_dst.suffix
            dst = original_dst.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        
        src.rename(dst)
        return {"success": True, "from": file_path, "to": str(dst)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# 工具映射表
TOOL_MAP = {
    "list_files": list_files,
    "read_file": read_file,
    "create_directory": create_directory,
    "move_file": move_file,
    "write_file": write_file,
    "rename_file": rename_file,
}
