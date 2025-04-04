import json
import os
from collections import defaultdict
from openai import OpenAI
from autoprotege import ontTool, ontModel

# DeepSeek API配置
client = OpenAI(
    api_key="sk-9a8d3cdc298145af835645c2e03948ca",
    base_url="https://api.deepseek.com",
)
    
tools = [
    {
        "type": "function",
        "function": {
            "name": "extract_ontology_elements",
            "description": "从文本中提取本体要素（类、数据属性、对象属性、实例）",
            "parameters": {
                "type": "object",
                "properties": {
                    "classes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "super_class": {"type": "string"}
                            }
                        }
                    },
                    "data_properties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "domain": {"type": "string"}
                            }
                        }
                    },
                    "object_properties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "domain": {"type": "string"},
                                "range": {"type": "string"}
                            }
                        }
                    },
                    "individuals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "data_properties": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "property": {"type": "string"},
                                            "value": {"type": "string"}
                                        }
                                    }
                                },
                                "object_properties": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "property": {"type": "string"},
                                            "value": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
]

# 新增冲突解决工具
conflict_resolution_tool = [
    {
        "type": "function",
        "function": {
            "name": "resolve_ontology_conflicts",
            "description": "智能解决本体元素名称冲突的决策工具",
            "parameters": {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "conflict_name": {"type": "string"},
                                "action": {"type": "string", "enum": ["keep_class", "keep_dp", "keep_op", "keep_individual", "rename"]},
                                "new_name": {"type": "string", "description": "仅当action为rename时需要"},
                                "reason": {"type": "string"}
                            },
                            "required": ["conflict_name", "action"]
                        }
                    }
                },
                "required": ["decisions"]
            }
        }
    }
]

def split_text(text, max_length=20000):
    """将长文本分割为多个段落"""
    return [text[i:i+max_length] for i in range(0, len(text), max_length)]

def parse_text_to_ontology(text):
    """使用DeepSeek解析文本生成本体要素（带分块处理）"""
    text_chunks = split_text(text)
    all_elements = {
        "classes": [],
        "data_properties": [],
        "object_properties": [],
        "individuals": []
    }
    
    for chunk in text_chunks:
        messages = [{
            "role": "user",
            "content": f"请从以下文本中提取本体要素：\n{chunk}\n要求：识别类层次结构、数据属性、对象属性和具体实例。"
        }]
        
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "extract_ontology_elements"}},
                max_tokens=4096
            )
            
            if response.choices[0].message.tool_calls:
                args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
                # 合并处理结果
                all_elements["classes"].extend(args.get("classes", []))
                all_elements["data_properties"].extend(args.get("data_properties", []))
                all_elements["object_properties"].extend(args.get("object_properties", []))
                all_elements["individuals"].extend(args.get("individuals", []))
                
        except Exception as e:
            print(f"处理文本块时发生错误: {str(e)}")
            continue
            
    return all_elements



def normalize_name(name, suffix=""):
    """标准化命名并添加后缀"""
    # 检查 name 是否为 None，若是则返回一个默认值
    if name is None:
        return f"Unknown{suffix}"
    
    # 正常情况下进行处理
    name = name.strip().replace(" ", "_").replace("#", "")
    return f"{name}{suffix}"

def collect_conflicts(elements):
    """收集所有跨类型名称冲突"""
    name_registry = defaultdict(set)
    
    # 遍历所有元素类型
    categories = {
        "classes": lambda x: x["name"],
        "data_properties": lambda x: x["name"],
        "object_properties": lambda x: x["name"],
        "individuals": lambda x: x["name"]
    }
    
    for cat, get_name in categories.items():
        for element in elements.get(cat, []):
            name = get_name(element)
            name_registry[name].add(cat)
    
    # 过滤出有冲突的名称
    return {name: cats for name, cats in name_registry.items() if len(cats) > 1}

def generate_conflict_prompt(conflicts):
    """生成用于AI决策的提示"""
    conflict_list = []
    for name, categories in conflicts.items():
        cat_names = {
            "classes": "类",
            "data_properties": "数据属性",
            "object_properties": "对象属性",
            "individuals": "实例"
        }
        categories_str = "、".join([cat_names[c] for c in categories])
        conflict_list.append(f"名称 '{name}' 同时存在于：{categories_str}")
    
    return (
        "请根据以下规则解决本体元素名称冲突：\n"
        "1. 优先保留类定义（当冲突涉及类和其他类型时）\n"
        "2. 其次保留对象属性（当冲突涉及对象属性和其他非类类型时）\n"
        "3. 实例与属性冲突时优先保留实例\n"
        "4. 如果多个同类元素冲突，添加数字后缀（如：飞行模型_1）\n\n"
        "需要解决的冲突列表：\n" + 
        "\n".join(conflict_list) + "\n\n"
        "请用JSON格式返回解决方案，包含每个冲突的解决方式和理由。"
    )

