#!/usr/bin/env python3
"""
Claude Memory 全局数据库初始化脚本
自动发现并迁移现有项目数据库到全局Schema
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import logging

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from global_mcp.database_migrator import DatabaseMigrator


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("init_global_database")


def find_search_paths() -> List[str]:
    """查找可能的搜索路径"""
    search_paths = []
    
    # 当前用户主目录
    home_dir = Path.home()
    search_paths.append(str(home_dir))
    
    # 常见开发目录
    dev_dirs = [
        "Documents",
        "Projects", 
        "Development",
        "Code",
        "Workspace",
        "repos",
        "src"
    ]
    
    for dev_dir in dev_dirs:
        dev_path = home_dir / dev_dir
        if dev_path.exists():
            search_paths.append(str(dev_path))
    
    # 从环境变量获取额外路径
    if "CLAUDE_MEMORY_SEARCH_PATHS" in os.environ:
        extra_paths = os.environ["CLAUDE_MEMORY_SEARCH_PATHS"].split(":")
        search_paths.extend(extra_paths)
    
    return search_paths


def interactive_migration_selection(discovered_dbs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """交互式迁移选择"""
    if not discovered_dbs:
        print("未发现任何Claude Memory数据库")
        return []
    
    print(f"\n发现 {len(discovered_dbs)} 个Claude Memory数据库:")
    print("-" * 80)
    
    for i, db_info in enumerate(discovered_dbs, 1):
        print(f"{i:2d}. 项目: {db_info['project_name']}")
        print(f"    路径: {db_info['project_path']}")
        print(f"    类型: {db_info['project_type']}")
        print(f"    对话: {db_info['conversation_count']} | 消息: {db_info['message_count']}")
        print(f"    数据库: {db_info['db_path']}")
        print()
    
    print("选择要迁移的数据库 (输入序号，多个用逗号分隔，'all'表示全部，'none'跳过):")
    choice = input("请选择: ").strip()
    
    if choice.lower() in ['none', 'skip', '']:
        return []
    
    if choice.lower() == 'all':
        return discovered_dbs
    
    # 解析选择的序号
    selected = []
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(',')]
        for idx in indices:
            if 0 <= idx < len(discovered_dbs):
                selected.append(discovered_dbs[idx])
    except ValueError:
        print("输入格式错误，跳过选择")
        return []
    
    return selected


def run_migration(
    global_db_path: str,
    search_paths: List[str] = None,
    auto_migrate: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """运行迁移过程"""
    logger = logging.getLogger("migration")
    
    # 初始化迁移器
    migrator = DatabaseMigrator(global_db_path, logger)
    
    # 确保全局数据库Schema
    if not migrator.ensure_global_schema():
        return {"success": False, "error": "全局数据库Schema创建失败"}
    
    # 发现现有数据库
    if not search_paths:
        search_paths = find_search_paths()
    
    logger.info(f"搜索路径: {search_paths}")
    discovered_dbs = migrator.discover_project_databases(search_paths)
    
    if not discovered_dbs:
        logger.info("未发现任何现有Claude Memory数据库")
        return {
            "success": True,
            "discovered_count": 0,
            "migrated_count": 0,
            "migrations": []
        }
    
    # 选择要迁移的数据库
    if auto_migrate:
        selected_dbs = discovered_dbs
    else:
        selected_dbs = interactive_migration_selection(discovered_dbs)
    
    if not selected_dbs:
        logger.info("未选择任何数据库进行迁移")
        return {
            "success": True,
            "discovered_count": len(discovered_dbs),
            "migrated_count": 0,
            "migrations": []
        }
    
    # 执行迁移
    migration_results = []
    total_conversations = 0
    total_messages = 0
    
    for db_info in selected_dbs:
        logger.info(f"迁移数据库: {db_info['project_name']} ({db_info['db_path']})")
        
        project_context = {
            "project_name": db_info["project_name"],
            "project_path": db_info["project_path"],
            "project_type": db_info["project_type"]
        }
        
        result = migrator.migrate_project_database(
            db_info["db_path"],
            project_context,
            dry_run=dry_run
        )
        
        migration_results.append(result)
        
        if result.get("success", False):
            total_conversations += result.get("conversations_migrated", 0)
            total_messages += result.get("messages_migrated", 0)
            logger.info(f"✓ 迁移完成: {result['conversations_migrated']} 对话, {result['messages_migrated']} 消息")
        else:
            logger.error(f"✗ 迁移失败: {result.get('error', '未知错误')}")
    
    # 生成迁移报告
    if not dry_run:
        migration_report = migrator.get_migration_report()
    else:
        migration_report = {"dry_run": True}
    
    return {
        "success": True,
        "discovered_count": len(discovered_dbs),
        "selected_count": len(selected_dbs),
        "migrated_count": sum(1 for r in migration_results if r.get("success", False)),
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "migrations": migration_results,
        "migration_report": migration_report,
        "dry_run": dry_run
    }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Claude Memory 全局数据库初始化")
    
    parser.add_argument(
        "--global-db",
        default=str(Path.home() / ".claude-memory" / "data" / "global_memory.db"),
        help="全局数据库路径"
    )
    
    parser.add_argument(
        "--search-paths",
        nargs="+",
        help="搜索路径列表"
    )
    
    parser.add_argument(
        "--auto-migrate",
        action="store_true",
        help="自动迁移所有发现的数据库"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干运行模式，只统计不实际迁移"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别"
    )
    
    parser.add_argument(
        "--output",
        help="输出报告到JSON文件"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_level)
    
    # 确保全局数据目录存在
    global_db_path = Path(args.global_db)
    global_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("Claude Memory 全局数据库初始化")
    logger.info("=" * 60)
    logger.info(f"全局数据库路径: {global_db_path}")
    
    if args.dry_run:
        logger.info("*** 干运行模式 - 不会实际修改数据 ***")
    
    # 运行迁移
    try:
        result = run_migration(
            global_db_path=str(global_db_path),
            search_paths=args.search_paths,
            auto_migrate=args.auto_migrate,
            dry_run=args.dry_run
        )
        
        # 输出结果
        if result["success"]:
            logger.info(f"✓ 初始化完成!")
            logger.info(f"  发现数据库: {result['discovered_count']}")
            logger.info(f"  成功迁移: {result['migrated_count']}")
            logger.info(f"  总对话数: {result['total_conversations']}")
            logger.info(f"  总消息数: {result['total_messages']}")
            
            # 保存报告
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                logger.info(f"报告已保存到: {args.output}")
            
            sys.exit(0)
        else:
            logger.error(f"✗ 初始化失败: {result.get('error', '未知错误')}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"初始化过程发生错误: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()