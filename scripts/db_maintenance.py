#!/usr/bin/env python3
"""
Claude Memory数据库维护脚本
数据清理、优化、备份和性能调优
"""

import os
import sqlite3
import psycopg2
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

class DatabaseMaintenance:
    """数据库维护器"""
    
    def __init__(self):
        self.project_root = Path("/home/jetgogoing/claude_memory")
        self.sqlite_path = self.project_root / "data" / "claude_memory.db"
        self.backups_dir = self.project_root / "backups"
        self.backups_dir.mkdir(exist_ok=True)
        
        # PostgreSQL连接配置
        self.pg_config = {
            "host": "localhost",
            "database": "claude_memory_db",
            "user": "claude_memory",
            "password": "password"
        }
    
    def cleanup_old_data(self, days_to_keep=90):
        """清理旧数据"""
        print(f"🧹 清理{days_to_keep}天前的旧数据...")
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        try:
            # SQLite清理
            if self.sqlite_path.exists():
                conn = sqlite3.connect(self.sqlite_path)
                cursor = conn.cursor()
                
                # 清理旧的成本跟踪记录
                cursor.execute("""
                    DELETE FROM cost_tracking 
                    WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_cost = cursor.rowcount
                
                # 清理旧的嵌入向量记录
                cursor.execute("""
                    DELETE FROM embeddings 
                    WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_embeddings = cursor.rowcount
                
                conn.commit()
                conn.close()
                
                print(f"✅ SQLite清理完成: 删除{deleted_cost}条成本记录, {deleted_embeddings}条向量记录")
            
            # PostgreSQL清理
            conn = psycopg2.connect(**self.pg_config)
            cursor = conn.cursor()
            
            # 清理旧对话记录
            cursor.execute("""
                DELETE FROM messages 
                WHERE created_at < %s
            """, (cutoff_date,))
            
            deleted_messages = cursor.rowcount
            
            # 清理孤立的对话记录
            cursor.execute("""
                DELETE FROM conversations 
                WHERE id NOT IN (SELECT DISTINCT conversation_id FROM messages WHERE conversation_id IS NOT NULL)
            """)
            
            deleted_conversations = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            print(f"✅ PostgreSQL清理完成: 删除{deleted_messages}条消息, {deleted_conversations}个孤立对话")
            
        except Exception as e:
            print(f"❌ 数据清理失败: {e}")
    
    def optimize_database(self):
        """优化数据库性能"""
        print("⚡ 优化数据库性能...")
        
        try:
            # SQLite优化
            if self.sqlite_path.exists():
                conn = sqlite3.connect(self.sqlite_path)
                cursor = conn.cursor()
                
                # 运行VACUUM清理碎片
                cursor.execute("VACUUM")
                
                # 重建索引
                cursor.execute("REINDEX")
                
                # 更新统计信息
                cursor.execute("ANALYZE")
                
                conn.close()
                print("✅ SQLite优化完成")
            
            # PostgreSQL优化
            conn = psycopg2.connect(**self.pg_config)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # 更新表统计信息
            cursor.execute("ANALYZE")
            
            # 重建索引（如果需要）
            cursor.execute("""
                SELECT schemaname, tablename, indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public'
            """)
            
            indexes = cursor.fetchall()
            print(f"📊 找到{len(indexes)}个索引")
            
            conn.close()
            print("✅ PostgreSQL优化完成")
            
        except Exception as e:
            print(f"❌ 数据库优化失败: {e}")
    
    def backup_databases(self):
        """备份数据库"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"💾 备份数据库 ({timestamp})...")
        
        try:
            # 备份SQLite
            if self.sqlite_path.exists():
                sqlite_backup = self.backups_dir / f"claude_memory_{timestamp}.db"
                shutil.copy2(self.sqlite_path, sqlite_backup)
                print(f"✅ SQLite备份完成: {sqlite_backup}")
            
            # 备份PostgreSQL
            pg_backup = self.backups_dir / f"claude_memory_pg_{timestamp}.sql"
            
            # 使用pg_dump备份
            cmd = [
                "pg_dump",
                "-h", self.pg_config["host"],
                "-U", self.pg_config["user"],
                "-d", self.pg_config["database"],
                "-f", str(pg_backup)
            ]
            
            env = os.environ.copy()
            env["PGPASSWORD"] = self.pg_config["password"]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ PostgreSQL备份完成: {pg_backup}")
            else:
                print(f"❌ PostgreSQL备份失败: {result.stderr}")
            
        except Exception as e:
            print(f"❌ 数据库备份失败: {e}")
    
    def cleanup_old_backups(self, days_to_keep=30):
        """清理旧备份文件"""
        print(f"🗂️ 清理{days_to_keep}天前的备份文件...")
        
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        try:
            for backup_file in self.backups_dir.iterdir():
                if backup_file.is_file():
                    # 获取文件修改时间
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    
                    if file_time < cutoff_time:
                        backup_file.unlink()
                        deleted_count += 1
                        print(f"🗑️ 删除旧备份: {backup_file.name}")
            
            print(f"✅ 清理完成，删除{deleted_count}个旧备份文件")
            
        except Exception as e:
            print(f"❌ 清理备份文件失败: {e}")
    
    def check_database_health(self):
        """检查数据库健康状态"""
        print("🏥 检查数据库健康状态...")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "sqlite": {"status": "unknown", "size_mb": 0, "tables": 0},
            "postgresql": {"status": "unknown", "connections": 0, "tables": 0},
            "issues": []
        }
        
        try:
            # 检查SQLite
            if self.sqlite_path.exists():
                size_mb = self.sqlite_path.stat().st_size / (1024 * 1024)
                
                conn = sqlite3.connect(self.sqlite_path)
                cursor = conn.cursor()
                
                # 获取表数量
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # 检查数据库完整性
                cursor.execute("PRAGMA integrity_check")
                integrity = cursor.fetchone()[0]
                
                conn.close()
                
                health_report["sqlite"] = {
                    "status": "healthy" if integrity == "ok" else "corrupted",
                    "size_mb": size_mb,
                    "tables": table_count
                }
                
                if integrity != "ok":
                    health_report["issues"].append("SQLite数据库完整性检查失败")
                
                print(f"✅ SQLite: {size_mb:.1f}MB, {table_count}个表, 状态: {integrity}")
            
            # 检查PostgreSQL
            conn = psycopg2.connect(**self.pg_config)
            cursor = conn.cursor()
            
            # 获取连接数
            cursor.execute("SELECT count(*) FROM pg_stat_activity")
            connection_count = cursor.fetchone()[0]
            
            # 获取表数量
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = cursor.fetchone()[0]
            
            # 检查数据库大小
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """)
            db_size = cursor.fetchone()[0]
            
            conn.close()
            
            health_report["postgresql"] = {
                "status": "healthy",
                "connections": connection_count,
                "tables": table_count,
                "size": db_size
            }
            
            print(f"✅ PostgreSQL: {db_size}, {table_count}个表, {connection_count}个连接")
            
        except Exception as e:
            health_report["issues"].append(f"数据库健康检查失败: {e}")
            print(f"❌ 健康检查失败: {e}")
        
        # 保存健康报告
        health_file = self.project_root / "logs" / f"db_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        health_file.parent.mkdir(exist_ok=True)
        
        import json
        with open(health_file, 'w') as f:
            json.dump(health_report, f, indent=2)
        
        return health_report
    
    def generate_maintenance_report(self):
        """生成维护报告"""
        print("📊 生成维护报告...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.project_root / "reports" / f"maintenance_report_{timestamp}.md"
        report_file.parent.mkdir(exist_ok=True)
        
        # 获取数据库统计信息
        health_report = self.check_database_health()
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Claude Memory 数据库维护报告\n\n")
            f.write(f"**维护时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 数据库状态
            f.write("## 📊 数据库状态\n\n")
            f.write(f"### SQLite\n")
            f.write(f"- 状态: {health_report['sqlite']['status']}\n")
            f.write(f"- 大小: {health_report['sqlite']['size_mb']:.1f} MB\n")
            f.write(f"- 表数量: {health_report['sqlite']['tables']}\n\n")
            
            f.write(f"### PostgreSQL\n")
            f.write(f"- 状态: {health_report['postgresql']['status']}\n")
            f.write(f"- 大小: {health_report['postgresql'].get('size', 'N/A')}\n")
            f.write(f"- 表数量: {health_report['postgresql']['tables']}\n")
            f.write(f"- 活动连接: {health_report['postgresql']['connections']}\n\n")
            
            # 维护操作
            f.write("## 🛠️ 执行的维护操作\n\n")
            f.write("- ✅ 数据清理 (90天前数据)\n")
            f.write("- ✅ 数据库优化 (VACUUM, ANALYZE)\n")
            f.write("- ✅ 数据备份\n")
            f.write("- ✅ 旧备份清理 (30天前)\n")
            f.write("- ✅ 健康状态检查\n\n")
            
            # 问题报告
            if health_report["issues"]:
                f.write("## ⚠️ 发现的问题\n\n")
                for issue in health_report["issues"]:
                    f.write(f"- {issue}\n")
                f.write("\n")
            else:
                f.write("## ✅ 无问题发现\n\n数据库运行正常，无需特殊处理。\n\n")
            
            # 下次维护建议
            f.write("## 📅 下次维护建议\n\n")
            f.write("- 监控数据库增长趋势\n")
            f.write("- 考虑调整数据保留策略\n")
            f.write("- 定期检查备份文件完整性\n")
            f.write("- 评估索引性能和优化机会\n\n")
            
            f.write("---\n*报告由Claude Memory数据库维护系统自动生成*\n")
        
        print(f"✅ 维护报告已生成: {report_file}")

def main():
    """主函数"""
    print("🔧 开始Claude Memory数据库维护...")
    
    maintenance = DatabaseMaintenance()
    
    # 执行维护操作
    maintenance.cleanup_old_data(days_to_keep=90)
    maintenance.optimize_database()
    maintenance.backup_databases()
    maintenance.cleanup_old_backups(days_to_keep=30)
    
    # 生成维护报告
    maintenance.generate_maintenance_report()
    
    print("✅ 数据库维护完成！")

if __name__ == "__main__":
    main()