def resolve_conflicts_with_ai(elements):
    """调用DeepSeek进行智能冲突解决"""
    conflicts = collect_conflicts(elements)
    if not conflicts:
        return elements
    
    prompt = generate_conflict_prompt(conflicts)
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            tools=conflict_resolution_tool,
            tool_choice={"type": "function", "function": {"name": "resolve_ontology_conflicts"}},
            max_tokens=2000
        )
        
        if not response.choices[0].message.tool_calls:
            raise ValueError("未返回有效解决方案")
        
        solution = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        return apply_ai_solution(elements, solution["decisions"])
    
    except Exception as e:
        print(f"\033[33mAI冲突解决失败: {str(e)}，使用备用方案\033[0m")
        return apply_fallback_solution(elements)

def apply_ai_solution(elements, decisions):
    """应用AI生成的解决方案"""
    # 构建解决方案映射
    decision_map = {d["conflict_name"]: d for d in decisions}
    
    # 处理每个类别的元素
    for category in ["classes", "data_properties", "object_properties", "individuals"]:
        new_elements = []
        seen_names = set()
        
        for element in elements[category]:
            orig_name = element["name"]
            
            if orig_name in decision_map:
                decision = decision_map[orig_name]
                
                # 根据决策类型处理
                if decision["action"] == "rename":
                    element["name"] = decision.get("new_name", f"{orig_name}_1")
                elif not decision_matches_category(decision["action"], category):
                    continue  # 跳过不保留的元素
                
            # 处理同类冲突
            if element["name"] in seen_names:
                element["name"] = generate_unique_name(element["name"], seen_names)
            
            seen_names.add(element["name"])
            new_elements.append(element)
        
        elements[category] = new_elements
    
    return elements

def decision_matches_category(action, category):
    """判断决策动作与当前类别是否匹配"""
    mapping = {
        "keep_class": "classes",
        "keep_dp": "data_properties",
        "keep_op": "object_properties",
        "keep_individual": "individuals"
    }
    return mapping.get(action, "") == category

def generate_unique_name(base_name, existing_names, suffix=1):
    """生成带数字后缀的唯一名称"""
    while f"{base_name}_{suffix}" in existing_names:
        suffix += 1
    return f"{base_name}_{suffix}"

def apply_fallback_solution(elements):
    """备用解决方案：基于优先级删除冲突项"""
    priority_order = ["classes", "object_properties", "individuals", "data_properties"]
    seen_names = set()
    
    for category in priority_order:
        filtered = []
        for element in elements[category]:
            name = element["name"]
            if name not in seen_names:
                seen_names.add(name)
                filtered.append(element)
        elements[category] = filtered
    
    return elements

def apply_naming_convention(elements):
    """应用命名规范（预防措施）"""
    # 类添加_Class后缀
    for cls in elements["classes"]:
        cls["name"] = normalize_name(cls["name"], "_Class")
        # 确保 super_class 键存在且不为 None 再进行正规化
        if "super_class" in cls and cls["super_class"] is not None:
            cls["super_class"] = normalize_name(cls["super_class"], "_Class")
    
    # 数据属性添加_DP后缀
    for dp in elements["data_properties"]:
        dp["name"] = normalize_name(dp["name"], "_DP")
        # 确保 domain 键存在且不为 None 再进行正规化
        if "domain" in dp and dp["domain"] is not None:
            dp["domain"] = normalize_name(dp["domain"], "_Class")
    
    # 对象属性添加_OP后缀
    for op in elements["object_properties"]:
        op["name"] = normalize_name(op["name"], "_OP")
        # 确保 domain 和 range 键存在且不为 None 再进行正规化
        if "domain" in op and op["domain"] is not None:
            op["domain"] = normalize_name(op["domain"], "_Class")
        if "range" in op and op["range"] is not None:
            op["range"] = normalize_name(op["range"], "_Class")
    
    # 实例保持原名但规范化
    for ind in elements["individuals"]:
        ind["name"] = normalize_name(ind["name"])
        if "type" in ind and ind["type"] is not None:
            ind["type"] = normalize_name(ind["type"], "_Class")
        
        # 处理属性引用
        for dp in ind.get("data_properties", []):
            if "property" in dp and dp["property"] is not None:
                dp["property"] = normalize_name(dp["property"], "_DP")
        for op in ind.get("object_properties", []):
            if "property" in op and op["property"] is not None:
                dp["property"] = normalize_name(dp["property"], "_OP")
            if "value" in op and op["value"] is not None:
                op["value"] = normalize_name(op["value"])
    
    return elements

