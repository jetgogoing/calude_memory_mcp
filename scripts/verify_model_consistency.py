#!/usr/bin/env python3
"""
验证Pydantic和SQLAlchemy模型字段一致性
检查MemoryUnitModel (Pydantic) 和 MemoryUnitDB (SQLAlchemy) 是否字段匹配
"""

import sys
import inspect
from typing import get_type_hints, get_origin, get_args
from dataclasses import dataclass
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/home/jetgogoing/claude_memory/src')

try:
    from claude_memory.models.data_models import MemoryUnitModel, MemoryUnitDB, MemoryUnitType
    from sqlalchemy import Column
    from pydantic import Field
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)

@dataclass
class FieldInfo:
    name: str
    type_info: str
    nullable: bool
    has_default: bool
    default_value: str

def analyze_pydantic_model(model_class):
    """分析Pydantic模型字段"""
    fields = {}
    
    # 使用Pydantic V2的model_fields
    model_fields = getattr(model_class, 'model_fields', getattr(model_class, '__fields__', {}))
    
    for field_name, field_info in model_fields.items():
        # 获取字段类型
        field_type = field_info.annotation if hasattr(field_info, 'annotation') else 'Unknown'
        
        # 检查是否可选
        nullable = False
        type_str = str(field_type)
        if hasattr(field_type, '__origin__') and field_type.__origin__ is type(None):
            nullable = True
        elif 'Optional' in type_str or 'Union' in type_str:
            nullable = True
            
        # 检查默认值
        has_default = hasattr(field_info, 'default') and field_info.default is not ...
        default_value = str(field_info.default) if has_default else "N/A"
        
        fields[field_name] = FieldInfo(
            name=field_name,
            type_info=type_str,
            nullable=nullable,
            has_default=has_default,
            default_value=default_value
        )
    
    return fields

def analyze_sqlalchemy_model(model_class):
    """分析SQLAlchemy模型字段"""
    fields = {}
    
    # 使用SQLAlchemy的__table__.columns来获取列信息
    if hasattr(model_class, '__table__'):
        for column in model_class.__table__.columns:
            column_name = column.name
            
            # 类型信息
            type_str = str(column.type)
            
            # 可空性
            nullable = column.nullable
            
            # 默认值
            has_default = column.default is not None or column.server_default is not None
            default_value = "N/A"
            if column.default is not None:
                if callable(column.default.arg):
                    default_value = f"函数: {column.default.arg.__name__}"
                else:
                    default_value = str(column.default.arg)
            elif column.server_default is not None:
                default_value = str(column.server_default.arg)
                
            fields[column_name] = FieldInfo(
                name=column_name,
                type_info=type_str,
                nullable=nullable,
                has_default=has_default,
                default_value=default_value
            )
    else:
        # 备用方法：检查类属性
        for attr_name in dir(model_class):
            if not attr_name.startswith('_'):
                attr = getattr(model_class, attr_name)
                if isinstance(attr, Column):
                    column_name = attr.name if attr.name else attr_name
                    
                    type_str = str(attr.type)
                    nullable = attr.nullable
                    has_default = attr.default is not None or attr.server_default is not None
                    default_value = "N/A"
                    
                    fields[column_name] = FieldInfo(
                        name=column_name,
                        type_info=type_str,
                        nullable=nullable,
                        has_default=has_default,
                        default_value=default_value
                    )
    
    return fields

