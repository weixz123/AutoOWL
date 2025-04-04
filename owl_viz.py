import os
import difflib
import graphviz
import owlready2 as owl
from pathlib import Path

class OntologyVisualizer:
    def __init__(self, owl_path):
        self.owl_path = Path(owl_path)
        self.onto = None
        self._verify_ontology()
        
    def _verify_ontology(self):
        """验证本体文件有效性"""
        if not self.owl_path.exists():
            raise FileNotFoundError(f"OWL文件不存在: {self.owl_path}")
        if self.owl_path.suffix.lower() != ".owl":
            raise ValueError("仅支持OWL格式文件")
            
    def load_ontology(self):
        """加载本体文件"""
        try:
            onto_uri = f"file://{self.owl_path.resolve()}"
            self.onto = owl.get_ontology(onto_uri).load()
            print(f"成功加载本体: {self.onto.name}")
        except Exception as e:
            raise RuntimeError(f"本体加载失败: {str(e)}")
    
    def _search_entity(self, keyword):
        """关键词搜索本体实体"""
        classes = list(self.onto.classes())
        class_names = [c.name.lower() for c in classes]
        
        # 模糊匹配
        matches = difflib.get_close_matches(
            keyword.lower(), 
            class_names,
            n=3,
            cutoff=0.6
        )
        
        return [c for c in classes if c.name.lower() in matches]
    
    def _generate_knowledge_graph(self, entity):
        """生成实体知识图谱"""
        # 此处整合原始代码中的generate_knowledge_graph和相关辅助函数
        # 为简化示例保留核心逻辑，完整实现请参考原始函数
        
        graph = []
        
        # 添加父类和子类关系
        for parent in entity.is_a:
            if isinstance(parent, owl.ThingClass):
                graph.append((entity.name, "subClassOf", parent.name))
                
        for child in entity.subclasses():
            graph.append((child.name, "subClassOf", entity.name))
            
        # 添加数据属性
        for prop in self.onto.data_properties():
            if entity in prop.domain:
                graph.append((entity.name, "hasDataProperty", prop.name))
                
        # 添加对象属性
        for prop in self.onto.object_properties():
            if entity in prop.domain:
                for range_cls in prop.range:
                    graph.append((entity.name, prop.name, range_cls.name))
        
        return graph
    
    def visualize_entity(self, keyword, output_format="png"):
        """可视化指定实体的关系"""
        entities = self._search_entity(keyword)
        if not entities:
            print(f"未找到匹配'{keyword}'的实体")
            return
            
        main_entity = entities[0]
        graph_data = self._generate_knowledge_graph(main_entity)
        
        # 创建Graphviz图表
        dot = graphviz.Digraph(name=f"Ontology_{main_entity.name}")
        dot.attr(rankdir="TB", label=f"{self.onto.name} - {main_entity.name}")
        
        # 添加节点和边
        nodes = set()
        for edge in graph_data:
            nodes.add(edge[0])
            nodes.add(edge[2])
            
        for node in nodes:
            dot.node(node, shape="box" if node == main_entity.name else "ellipse")
            
        for src, label, dest in graph_data:
            dot.edge(src, dest, label=label)
            
        # 保存并渲染
        output_path = self.owl_path.parent / "visualizations"
        output_path.mkdir(exist_ok=True)
        
        dot.render(
            directory=str(output_path),
            format=output_format,
            filename=f"{main_entity.name}_graph",
            cleanup=True
        )
        
        print(f"可视化已保存至: {output_path}/{main_entity.name}_graph.{output_format}")
    


    def visualize_entity(self, keyword, output_format="png"):
        """可视化指定实体的关系"""
        entities = self._search_entity(keyword)
        if not entities:
            print(f"未找到匹配'{keyword}'的实体")
            return
            
        main_entity = entities[0]
        graph_data = self._generate_knowledge_graph(main_entity)
        
        # 创建Graphviz图表
        dot = graphviz.Digraph(name=f"Ontology_{main_entity.name}")
        dot.attr(rankdir="TB", label=f"{self.onto.name} - {main_entity.name}")
        
        # 添加节点和边
        nodes = set()
        for edge in graph_data:
            nodes.add(edge[0])
            nodes.add(edge[2])
            
        for node in nodes:
            dot.node(node, shape="box" if node == main_entity.name else "ellipse")
            
        for src, label, dest in graph_data:
            dot.edge(src, dest, label=label)
            
        # 保存并渲染
        output_path = self.owl_path.parent / "visualizations"
        output_path.mkdir(exist_ok=True)
        
        dot.render(
            directory=str(output_path),
            format=output_format,
            filename=f"{main_entity.name}_graph",
            cleanup=True
        )
        
        # 保存DOT源码
        dot_filename = f"{main_entity.name}_graph.dot"
        dot_file_path = output_path / dot_filename
        with open(dot_file_path, "w", encoding="utf-8") as f:
            f.write(dot.source)
        print(f"可视化已保存至: {output_path}/{main_entity.name}_graph.{output_format}")
        print(f"DOT文件已保存至: {dot_file_path}")

    def visualize_overview(self):
        """生成整体本体结构概览"""
        dot = graphviz.Digraph(name="Ontology_Overview")
        dot.attr(compound="true", rankdir="LR")
        
        # 添加所有类节点
        classes = list(self.onto.classes())
        for cls in classes:
            dot.node(cls.name, shape="box")
            
        # 添加继承关系
        for cls in classes:
            for parent in cls.is_a:
                if isinstance(parent, owl.ThingClass):
                    dot.edge(cls.name, parent.name, label="subClassOf")
                    
        # 添加对象属性关系
        for prop in self.onto.object_properties():
            if prop.domain and prop.range:
                for domain_cls in prop.domain:
                    for range_cls in prop.range:
                        dot.edge(
                            domain_cls.name, 
                            range_cls.name,
                            label=prop.name,
                            style="dashed"
                        )
        
        # 保存概览图
        output_path = self.owl_path.parent / "visualizations"
        output_path.mkdir(exist_ok=True)
        
        dot.render(
            directory=str(output_path),
            format="png",
            filename="ontology_overview",
            cleanup=True
        )
        
        # 保存DOT源码
        overview_dot_filename = "ontology_overview.dot"
        overview_dot_path = output_path / overview_dot_filename
        with open(overview_dot_path, "w", encoding="utf-8") as f:
            f.write(dot.source)
        print(f"概览图已保存至: {output_path}/ontology_overview.png")
        print(f"概览DOT文件已保存至: {overview_dot_path}")

# 使用示例
if __name__ == "__main__":
    # 配置参数
    OWL_FILE = "output.owl"  # 替换为你的OWL文件路径
    SEARCH_KEYWORD = "Person"               # 要可视化的实体关键词
    
    # 执行可视化
    visualizer = OntologyVisualizer(OWL_FILE)
    visualizer.load_ontology()
    
    # 生成整体概览
    visualizer.visualize_overview()
    
    # 生成指定实体详细视图
    #visualizer.visualize_entity(SEARCH_KEYWORD)
    
    # 可添加多个关键词查询
    #visualizer.visualize_entity("Organization")
    #visualizer.visualize_entity("Event")