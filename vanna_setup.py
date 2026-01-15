import os
import json
from dotenv import load_dotenv
import vanna as vn
from openai import OpenAI

# 加载环境变量
load_dotenv()

class MyVanna:
    def __init__(self, config=None):
        # 初始化 OpenAI 客户端（用于阿里云 Qwen-Plus）
        self.client = OpenAI(
            api_key=os.getenv('ALI_API_KEY'),
            base_url=os.getenv('ALI_BASE_URL')
        )
        self.model = os.getenv('VANNA_MODEL', 'qwen-plus')

        # 初始化训练数据
        self.training_data = []

    def train(self, **kwargs):
        """训练 Vanna，支持多种训练方式"""
        if 'ddl' in kwargs:
            # 存储 DDL 用于训练
            self.training_data.append({
                'type': 'ddl',
                'content': kwargs['ddl']
            })
        elif 'documentation' in kwargs:
            # 存储文档说明
            self.training_data.append({
                'type': 'documentation',
                'content': kwargs['documentation']
            })
        elif 'sql' in kwargs and 'question' in kwargs:
            # 存储 SQL-问题对
            self.training_data.append({
                'type': 'sql',
                'question': kwargs['question'],
                'sql': kwargs['sql']
            })

        return True

    def generate_sql(self, question: str, **kwargs) -> str:
        """生成 SQL 查询"""

        # 构建系统提示词
        system_prompt = """你是一个专业的 SQL 专家。请根据用户的问题生成准确的 MySQL SQL 查询语句。

        注意以下要点：
        1. 只返回 SQL 代码，不要包含解释
        2. 使用正确的 MySQL 语法
        3. 如果问题中涉及到表名，请使用完整的 database.table 格式
        4. 确保 SQL 语法正确
        5. 如果用户问题不明确，做出合理的假设并说明在注释中

        可用上下文信息："""

        # 添加训练数据到上下文
        context = ""
        for item in self.training_data[-10:]:  # 只使用最近10条训练数据
            if item['type'] == 'ddl':
                context += f"\n\nDDL结构:\n{item['content']}"
            elif item['type'] == 'documentation':
                context += f"\n\n表说明:\n{item['content']}"
            elif item['type'] == 'sql':
                context += f"\n\n示例查询:\n问题: {item['question']}\nSQL: {item['sql']}"

        system_prompt += context

        # 如果有额外的数据库上下文，添加进去
        if 'db_context' in kwargs:
            system_prompt += f"\n\n当前数据库上下文:\n{kwargs['db_context']}"

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": question
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # 稍高的温度以获得更好的创造性
                max_tokens=1000,
            )

            sql = response.choices[0].message.content.strip()

            # 清理 SQL 输出
            # 移除可能的多余代码块标记
            sql = sql.replace('```sql', '').replace('```', '').strip()

            return sql

        except Exception as e:
            print(f"生成 SQL 时出错: {e}")
            return f"-- 生成 SQL 时出错: {str(e)}\n-- 请检查您的查询问题"

    def run_sql(self, sql: str, **kwargs):
        """执行 SQL 查询（在实际应用中，这会连接到数据库）"""
        # 这个方法在实际应用中会连接到数据库执行查询
        # 这里返回一个模拟的结果
        return {"status": "success", "message": "SQL 执行成功（模拟）"}

    def get_training_data(self):
        """获取所有训练数据"""
        return self.training_data

    def clear_training_data(self):
        """清空训练数据"""
        self.training_data = []
        return True

def initialize_vanna():
    """初始化 Vanna 实例"""
    try:
        vn = MyVanna()

        # 测试 API 连接
        print("Vanna 初始化成功，使用模型:", vn.model)

        return vn

    except Exception as e:
        print(f"初始化 Vanna 失败: {e}")
        raise e