def build_ontology(domain_name, elements, output_path):
    """使用AutoProtégé构建本体（整合智能冲突解决）"""
    try:
        # 1. 应用命名规范
        elements = apply_naming_convention(elements)
        
        # 2. 智能冲突解决
        elements = resolve_conflicts_with_ai(elements)
        
        # 3. 最终冲突检测
        final_conflicts = collect_conflicts(elements)
        if final_conflicts:
            conflict_list = [f"名称 '{name}' 在 {', '.join(cats)} 中存在冲突" 
                            for name, cats in final_conflicts.items()]
            raise ValueError("\n".join(["剩余未解决冲突:"] + conflict_list))
        
        # 4. 构建本体（原始逻辑）
        owl = ontTool.initial_owl(domain_name)
        owl_dict = ontTool.split_owl(owl, domain_name)
        
        # 类处理
        for cls in elements["classes"]:
            new_class = ontModel.OneClass(domain_name, cls["name"], None)
            if "super_class" in cls and cls["super_class"]:
                new_class.addSuperClass(cls["super_class"])  # 已经在 apply_naming_convention 中正规化
            owl_dict["classesList"].append(new_class)
        
        # 数据属性处理
        for dp in elements["data_properties"]:
            new_dp = ontModel.DP(domain_name, dp["name"], None)
            if "domain" in dp and dp["domain"]:
                new_dp.addDomain(dp["domain"])  # 已经在 apply_naming_convention 中正规化
            owl_dict["dpList"].append(new_dp)
        
        # 对象属性处理
        for op in elements["object_properties"]:
            new_op = ontModel.OP(domain_name, op["name"], None)
            if "domain" in op and op["domain"]:
                new_op.addDomain(op["domain"])  # 已经在 apply_naming_convention 中正规化
            if "range" in op and op["range"]:
                new_op.addRange(op["range"])  # 已经在 apply_naming_convention 中正规化
            owl_dict["opList"].append(new_op)
        
        # 实例处理
        for ind in elements["individuals"]:
            entity = ontModel.Individual(domain_name, ind["name"], None)
            if "type" in ind and ind["type"]:
                entity.addType(ind["type"])  # 已经在 apply_naming_convention 中正规化
            
            for dp in ind.get("data_properties", []):
                if "property" in dp and dp["property"] and "value" in dp:
                    entity.addDataProperty(
                        dp["property"],  # 已经在 apply_naming_convention 中正规化
                        dp["value"] if dp["value"] is not None else ""
                    )
            
            for op in ind.get("object_properties", []):
                if "property" in op and op["property"] and "value" in op and op["value"]:
                    entity.addObjectProperty(
                        op["property"],  # 已经在 apply_naming_convention 中正规化
                        op["value"]  # 已经在 apply_naming_convention 中正规化
                    )
            
            owl_dict["indsList"].append(entity)
        
        # 保存本体
        merged_owl = ontTool.merge_owl(owl_dict)
        ontTool.write_owl(merged_owl, output_path)
        return True
    
    except Exception as e:
        print(f"\033[31m本体构建失败: {str(e)}\033[0m")
        import traceback
        traceback.print_exc()  # 打印详细的堆栈跟踪以便调试
        return False

def process_file(input_txt, output_owl, domain="MyDomain"):
    """处理输入文件生成本体"""
    try:
        with open(input_txt, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"\033[31m错误：找不到输入文件 {input_txt}\033[0m")
        print(f"当前工作目录：{os.getcwd()}")
        print(f"目录内容：{os.listdir()}")
        return
    
    print(f"正在处理文本（长度：{len(text)}字符）...")
    elements = parse_text_to_ontology(text)
    
    if elements:
        print(f"提取到本体要素：")
        print(f"- 类: {len(elements['classes'])}个")
        print(f"- 数据属性: {len(elements['data_properties'])}个")
        print(f"- 对象属性: {len(elements['object_properties'])}个")
        print(f"- 实例: {len(elements['individuals'])}个")
        
        if build_ontology(domain, elements, output_owl):
            print(f"\033[32m本体已成功生成至：{output_owl}\033[0m")
        else:
            print("\033[31m本体生成失败，请检查上述错误信息\033[0m")
    else:
        print("\033[33m未能从文本中提取有效信息\033[0m")

if __name__ == "__main__":
    process_file(
        input_txt="input.txt",
        output_owl="output.owl"
    )