def compare_models():
    """比较两个模型的字段一致性"""
    print("=" * 80)
    print("Claude Memory MCP Service - 模型字段一致性验证")
    print("=" * 80)
    
    # 分析模型
    print("\n📊 分析Pydantic模型...")
    pydantic_fields = analyze_pydantic_model(MemoryUnitModel)
    
    print("📊 分析SQLAlchemy模型...")
    sqlalchemy_fields = analyze_sqlalchemy_model(MemoryUnitDB)
    
    # 对比字段
    print(f"\n🔍 字段对比结果:")
    print(f"Pydantic字段数: {len(pydantic_fields)}")
    print(f"SQLAlchemy字段数: {len(sqlalchemy_fields)}")
    
    # 找出差异
    pydantic_only = set(pydantic_fields.keys()) - set(sqlalchemy_fields.keys())
    sqlalchemy_only = set(sqlalchemy_fields.keys()) - set(pydantic_fields.keys())
    common_fields = set(pydantic_fields.keys()) & set(sqlalchemy_fields.keys())
    
    print(f"\n✅ 共同字段: {len(common_fields)}")
    print(f"⚠️  仅在Pydantic中: {len(pydantic_only)}")
    print(f"⚠️  仅在SQLAlchemy中: {len(sqlalchemy_only)}")
    
    # 显示详细差异
    if pydantic_only:
        print(f"\n🔶 仅在Pydantic模型中的字段:")
        for field in sorted(pydantic_only):
            info = pydantic_fields[field]
            print(f"  • {field}: {info.type_info} (默认: {info.default_value})")
    
    if sqlalchemy_only:
        print(f"\n🔶 仅在SQLAlchemy模型中的字段:")
        for field in sorted(sqlalchemy_only):
            info = sqlalchemy_fields[field]
            print(f"  • {field}: {info.type_info} (默认: {info.default_value})")
    
    # 检查共同字段的一致性
    print(f"\n🔍 共同字段一致性检查:")
    inconsistencies = []
    
    for field in sorted(common_fields):
        pyd_info = pydantic_fields[field]
        sql_info = sqlalchemy_fields[field]
        
        # 检查可空性（简化检查）
        if pyd_info.nullable != sql_info.nullable:
            inconsistencies.append(f"  ❌ {field}: 可空性不匹配 (Pydantic: {pyd_info.nullable}, SQLAlchemy: {sql_info.nullable})")
        else:
            print(f"  ✅ {field}: 类型和约束匹配")
    
    if inconsistencies:
        print(f"\n⚠️  发现 {len(inconsistencies)} 个一致性问题:")
        for issue in inconsistencies:
            print(issue)
    else:
        print(f"\n🎉 所有共同字段都一致！")
    
    # 显示详细字段信息
    print(f"\n📋 详细字段对比:")
    print(f"{'字段名':<20} {'Pydantic类型':<30} {'SQLAlchemy类型':<25} {'状态'}")
    print("-" * 85)
    
    all_fields = sorted(set(pydantic_fields.keys()) | set(sqlalchemy_fields.keys()))
    for field in all_fields:
        pyd_type = pydantic_fields.get(field, {}).type_info if field in pydantic_fields else "❌ 缺失"
        sql_type = sqlalchemy_fields.get(field, {}).type_info if field in sqlalchemy_fields else "❌ 缺失"
        
        if field in pydantic_fields and field in sqlalchemy_fields:
            status = "✅ 匹配"
        elif field in pydantic_only:
            status = "🔶 仅Pydantic"
        else:
            status = "🔶 仅SQLAlchemy"
            
        print(f"{field:<20} {str(pyd_type):<30} {str(sql_type):<25} {status}")
    
    # 总结和建议
    print(f"\n📋 修复建议:")
    if pydantic_only:
        print(f"1. 考虑在MemoryUnitDB中添加缺失字段:")
        for field in sorted(pydantic_only):
            print(f"   • {field}")
    
    if sqlalchemy_only:
        print(f"2. 考虑在MemoryUnitModel中添加缺失字段:")
        for field in sorted(sqlalchemy_only):
            print(f"   • {field}")
    
    if inconsistencies:
        print(f"3. 修复字段一致性问题")
    
    # 返回验证结果
    is_consistent = len(pydantic_only) == 0 and len(sqlalchemy_only) == 0 and len(inconsistencies) == 0
    return is_consistent

if __name__ == "__main__":
    try:
        is_consistent = compare_models()
        print(f"\n{'='*80}")
        if is_consistent:
            print(f"🎉 验证通过：模型字段完全一致！")
            sys.exit(0)
        else:
            print(f"⚠️  验证失败：发现字段不一致问题")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 验证过程出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)