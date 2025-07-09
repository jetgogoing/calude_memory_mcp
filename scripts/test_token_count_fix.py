#!/usr/bin/env python3
"""
测试token_count字段修复
验证MemoryUnitModel的token_count字段是否可以正常访问和使用
"""

import sys
import uuid
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/home/jetgogoing/claude_memory/src')

try:
    from claude_memory.models.data_models import MemoryUnitModel, MemoryUnitType
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)

def test_memory_unit_token_count():
    """测试MemoryUnitModel的token_count字段"""
    print("=" * 60)
    print("测试MemoryUnitModel的token_count字段")
    print("=" * 60)
    
    try:
        # 创建MemoryUnitModel实例
        memory_unit = MemoryUnitModel(
            id=str(uuid.uuid4()),
            project_id="test_project",
            conversation_id=str(uuid.uuid4()),
            unit_type=MemoryUnitType.CONVERSATION,
            title="测试记忆单元",
            summary="这是一个测试用的记忆单元摘要",
            content="这是测试记忆单元的内容，用于验证token_count字段功能。",
            keywords=["测试", "token_count", "修复"],
            relevance_score=0.85,
            token_count=42  # 设置token计数
        )
        
        print("✅ 成功创建MemoryUnitModel实例")
        
        # 测试token_count字段访问
        print(f"📊 Token Count: {memory_unit.token_count}")
        
        # 测试字段修改
        memory_unit.token_count = 100
        print(f"📊 更新后的Token Count: {memory_unit.token_count}")
        
        # 测试字段赋值（模拟semantic_compressor中的使用）
        calculated_tokens = len(memory_unit.content.split())  # 简单的token计算
        memory_unit.token_count = calculated_tokens
        print(f"📊 计算后的Token Count: {memory_unit.token_count}")
        
        # 验证所有必需字段都存在
        required_fields = [
            'id', 'project_id', 'conversation_id', 'unit_type', 
            'title', 'summary', 'content', 'token_count'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not hasattr(memory_unit, field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ 缺失字段: {missing_fields}")
            return False
        else:
            print("✅ 所有必需字段都存在")
        
        # 测试模型转换为字典
        model_dict = memory_unit.model_dump()
        if 'token_count' in model_dict:
            print(f"✅ model_dump()包含token_count: {model_dict['token_count']}")
        else:
            print("❌ model_dump()不包含token_count字段")
            return False
        
        print("\n🎉 所有token_count字段测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_field_consistency():
    """测试字段一致性（简化版本）"""
    print("\n" + "=" * 60)
    print("测试MemoryUnitModel字段一致性")
    print("=" * 60)
    
    try:
        # 创建实例并检查关键字段
        memory_unit = MemoryUnitModel(
            conversation_id=str(uuid.uuid4()),
            unit_type=MemoryUnitType.DOCUMENTATION,
            title="字段测试",
            summary="测试字段一致性",
            content="测试内容"
        )
        
        # 检查新添加的字段
        essential_fields = {
            'token_count': int,
            'is_active': bool,
            'keywords': list,  # 现在是Optional[List[str]]，可以是None或list
        }
        
        all_good = True
        for field_name, expected_type in essential_fields.items():
            if hasattr(memory_unit, field_name):
                field_value = getattr(memory_unit, field_name)
                if field_name == 'keywords' and field_value is None:
                    # keywords字段现在是可选的，None是有效值
                    print(f"✅ {field_name}: None (可选字段)")
                elif isinstance(field_value, expected_type):
                    print(f"✅ {field_name}: {field_value} ({type(field_value).__name__})")
                else:
                    print(f"❌ {field_name}: 类型不匹配，期望{expected_type}，实际{type(field_value)}")
                    all_good = False
            else:
                print(f"❌ 缺少字段: {field_name}")
                all_good = False
        
        if all_good:
            print("\n✅ 字段一致性测试通过！")
            return True
        else:
            print("\n❌ 字段一致性测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 字段一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Claude Memory MCP Service - Token Count修复测试")
    print("时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # 运行测试
    test1_passed = test_memory_unit_token_count()
    test2_passed = test_field_consistency()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"Token Count字段测试: {'✅ 通过' if test1_passed else '❌ 失败'}")
    print(f"字段一致性测试: {'✅ 通过' if test2_passed else '❌ 失败'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过！修复成功。")
        print("\n下一步建议:")
        print("1. 重启Claude Memory API服务器")
        print("2. 运行完整的集成测试")
        print("3. 验证semantic_compressor在实际场景中的工作情况")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败，请检查修复。")
        sys.exit(1)