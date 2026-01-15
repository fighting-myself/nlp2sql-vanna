import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from vanna_setup import initialize_vanna
import mysql.connector
from mysql.connector import Error
import hashlib
from typing import Dict, List, Optional, Set, Tuple, Dict
import re

# 加载环境变量
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="智能多数据库查询助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin: 5px;
    }
    .database-card {
        background-color: #f0f7ff;
        border-left: 4px solid #4CAF50;
        padding: 12px;
        margin: 8px 0;
        border-radius: 8px;
    }
    .priority-database-card {
        background-color: #fff3e0;
        border-left: 4px solid #FF9800;
        padding: 12px;
        margin: 8px 0;
        border-radius: 8px;
        border: 2px solid #FF9800;
    }
    .table-card {
        background-color: #f9f9f9;
        border-left: 3px solid #2196F3;
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
    }
    .sql-container {
        background-color: #272822;
        color: #f8f8f2;
        padding: 15px;
        border-radius: 8px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        margin: 15px 0;
    }
    .result-container {
        border: 2px solid #e3f2fd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        background-color: #fafafa;
    }
    .progress-container {
        background-color: #e8f5e9;
        border-radius: 10px;
        padding: 15px;
        margin: 15px 0;
    }
    .priority-badge {
        background-color: #FF9800;
        color: white;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        margin-left: 8px;
    }
    .train-tab {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# 初始化Vanna
@st.cache_resource
def init_vanna():
    try:
        vn = initialize_vanna()
        # 初始化训练历史记录
        if 'train_history' not in st.session_state:
            st.session_state.train_history = []
        return vn
    except Exception as e:
        st.error(f"初始化Vanna失败: {str(e)}")
        return None

# 智能数据库管理器
class IntelligentDBAssistant:
    def __init__(self):
        self.connections = {}
        self.discovered_databases = {}
        self.schema_cache = {}

    def get_connection(self, host: str, database: str = None):
        """获取数据库连接"""
        key = f"{host}_{database}" if database else host

        if key in self.connections:
            try:
                self.connections[key].ping(reconnect=True)
                return self.connections[key]
            except:
                pass

        try:
            conn = mysql.connector.connect(
                host=host,
                database=database,
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                port=int(os.getenv('DB_PORT', 3306)),
                charset='utf8mb4',
                connect_timeout=10
            )
            self.connections[key] = conn
            return conn
        except Error as e:
            print(f"连接失败 {host}:{database}: {str(e)}")
            return None

    def discover_all_databases(self, host: str) -> Dict:
        """发现所有数据库和表"""
        conn = self.get_connection(host)
        if not conn:
            return {}

        try:
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            databases = [row[0] for row in cursor.fetchall()
                        if row[0] not in ['information_schema', 'mysql', 'performance_schema', 'sys']]

            all_info = {
                'host': host,
                'databases': {},
                'total_databases': 0,
                'total_tables': 0,
                'discovery_time': datetime.now().isoformat()
            }

            total_tables = 0

            for db in databases:
                try:
                    db_conn = self.get_connection(host, db)
                    if db_conn:
                        cursor_db = db_conn.cursor()
                        cursor_db.execute("SHOW TABLES")
                        tables = [row[0] for row in cursor_db.fetchall()]
                        cursor_db.close()

                        if tables:
                            # 获取每个表的字段信息
                            tables_info = {}
                            for table in tables:
                                try:
                                    cursor_desc = db_conn.cursor()
                                    cursor_desc.execute(f"DESCRIBE `{table}`")
                                    columns = cursor_desc.fetchall()
                                    cursor_desc.close()

                                    tables_info[table] = {
                                        'columns': [col[0] for col in columns],
                                        'column_types': [col[1] for col in columns],
                                        'column_count': len(columns)
                                    }
                                except:
                                    tables_info[table] = {'columns': [], 'column_types': [], 'column_count': 0}

                            all_info['databases'][db] = {
                                'tables': tables,
                                'table_count': len(tables),
                                'tables_info': tables_info
                            }
                            total_tables += len(tables)

                except Exception as e:
                    print(f"获取数据库 {db} 信息失败: {str(e)}")
                    continue

            cursor.close()

            all_info['total_databases'] = len(all_info['databases'])
            all_info['total_tables'] = total_tables

            return all_info

        except Error as e:
            print(f"发现数据库失败: {str(e)}")
            return {}

    def get_table_ddl(self, host: str, database: str, table_name: str) -> Optional[str]:
        """获取表DDL"""
        try:
            conn = self.get_connection(host, database)
            if not conn:
                return None

            cursor = conn.cursor()
            cursor.execute(f"SHOW CREATE TABLE `{database}`.`{table_name}`")
            result = cursor.fetchone()
            cursor.close()

            return result[1] if result else None
        except Exception as e:
            print(f"获取DDL失败 {database}.{table_name}: {str(e)}")
            return None

    def execute_query(self, host: str, database: str, query: str) -> tuple:
        """执行查询"""
        try:
            conn = self.get_connection(host, database)
            if not conn:
                return None, "连接失败"

            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            result = cursor.fetchall()
            cursor.close()

            return result, None
        except Error as e:
            return None, str(e)

    def get_table_sample_data(self, host: str, database: str, table_name: str, limit: int = 5) -> Optional[list]:
        """获取表的样例数据"""
        try:
            conn = self.get_connection(host, database)
            if not conn:
                return None

            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {limit}")
            result = cursor.fetchall()
            cursor.close()

            return result
        except Error as e:
            print(f"获取样例数据失败 {database}.{table_name}: {str(e)}")
            return None

# Vanna完整训练管理器
class VannaTrainingManager:
    def __init__(self, vn):
        self.vn = vn
        self.train_history = []

    def add_to_history(self, train_type: str, content: str, metadata: dict = None):
        """添加训练历史"""
        history_item = {
            'type': train_type,
            'content': content[:100] + "..." if len(content) > 100 else content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self.train_history.append(history_item)

        # 限制历史记录数量
        if len(self.train_history) > 50:
            self.train_history = self.train_history[-50:]

    def train_ddl(self, ddl: str, metadata: dict = None) -> bool:
        """训练DDL"""
        try:
            self.vn.train(ddl=ddl)
            self.add_to_history('DDL', ddl, metadata)
            return True
        except Exception as e:
            st.error(f"DDL训练失败: {str(e)}")
            return False

    def train_documentation(self, documentation: str, metadata: dict = None) -> bool:
        """训练文档"""
        try:
            self.vn.train(documentation=documentation)
            self.add_to_history('Documentation', documentation, metadata)
            return True
        except Exception as e:
            st.error(f"文档训练失败: {str(e)}")
            return False

    def train_question_sql(self, question: str, sql: str, metadata: dict = None) -> bool:
        """训练问题-SQL对"""
        try:
            self.vn.train(question=question, sql=sql)
            self.add_to_history('Question-SQL', f"Q: {question}\nSQL: {sql}", metadata)
            return True
        except Exception as e:
            st.error(f"问题-SQL训练失败: {str(e)}")
            return False

    def train_plan(self, plan: str, metadata: dict = None) -> bool:
        """训练执行计划（如果有此方法）"""
        try:
            if hasattr(self.vn, 'train_plan'):
                self.vn.train_plan(plan=plan)
                self.add_to_history('Plan', plan, metadata)
                return True
            else:
                st.warning("当前Vanna版本不支持Plan训练")
                return False
        except Exception as e:
            st.error(f"Plan训练失败: {str(e)}")
            return False

    def get_train_history(self) -> List[dict]:
        """获取训练历史"""
        return self.train_history

    def clear_history(self):
        """清空训练历史"""
        self.train_history = []

    def get_training_stats(self) -> dict:
        """获取训练统计"""
        stats = {
            'total': len(self.train_history),
            'by_type': {}
        }

        for item in self.train_history:
            train_type = item['type']
            if train_type not in stats['by_type']:
                stats['by_type'][train_type] = 0
            stats['by_type'][train_type] += 1

        return stats

# 智能查询生成器 - 修复版
class EnhancedSmartQueryGenerator:
    def __init__(self, vanna_instance):
        self.vn = vanna_instance
        self.trained_items = set()
        self.is_trained = False
        self.priority_databases = set()
        self.training_manager = None

        # 初始化训练管理器
        if vanna_instance:
            self.training_manager = VannaTrainingManager(vanna_instance)

    def set_priority_databases(self, databases: Set[str]):
        """设置优先数据库"""
        self.priority_databases = databases

    def train_all_databases(self, db_manager, host: str, db_info: Dict) -> Dict:
        """一键训练所有数据库"""
        results = {
            'success': False,
            'databases_trained': 0,
            'tables_trained': 0,
            'errors': [],
            'training_time': None
        }

        if not db_info or 'databases' not in db_info:
            results['errors'].append("无数据库信息")
            return results

        start_time = time.time()
        databases = db_info['databases']

        # 进度显示
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        progress_bar = st.progress(0)

        total_dbs = len(databases)
        trained_dbs = 0
        trained_tables = 0

        # 如果有优先数据库，先训练优先数据库
        training_order = []
        priority_dbs = []
        other_dbs = []

        for db_name in databases.keys():
            if db_name in self.priority_databases:
                priority_dbs.append(db_name)
            else:
                other_dbs.append(db_name)

        training_order = priority_dbs + other_dbs

        for i, db_name in enumerate(training_order):
            db_data = databases[db_name]
            db_progress = (i + 1) / total_dbs
            progress_bar.progress(db_progress)

            # 显示是否是优先数据库
            priority_mark = "🎯 " if db_name in self.priority_databases else ""
            status_placeholder.text(f"{priority_mark}正在训练数据库: {db_name} ({i+1}/{total_dbs})")

            tables = db_data.get('tables', [])
            tables_info = db_data.get('tables_info', {})

            for table in tables:
                try:
                    # 训练DDL
                    ddl = db_manager.get_table_ddl(host, db_name, table)
                    if ddl and self.training_manager:
                        metadata = {
                            'database': db_name,
                            'table': table,
                            'priority': db_name in self.priority_databases
                        }
                        self.training_manager.train_ddl(ddl, metadata)

                    # 训练多种查询模式
                    if self.training_manager:
                        metadata = {
                            'database': db_name,
                            'table': table,
                            'priority': db_name in self.priority_databases
                        }

                        # 1. 训练简单的表名查询
                        table_query = f"查询表 {table}"
                        sql = f"SELECT * FROM `{db_name}`.`{table}` LIMIT 10"
                        self.training_manager.train_question_sql(table_query, sql, metadata)

                        # 2. 训练表详情查询
                        table_detail_query = f"查看表 {table} 的详情"
                        detail_sql = f"DESCRIBE `{db_name}`.`{table}`"
                        self.training_manager.train_question_sql(table_detail_query, detail_sql, metadata)

                        # 3. 训练中文查询
                        chinese_query = f"帮我查 {table} 表"
                        self.training_manager.train_question_sql(chinese_query, sql, metadata)

                        # 4. 训练表结构描述
                        if table in tables_info:
                            columns = tables_info[table].get('columns', [])
                            column_types = tables_info[table].get('column_types', [])

                            if columns:
                                columns_desc = []
                                for col, col_type in zip(columns, column_types):
                                    columns_desc.append(f"{col} ({col_type})")

                                priority_note = "（优先数据库）" if db_name in self.priority_databases else ""
                                table_desc = f"数据库 {db_name} {priority_note}中的表 {table} 包含以下字段: {', '.join(columns_desc)}"
                                self.training_manager.train_documentation(table_desc, metadata)

                    self.trained_items.add(f"{db_name}.{table}")
                    trained_tables += 1

                except Exception as e:
                    results['errors'].append(f"表 {db_name}.{table} 训练失败: {str(e)}")

            # 训练数据库上下文
            try:
                if tables and self.training_manager:
                    metadata = {
                        'database': db_name,
                        'priority': db_name in self.priority_databases
                    }
                    priority_tag = "（优先数据库）" if db_name in self.priority_databases else ""
                    db_context = f"数据库 {db_name} {priority_tag}包含以下表: {', '.join(tables[:10])}"
                    if len(tables) > 10:
                        db_context += f" 等共 {len(tables)} 个表"
                    self.training_manager.train_documentation(db_context, metadata)

                trained_dbs += 1

            except Exception as e:
                results['errors'].append(f"数据库 {db_name} 上下文训练失败: {str(e)}")

        progress_bar.empty()
        status_placeholder.empty()

        results['success'] = True
        results['databases_trained'] = trained_dbs
        results['tables_trained'] = trained_tables
        results['training_time'] = time.time() - start_time
        self.is_trained = True

        return results

    def generate_smart_query(self, user_query: str, db_info: Dict) -> Dict:
        """智能生成查询"""
        try:
            # 首先尝试精确匹配表名
            exact_match_result = self._try_exact_table_match(user_query, db_info)
            if exact_match_result:
                return exact_match_result

            # 如果没有精确匹配，使用Vanna智能查询
            sql = self.vn.generate_sql(question=user_query)

            if not sql:
                return {'success': False, 'error': '无法生成SQL'}

            # 分析SQL中使用了哪些数据库
            used_databases = self._analyze_sql_databases(sql, db_info)

            return {
                'success': True,
                'sql': sql,
                'enhanced_query': user_query,
                'relevant_info': {'databases': {}, 'total_matches': 0},
                'keywords': [],
                'used_databases': used_databases,
                'priority_used': any(db in self.priority_databases for db in used_databases),
                'match_type': 'vanna_generated'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _try_exact_table_match(self, user_query: str, db_info: Dict) -> Optional[Dict]:
        """尝试精确匹配表名"""
        if not db_info or 'databases' not in db_info:
            return None

        # 从查询中提取可能的表名
        potential_table_names = self._extract_table_names_from_query(user_query)

        if not potential_table_names:
            return None

        # 首先在优先数据库中查找
        for table_name in potential_table_names:
            for db_name in self.priority_databases:
                if db_name in db_info['databases']:
                    db_data = db_info['databases'][db_name]
                    tables = db_data.get('tables', [])

                    # 精确匹配
                    if table_name in tables:
                        return self._create_exact_match_result(db_name, table_name, user_query)

                    # 忽略大小写匹配
                    for actual_table in tables:
                        if actual_table.lower() == table_name.lower():
                            return self._create_exact_match_result(db_name, actual_table, user_query)

        # 然后在所有数据库中查找
        for table_name in potential_table_names:
            for db_name, db_data in db_info['databases'].items():
                tables = db_data.get('tables', [])

                # 精确匹配
                if table_name in tables:
                    return self._create_exact_match_result(db_name, table_name, user_query)

                # 忽略大小写匹配
                for actual_table in tables:
                    if actual_table.lower() == table_name.lower():
                        return self._create_exact_match_result(db_name, actual_table, user_query)

        return None

    def _extract_table_names_from_query(self, query: str) -> List[str]:
        """从查询中提取可能的表名"""
        query_lower = query.lower()

        # 常见表名模式匹配
        table_patterns = [
            r'查\s+(\w+)\s*表',    # "查 xxx 表"
            r'查询\s+(\w+)\s*表',   # "查询 xxx 表"
            r'表\s+(\w+)',         # "表 xxx"
            r'\b(\w+)\b表',        # "xxx表"
            r'帮我查\s+(\w+)',     # "帮我查 xxx"
        ]

        potential_table_names = []

        for pattern in table_patterns:
            matches = re.findall(pattern, query_lower)
            potential_table_names.extend(matches)

        # 提取单词
        words = re.findall(r'\b(\w+)\b', query_lower)
        for word in words:
            if len(word) >= 3 and word not in ['查询', '帮我', '详情', '查看']:
                potential_table_names.append(word)

        # 去重
        potential_table_names = list(set(potential_table_names))

        return potential_table_names

    def _create_exact_match_result(self, db_name: str, table_name: str, user_query: str) -> Dict:
        """创建精确匹配的结果"""
        # 根据查询意图生成SQL
        sql = self._generate_query_by_intent(db_name, table_name, user_query)

        return {
            'success': True,
            'sql': sql,
            'enhanced_query': f"查询表 {db_name}.{table_name}",
            'relevant_info': {
                'databases': {
                    db_name: {
                        'tables': {
                            table_name: {'matches': ['精确匹配']}
                        },
                        'priority': db_name in self.priority_databases
                    }
                },
                'total_matches': 1
            },
            'keywords': [table_name],
            'used_databases': [db_name],
            'priority_used': db_name in self.priority_databases,
            'match_type': 'exact_table'
        }

    def _generate_query_by_intent(self, db_name: str, table_name: str, user_query: str) -> str:
        """根据查询意图生成SQL"""
        query_lower = user_query.lower()

        if any(word in query_lower for word in ['详情', '结构', '字段', '列', 'desc', 'describe']):
            return f"DESCRIBE `{db_name}`.`{table_name}`;"
        elif any(word in query_lower for word in ['数量', '计数', 'count', '多少']):
            return f"SELECT COUNT(*) FROM `{db_name}`.`{table_name}`;"
        else:
            return f"SELECT * FROM `{db_name}`.`{table_name}` LIMIT 10;"

    def _analyze_sql_databases(self, sql: str, db_info: Dict) -> List[str]:
        """分析SQL中使用的数据库"""
        used_dbs = []

        pattern = r'`?(\w+)`?\.`?(\w+)`?'
        matches = re.findall(pattern, sql)

        for db_match, _ in matches:
            if db_match in db_info.get('databases', {}):
                used_dbs.append(db_match)

        return used_dbs

def generate_diverse_qsql_pairs(tables_info, pair_count, diversity_level, training_manager):
    """生成多样化的问题-SQL对"""
    try:
        from openai import OpenAI
        import os

        # 准备表信息文本
        tables_text = ""
        for table_info in tables_info:
            db_name = table_info['database']
            table_name = table_info['table']
            columns = table_info.get('columns', [])
            columns_info = table_info.get('columns_info', [])

            tables_text += f"数据库: {db_name}\n"
            tables_text += f"表: {table_name}\n"
            tables_text += f"字段 ({len(columns)}个): {', '.join(columns_info)}\n\n"

        # 构建Prompt
        prompt = f"""你是一个SQL专家，需要为以下数据库表生成自然语言问题和对应的SQL查询对。

        表信息：
        {tables_text}

        请生成{pair_count}个多样化的问题-SQL对，涵盖以下类型：
        1. 简单查询（SELECT *）
        2. 表结构查询（DESCRIBE/SHOW COLUMNS）
        3. 统计查询（COUNT, SUM, AVG等）
        4. 条件查询（WHERE子句）
        5. 排序查询（ORDER BY）
        6. 分组查询（GROUP BY）
        7. 多表查询（JOIN，如果涉及多个表）
        8. 字段详情查询

        多样性要求：{diversity_level}级别

        格式要求：每个对占一行，问题和SQL之间用"###"分隔

        示例：
        查询用户表的所有数据###SELECT * FROM users LIMIT 10
        查看订单表的字段信息###DESCRIBE orders
        统计用户数量###SELECT COUNT(*) FROM users

        现在开始生成："""

        # 使用.env配置文件中的阿里云API配置
        api_key = os.getenv('ALI_API_KEY')
        base_url = os.getenv('ALI_BASE_URL')
        model = os.getenv('VANNA_MODEL', 'qwen3-max')

        if not api_key:
            st.error("❌ 未配置阿里云API密钥，请在.env文件中设置ALI_API_KEY")
            return []

        # 调用阿里云API
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的SQL查询生成助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7 if diversity_level == "高" else 0.5,
            max_tokens=2000
        )

        # 解析响应
        content = response.choices[0].message.content
        lines = content.strip().split('\n')

        pairs = []
        for line in lines:
            line = line.strip()
            if '###' in line:
                question, sql = line.split('###', 1)
                question = question.strip()
                sql = sql.strip()

                # 验证SQL语法
                if sql.upper().startswith(('SELECT', 'DESCRIBE', 'SHOW', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX')):
                    pairs.append((question, sql))

        # 如果AI生成的不够，补充一些基础查询
        if len(pairs) < pair_count:
            for table_info in tables_info:
                db_name = table_info['database']
                table_name = table_info['table']
                columns = table_info.get('columns', [])

                # 基础查询
                base_queries = [
                    (f"查询{table_name}表的所有数据", f"SELECT * FROM `{db_name}`.`{table_name}` LIMIT 10"),
                    (f"查看{table_name}表的字段信息", f"DESCRIBE `{db_name}`.`{table_name}`"),
                    (f"统计{table_name}表有多少条记录", f"SELECT COUNT(*) FROM `{db_name}`.`{table_name}`"),
                ]

                # 如果有字段，生成一些字段相关的查询
                if columns:
                    for column in columns[:3]:  # 取前3个字段
                        base_queries.append(
                            (f"查询{table_name}表的{column}字段", f"SELECT {column} FROM `{db_name}`.`{table_name}` LIMIT 10")
                        )

                pairs.extend(base_queries)

        # 去重并限制数量
        unique_pairs = []
        seen = set()
        for question, sql in pairs:
            if (question, sql) not in seen and len(unique_pairs) < pair_count:
                seen.add((question, sql))
                unique_pairs.append((question, sql))

        return unique_pairs

    except ImportError:
        st.error("❌ 未安装openai库，请运行: pip install openai")
        return []
    except Exception as e:
        print(f"生成问题-SQL对失败: {str(e)}")

        # 备选方案：生成基础查询
        backup_pairs = []
        for table_info in tables_info[:3]:  # 最多3个表
            db_name = table_info['database']
            table_name = table_info['table']
            columns = table_info.get('columns', [])

            # 基础查询
            backup_pairs.extend([
                (f"查询{table_name}表的所有数据", f"SELECT * FROM `{db_name}`.`{table_name}` LIMIT 10"),
                (f"查看{table_name}表的字段信息", f"DESCRIBE `{db_name}`.`{table_name}`"),
                (f"统计{table_name}表有多少条记录", f"SELECT COUNT(*) FROM `{db_name}`.`{table_name}`"),
                (f"从{table_name}表查询前10条数据", f"SELECT * FROM `{db_name}`.`{table_name}` LIMIT 10"),
            ])

            # 字段查询
            if columns:
                for column in columns[:2]:
                    backup_pairs.append(
                        (f"查询{table_name}表的{column}字段", f"SELECT {column} FROM `{db_name}`.`{table_name}` LIMIT 10")
                    )

        # 限制数量
        return backup_pairs[:pair_count]

# 手动训练界面
def show_manual_training_interface(training_manager, db_manager, host, db_info):
    """显示手动训练界面"""
    st.markdown("### 🎓 手动训练")
    st.info("通过手动训练可以增强模型的查询能力，特别是对于复杂的查询场景")

    # 训练类型选择
    train_type = st.selectbox(
        "选择训练类型",
        ["DDL训练", "文档训练", "问题-SQL对训练", "批量训练", "训练历史"],
        key="train_type_select"
    )

    if train_type == "DDL训练":
        st.markdown("#### 📋 DDL训练")
        st.caption("训练表的创建语句，帮助模型理解表结构")

        col1, col2 = st.columns([2, 1])

        with col1:
            # 选择数据库和表
            if db_info and 'databases' in db_info:
                databases = list(db_info['databases'].keys())
                selected_db = st.selectbox("选择数据库", databases)

                if selected_db:
                    tables = db_info['databases'][selected_db]['tables']
                    selected_table = st.selectbox("选择表", tables)

                    if st.button("获取DDL", key="get_ddl_btn"):
                        with st.spinner("正在获取DDL..."):
                            ddl = db_manager.get_table_ddl(host, selected_db, selected_table)
                            if ddl:
                                st.code(ddl, language="sql")
                                st.session_state.ddl_content = ddl
                                st.session_state.ddl_metadata = {
                                    'database': selected_db,
                                    'table': selected_table
                                }
                            else:
                                st.error("获取DDL失败")

        with col2:
            # DDL输入
            ddl_input = st.text_area(
                "或直接输入DDL",
                value=st.session_state.get('ddl_content', ''),
                height=200,
                placeholder="CREATE TABLE ..."
            )

            metadata = st.session_state.get('ddl_metadata', {})

            if st.button("训练DDL", type="primary", key="train_ddl_btn"):
                if ddl_input:
                    with st.spinner("正在训练..."):
                        success = training_manager.train_ddl(ddl_input, metadata)
                        if success:
                            st.success("✅ DDL训练成功")
                else:
                    st.warning("请输入DDL内容")

    elif train_type == "文档训练":
        st.markdown("#### 📝 文档训练")
        st.caption("训练关于表、字段或业务逻辑的描述文档")

        col1, col2 = st.columns([1, 2])

        with col1:
            doc_type = st.selectbox(
                "文档类型",
                ["表描述", "字段描述", "业务逻辑", "自定义"],
                key="doc_type_select"
            )

            # 如果是表描述，可以选择表
            if doc_type == "表描述" and db_info and 'databases' in db_info:
                databases = list(db_info['databases'].keys())
                selected_db = st.selectbox("选择数据库", databases, key="doc_db_select")

                if selected_db:
                    tables = db_info['databases'][selected_db]['tables']
                    selected_table = st.selectbox("选择表", tables, key="doc_table_select")
                    st.session_state.doc_metadata = {
                        'database': selected_db,
                        'table': selected_table,
                        'type': doc_type
                    }

        with col2:
            documentation = st.text_area(
                "文档内容",
                height=150,
                placeholder="例如：用户表存储系统用户的基本信息，包含用户名、邮箱、创建时间等字段..."
            )

            if st.button("训练文档", type="primary", key="train_doc_btn"):
                if documentation:
                    metadata = st.session_state.get('doc_metadata', {'type': doc_type})
                    with st.spinner("正在训练..."):
                        success = training_manager.train_documentation(documentation, metadata)
                        if success:
                            st.success("✅ 文档训练成功")
                else:
                    st.warning("请输入文档内容")

    elif train_type == "问题-SQL对训练":
        st.markdown("#### 💬 问题-SQL对训练")
        st.caption("训练自然语言问题到SQL的映射，这是最重要的训练方式")

        # 初始化session state
        if 'generated_question' not in st.session_state:
            st.session_state.generated_question = ""
        if 'generated_sql' not in st.session_state:
            st.session_state.generated_sql = ""
        if 'generated_pairs' not in st.session_state:
            st.session_state.generated_pairs = []
        if 'selected_pairs' not in st.session_state:
            st.session_state.selected_pairs = []

        # 创建两个主要区域
        tab1, tab2 = st.tabs(["🔧 手动训练", "🤖 智能批量生成"])

        with tab1:
            # 原有的手动训练界面
            col1, col2 = st.columns(2)

            with col1:
                # 问题输入框
                question_container = st.empty()

                if st.session_state.generated_question:
                    question = question_container.text_area(
                        "自然语言问题",
                        value=st.session_state.generated_question,
                        height=100,
                        placeholder="例如：查询所有用户的信息",
                        key="question_input_with_value"
                    )
                else:
                    question = question_container.text_area(
                        "自然语言问题",
                        height=100,
                        placeholder="例如：查询所有用户的信息",
                        key="question_input"
                    )

                # 简单的问题生成助手
                if db_info and 'databases' in db_info:
                    with st.expander("💡 简单示例生成"):
                        databases = list(db_info['databases'].keys())
                        selected_db = st.selectbox("数据库", databases, key="simple_db_select")

                        if selected_db:
                            tables = db_info['databases'][selected_db]['tables']
                            selected_table = st.selectbox("表", tables, key="simple_table_select")

                            if st.button("生成简单示例", key="simple_gen_btn"):
                                # 生成几个简单的示例
                                examples = [
                                    (f"查询{selected_table}表的所有数据",
                                     f"SELECT * FROM `{selected_db}`.`{selected_table}` LIMIT 10"),
                                    (f"查看{selected_table}表的字段信息",
                                     f"DESCRIBE `{selected_db}`.`{selected_table}`"),
                                    (f"统计{selected_table}表有多少条记录",
                                     f"SELECT COUNT(*) FROM `{selected_db}`.`{selected_table}`"),
                                ]
                                st.session_state.generated_pairs = examples
                                st.rerun()

            with col2:
                # SQL输入框
                sql_container = st.empty()

                if st.session_state.generated_sql:
                    sql_query = sql_container.text_area(
                        "对应的SQL",
                        value=st.session_state.generated_sql,
                        height=100,
                        placeholder="例如：SELECT * FROM users",
                        key="sql_input_with_value"
                    )
                else:
                    sql_query = sql_container.text_area(
                        "对应的SQL",
                        height=100,
                        placeholder="例如：SELECT * FROM users",
                        key="sql_input"
                    )

                metadata = st.session_state.get('train_metadata', {})

                # 确定使用哪个问题和SQL
                if st.session_state.generated_question:
                    current_question = st.session_state.generated_question
                else:
                    current_question = question if 'question' in locals() else ""

                if st.session_state.generated_sql:
                    current_sql = st.session_state.generated_sql
                else:
                    current_sql = sql_query if 'sql_query' in locals() else ""

                # 单对训练按钮
                if st.button("训练此问题-SQL对", type="primary", key="train_single_btn"):
                    if current_question and current_sql:
                        with st.spinner("正在训练..."):
                            success = training_manager.train_question_sql(current_question, current_sql, metadata)
                            if success:
                                st.success("✅ 问题-SQL对训练成功")
                                # 清空生成的内容
                                st.session_state.generated_question = ""
                                st.session_state.generated_sql = ""
                                st.rerun()
                    else:
                        st.warning("请同时输入问题和SQL")

        with tab2:
            st.markdown("#### 🤖 智能批量生成")
            st.info("选择数据库和表，让AI生成多样化的问题-SQL对进行批量训练")

            # 数据库和表选择
            if db_info and 'databases' in db_info:
                col_select1, col_select2, col_select3 = st.columns([2, 2, 1])

                with col_select1:
                    # 多选数据库
                    all_databases = list(db_info['databases'].keys())
                    selected_dbs = st.multiselect(
                        "选择数据库（可多选）",
                        all_databases,
                        default=all_databases[:2] if len(all_databases) >= 2 else all_databases,
                        help="选择要生成训练数据的数据库"
                    )

                with col_select2:
                    # 显示选中的数据库中的表
                    available_tables = []
                    if selected_dbs:
                        for db in selected_dbs:
                            tables = db_info['databases'][db]['tables']
                            for table in tables:
                                available_tables.append(f"{db}.{table}")

                    selected_tables_full = st.multiselect(
                        "选择表（可多选）",
                        available_tables,
                        help="选择要生成训练数据的表"
                    )

                    # 解析数据库和表名
                    selected_tables = []
                    table_info_map = {}
                    for table_full in selected_tables_full:
                        if '.' in table_full:
                            db_name, table_name = table_full.split('.', 1)
                            selected_tables.append((db_name, table_name))
                            # 获取表信息
                            if db_name in db_info['databases'] and table_name in db_info['databases'][db_name]['tables_info']:
                                table_info = db_info['databases'][db_name]['tables_info'][table_name]
                                columns = table_info.get('columns', [])
                                table_info_map[f"{db_name}.{table_name}"] = {
                                    'database': db_name,
                                    'table': table_name,
                                    'columns': columns,
                                    'column_count': len(columns)
                                }

                with col_select3:
                    # 生成数量
                    pair_count = st.number_input("生成数量", min_value=5, max_value=50, value=15, step=5)

                    # 多样性级别
                    diversity = st.select_slider(
                        "多样性级别",
                        options=["低", "中", "高"],
                        value="中",
                        help="高多样性会生成更多类型的查询"
                    )

                # 生成按钮
                if st.button("🎯 开始智能生成", type="primary", use_container_width=True):
                    if not selected_tables:
                        st.warning("请至少选择一个表")
                    else:
                        with st.spinner("🤖 AI正在生成多样化的问题-SQL对..."):
                            # 准备表信息
                            tables_info = []
                            for db_name, table_name in selected_tables:
                                if db_name in db_info['databases']:
                                    db_data = db_info['databases'][db_name]
                                    if table_name in db_data['tables_info']:
                                        table_info = db_data['tables_info'][table_name]
                                        columns = table_info.get('columns', [])
                                        columns_info = []
                                        for i, col in enumerate(columns):
                                            col_type = table_info.get('column_types', [])[i] if i < len(table_info.get('column_types', [])) else "未知类型"
                                            columns_info.append(f"{col} ({col_type})")

                                        tables_info.append({
                                            'database': db_name,
                                            'table': table_name,
                                            'columns': columns,
                                            'columns_info': columns_info,
                                            'column_count': len(columns)
                                        })

                            # 生成多样化的问题-SQL对
                            generated_pairs = generate_diverse_qsql_pairs(
                                tables_info,
                                pair_count,
                                diversity,
                                training_manager
                            )

                            if generated_pairs:
                                st.session_state.generated_pairs = generated_pairs
                                st.session_state.selected_pairs = [True] * len(generated_pairs)  # 默认全选
                                st.success(f"✅ 成功生成 {len(generated_pairs)} 个问题-SQL对")
                                st.rerun()
                            else:
                                st.error("生成失败，请重试")

                # 显示生成的训练对
                if st.session_state.generated_pairs:
                    st.markdown("---")
                    st.markdown(f"#### 📋 生成结果 ({len(st.session_state.generated_pairs)} 对)")

                    # 批量操作
                    col_batch1, col_batch2, col_batch3 = st.columns(3)
                    with col_batch1:
                        if st.button("✅ 全选", use_container_width=True):
                            st.session_state.selected_pairs = [True] * len(st.session_state.generated_pairs)
                            st.rerun()

                    with col_batch2:
                        if st.button("❌ 全不选", use_container_width=True):
                            st.session_state.selected_pairs = [False] * len(st.session_state.generated_pairs)
                            st.rerun()

                    with col_batch3:
                        if st.button("🔄 重新生成", use_container_width=True):
                            st.session_state.generated_pairs = []
                            st.session_state.selected_pairs = []
                            st.rerun()

                    # 显示所有生成的对
                    for idx, (question, sql) in enumerate(st.session_state.generated_pairs):
                        with st.expander(f"第 {idx+1} 对: {question[:50]}...", expanded=False):
                            col_display1, col_display2, col_display3 = st.columns([4, 1, 1])

                            with col_display1:
                                st.markdown(f"**问题**: {question}")
                                st.code(sql, language="sql")

                            with col_display2:
                                # 编辑按钮
                                if st.button("✏️ 编辑", key=f"edit_{idx}"):
                                    st.session_state.editing_idx = idx
                                    st.session_state.editing_question = question
                                    st.session_state.editing_sql = sql
                                    st.rerun()

                            with col_display3:
                                # 选择框
                                selected = st.checkbox(
                                    "选择训练",
                                    value=st.session_state.selected_pairs[idx] if idx < len(st.session_state.selected_pairs) else True,
                                    key=f"select_{idx}"
                                )
                                if idx < len(st.session_state.selected_pairs):
                                    st.session_state.selected_pairs[idx] = selected

                    # 批量训练按钮
                    if st.button("🚀 批量训练选中的对", type="primary", use_container_width=True):
                        selected_count = sum(st.session_state.selected_pairs)
                        if selected_count == 0:
                            st.warning("请至少选择一对进行训练")
                        else:
                            success_count = 0
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            for i, selected in enumerate(st.session_state.selected_pairs):
                                if selected and i < len(st.session_state.generated_pairs):
                                    question, sql = st.session_state.generated_pairs[i]
                                    status_text.text(f"正在训练第 {i+1}/{selected_count} 对...")
                                    progress_bar.progress((i + 1) / selected_count)

                                    metadata = {
                                        'database': 'auto_generated',
                                        'table': 'multiple',
                                        'batch_idx': i
                                    }
                                    if training_manager.train_question_sql(question, sql, metadata):
                                        success_count += 1

                            progress_bar.empty()
                            status_text.empty()

                            if success_count > 0:
                                st.success(f"✅ 批量训练完成！成功训练 {success_count}/{selected_count} 对")
                                # 保留未选中的对
                                new_pairs = []
                                new_selected = []
                                for i, selected in enumerate(st.session_state.selected_pairs):
                                    if not selected and i < len(st.session_state.generated_pairs):
                                        new_pairs.append(st.session_state.generated_pairs[i])
                                        new_selected.append(False)

                                st.session_state.generated_pairs = new_pairs
                                st.session_state.selected_pairs = new_selected
                                st.rerun()
                            else:
                                st.error("批量训练失败")

                # 编辑界面
                if 'editing_idx' in st.session_state:
                    st.markdown("---")
                    st.markdown("#### ✏️ 编辑问题-SQL对")

                    editing_idx = st.session_state.editing_idx
                    original_question = st.session_state.editing_question
                    original_sql = st.session_state.editing_sql

                    new_question = st.text_area("修改问题", value=original_question, key="edit_question")
                    new_sql = st.text_area("修改SQL", value=original_sql, key="edit_sql")

                    col_edit1, col_edit2, col_edit3 = st.columns(3)

                    with col_edit1:
                        if st.button("💾 保存修改", type="primary"):
                            if editing_idx < len(st.session_state.generated_pairs):
                                st.session_state.generated_pairs[editing_idx] = (new_question, new_sql)
                                del st.session_state.editing_idx
                                del st.session_state.editing_question
                                del st.session_state.editing_sql
                                st.success("修改已保存")
                                st.rerun()

                    with col_edit2:
                        if st.button("❌ 删除此对"):
                            if editing_idx < len(st.session_state.generated_pairs):
                                st.session_state.generated_pairs.pop(editing_idx)
                                if editing_idx < len(st.session_state.selected_pairs):
                                    st.session_state.selected_pairs.pop(editing_idx)
                                del st.session_state.editing_idx
                                del st.session_state.editing_question
                                del st.session_state.editing_sql
                                st.success("已删除")
                                st.rerun()

                    with col_edit3:
                        if st.button("↩️ 取消编辑"):
                            del st.session_state.editing_idx
                            del st.session_state.editing_question
                            del st.session_state.editing_sql
                            st.rerun()

            else:
                st.warning("请先发现数据库")

    elif train_type == "批量训练":
        st.markdown("#### 📚 批量训练")
        st.caption("批量导入训练数据（JSON格式）")

        train_format = st.selectbox(
            "训练数据格式",
            ["问题-SQL对", "DDL列表", "文档列表"],
            key="batch_format"
        )

        if train_format == "问题-SQL对":
            example_data = [
                {
                    "question": "查询所有用户信息",
                    "sql": "SELECT * FROM users"
                },
                {
                    "question": "统计订单数量",
                    "sql": "SELECT COUNT(*) FROM orders"
                }
            ]
        elif train_format == "DDL列表":
            example_data = [
                {
                    "ddl": "CREATE TABLE users (id INT, name VARCHAR(100))"
                }
            ]
        else:
            example_data = [
                {
                    "documentation": "用户表存储用户基本信息"
                }
            ]

        st.code(json.dumps(example_data, indent=2, ensure_ascii=False), language="json")

        batch_data = st.text_area(
            "批量训练数据（JSON格式）",
            height=200,
            placeholder="粘贴JSON数据..."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("验证JSON格式", key="validate_json"):
                try:
                    data = json.loads(batch_data)
                    st.success(f"✅ JSON格式正确，共{len(data)}条记录")
                except Exception as e:
                    st.error(f"❌ JSON格式错误: {str(e)}")

        with col2:
            if st.button("执行批量训练", type="primary", key="batch_train"):
                if batch_data:
                    try:
                        data = json.loads(batch_data)
                        success_count = 0
                        total_count = len(data)

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        for i, item in enumerate(data):
                            status_text.text(f"正在训练第 {i+1}/{total_count} 条...")
                            progress_bar.progress((i + 1) / total_count)

                            if train_format == "问题-SQL对":
                                if 'question' in item and 'sql' in item:
                                    if training_manager.train_question_sql(item['question'], item['sql']):
                                        success_count += 1
                            elif train_format == "DDL列表":
                                if 'ddl' in item:
                                    if training_manager.train_ddl(item['ddl']):
                                        success_count += 1
                            elif train_format == "文档列表":
                                if 'documentation' in item:
                                    if training_manager.train_documentation(item['documentation']):
                                        success_count += 1

                        progress_bar.empty()
                        status_text.empty()

                        st.success(f"✅ 批量训练完成！成功: {success_count}/{total_count}")

                    except Exception as e:
                        st.error(f"批量训练失败: {str(e)}")
                else:
                    st.warning("请输入批量训练数据")

    elif train_type == "训练历史":
        st.markdown("#### 📜 训练历史")

        if training_manager:
            stats = training_manager.get_training_stats()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总训练次数", stats['total'])
            with col2:
                st.metric("训练类型数", len(stats['by_type']))
            with col3:
                if st.button("清空历史", type="secondary"):
                    training_manager.clear_history()
                    st.rerun()

            # 显示训练历史
            history = training_manager.get_train_history()
            if history:
                st.markdown("##### 最近训练记录")
                for i, record in enumerate(reversed(history[-20:]), 1):
                    with st.expander(f"{i}. [{record['type']}] {record['timestamp'][:19]}"):
                        st.write(f"**内容**: {record['content']}")
                        if record['metadata']:
                            st.write(f"**元数据**: {record['metadata']}")
            else:
                st.info("暂无训练历史")

    # 快速训练区域
    st.markdown("---")
    st.markdown("#### ⚡ 快速训练")

    quick_train_col1, quick_train_col2, quick_train_col3 = st.columns(3)

    with quick_train_col1:
        if st.button("训练常用查询模式", key="quick_patterns"):
            quick_patterns = [
                ("查询表结构", "DESCRIBE {table}"),
                ("查看表数据", "SELECT * FROM {table} LIMIT 10"),
                ("统计记录数", "SELECT COUNT(*) FROM {table}"),
                ("查询前N条", "SELECT * FROM {table} LIMIT {n}")
            ]

            for question, sql in quick_patterns:
                training_manager.train_question_sql(question, sql, {'type': 'quick_pattern'})

            st.success("✅ 常用查询模式训练完成")

    with quick_train_col2:
        if st.button("训练数据库术语", key="quick_terms"):
            terms = [
                "表是数据库中存储数据的基本单位",
                "字段是表中的列，用于存储特定类型的数据",
                "主键是唯一标识表中每条记录的字段",
                "外键是关联两个表的字段"
            ]

            for term in terms:
                training_manager.train_documentation(term, {'type': 'terminology'})

            st.success("✅ 数据库术语训练完成")

    with quick_train_col3:
        if db_info and 'databases' in db_info and st.button("训练表名查询", key="quick_table_names"):
            databases = db_info['databases']
            trained = 0

            for db_name, db_data in databases.items():
                tables = db_data.get('tables', [])[:5]  # 每个数据库训练前5个表
                for table in tables:
                    question = f"查询{table}表"
                    sql = f"SELECT * FROM `{db_name}`.`{table}` LIMIT 10"
                    if training_manager.train_question_sql(question, sql, {'database': db_name, 'table': table}):
                        trained += 1

            st.success(f"✅ 表名查询训练完成，共训练{trained}个表")

# 数据库选择组件
def database_selector(db_info: Dict, current_priority_dbs: Set[str] = None):
    """数据库选择器组件"""
    if current_priority_dbs is None:
        current_priority_dbs = set()

    if not db_info or 'databases' not in db_info:
        st.warning("请先发现数据库")
        return current_priority_dbs

    st.markdown("### 🎯 选择优先数据库")
    st.info("选择您最常查询的数据库，系统会优先在这些数据库中查找相关表")

    databases = list(db_info['databases'].keys())

    # 使用多选框让用户选择优先数据库
    selected_dbs = st.multiselect(
        "选择优先数据库（可多选）",
        databases,
        default=list(current_priority_dbs),
        format_func=lambda x: f"{x} ({db_info['databases'][x]['table_count']}个表)",
        help="选择后，系统会优先在这些数据库中查找相关表"
    )

    # 显示选择的统计
    if selected_dbs:
        total_tables = sum(db_info['databases'][db]['table_count'] for db in selected_dbs)
        st.success(f"已选择 {len(selected_dbs)} 个优先数据库，共 {total_tables} 个表")

        # 显示选择的数据库详情
        with st.expander("📋 查看选择的数据库", expanded=True):
            for db in selected_dbs:
                db_data = db_info['databases'][db]
                st.markdown(f"""
                <div class="priority-database-card">
                <strong>{db}</strong> - {db_data['table_count']} 个表
                <span class="priority-badge">优先</span>
                </div>
                """, unsafe_allow_html=True)

                # 显示前几个表
                for table in db_data['tables'][:3]:
                    col_count = db_data['tables_info'].get(table, {}).get('column_count', 0)
                    st.markdown(f"""
                    <div class="table-card">
                    &nbsp;&nbsp;📊 {table} ({col_count}个字段)
                    </div>
                    """, unsafe_allow_html=True)

                if db_data['table_count'] > 3:
                    st.caption(f"还有 {db_data['table_count']-3} 个表未显示")

    return set(selected_dbs)

# 主应用
def main():
    st.markdown('<h1 class="main-header">🤖 智能多数据库查询助手</h1>', unsafe_allow_html=True)
    st.markdown("自动发现、学习数据库结构，智能生成SQL查询（支持优先数据库）")

    # 初始化
    vn = init_vanna()

    # 初始化session state
    if 'db_info' not in st.session_state:
        st.session_state.db_info = None
    if 'query_generator' not in st.session_state:
        st.session_state.query_generator = None
    if 'training_result' not in st.session_state:
        st.session_state.training_result = None
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = IntelligentDBAssistant()
    if 'priority_databases' not in st.session_state:
        st.session_state.priority_databases = set()

    db_manager = st.session_state.db_manager

    # 侧边栏 - 数据库连接和发现
    with st.sidebar:
        st.markdown("### 🔌 数据库连接")

        col1, col2 = st.columns(2)
        with col1:
            host = st.text_input("主机地址", value=os.getenv('DB_HOST', 'localhost'))
        with col2:
            port = st.number_input("端口", value=int(os.getenv('DB_PORT', 3306)), min_value=1, max_value=65535)

        # 一键发现所有数据库
        if st.button("🔍 发现所有数据库", type="primary", use_container_width=True):
            with st.spinner("正在发现所有数据库和表..."):
                db_info = db_manager.discover_all_databases(host)

                if db_info and db_info.get('databases'):
                    st.session_state.db_info = db_info

                    # 显示统计
                    st.success("✅ 发现完成!")

                    col_stat1, col_stat2 = st.columns(2)
                    with col_stat1:
                        st.metric("数据库数量", db_info['total_databases'])
                    with col_stat2:
                        st.metric("表总数量", db_info['total_tables'])
                else:
                    st.error("❌ 未发现数据库")

        # 如果已发现数据库，显示数据库选择器
        if st.session_state.db_info is not None:
            st.markdown("---")
            st.markdown("### 🎯 优先数据库设置")

            # 数据库选择器
            selected_priority_dbs = database_selector(
                st.session_state.db_info,
                st.session_state.priority_databases
            )

            # 保存选择
            if st.button("💾 保存优先数据库设置", use_container_width=True):
                st.session_state.priority_databases = selected_priority_dbs
                st.success(f"已设置 {len(selected_priority_dbs)} 个优先数据库")

        # 一键训练所有数据库
        if st.button("🎯 一键训练所有数据库", type="primary", use_container_width=True):
            if 'db_info' not in st.session_state or st.session_state.db_info is None:
                st.warning("请先发现数据库")
            elif not vn:
                st.error("Vanna 初始化失败")
            else:
                # 创建训练器（如果不存在）
                if st.session_state.query_generator is None:
                    st.session_state.query_generator = EnhancedSmartQueryGenerator(vn)

                query_generator = st.session_state.query_generator

                # 设置优先数据库
                query_generator.set_priority_databases(st.session_state.priority_databases)

                with st.spinner("正在训练所有数据库表结构（优先数据库会优先训练）..."):
                    training_result = query_generator.train_all_databases(
                        db_manager, host, st.session_state.db_info
                    )

                st.session_state.training_result = training_result

                if training_result['success']:
                    # 显示统计
                    priority_count = len(st.session_state.priority_databases)
                    normal_count = training_result['databases_trained'] - priority_count

                    st.success("✅ 训练完成!")

                    col_train1, col_train2 = st.columns(2)
                    with col_train1:
                        st.metric("总训练数据库", training_result['databases_trained'])
                        st.caption(f"优先: {priority_count} | 普通: {normal_count}")
                    with col_train2:
                        st.metric("训练表", training_result['tables_trained'])

                    st.info(f"训练耗时: {training_result['training_time']:.1f}秒")

                    if training_result['errors']:
                        with st.expander("⚠️ 查看错误详情"):
                            for error in training_result['errors'][:5]:
                                st.error(error)
                else:
                    st.error("训练失败")

        # 显示当前状态
        st.markdown("---")
        st.markdown("### 📊 当前状态")

        if st.session_state.db_info is not None:
            info = st.session_state.db_info
            priority_count = len(st.session_state.priority_databases)
            st.write(f"**已发现**: {info['total_databases']}库/{info['total_tables']}表")
            st.write(f"**优先库**: {priority_count}个")
        else:
            st.write("**已发现**: 未发现")
            st.write("**优先库**: 未设置")

        if (st.session_state.query_generator is not None and
            hasattr(st.session_state.query_generator, 'is_trained') and
            st.session_state.query_generator.is_trained):
            trainer = st.session_state.query_generator
            st.write(f"**已训练**: {len(trainer.trained_items)}个表")
            st.write(f"**训练状态**: ✅ 已训练")
        else:
            st.write("**已训练**: 未训练")
            st.write("**训练状态**: ❌ 未训练")

    # 主界面 - 创建标签页
    tab1, tab2 = st.tabs(["💬 智能查询", "🎓 手动训练"])

    with tab1:
        # 智能查询界面
        st.markdown("### 💬 智能查询")

        # 状态显示
        if (st.session_state.db_info is not None and
            st.session_state.query_generator is not None and
            hasattr(st.session_state.query_generator, 'is_trained') and
            st.session_state.query_generator.is_trained):

            # 显示优先数据库信息
            priority_count = len(st.session_state.priority_databases)
            if priority_count > 0:
                st.success(f"✅ 系统已就绪！已设置 {priority_count} 个优先数据库，会优先在这些库中查询")
            else:
                st.success("✅ 系统已就绪，可以开始查询")
        elif st.session_state.db_info is not None:
            st.warning("⚠️ 数据库已发现，请先进行训练")
        else:
            st.info("ℹ️ 请先发现并训练数据库")

        # 查询输入
        st.markdown("#### 📝 输入您的查询需求")
        user_query = st.text_area(
            "用自然语言描述您想要查询什么",
            placeholder="例如：\n1. 帮我查 db_business表的详情\n2. 查询所有用户的信息\n3. 统计订单数量\n4. 查看用户表的字段信息",
            height=150,
            key="query_input"
        )

        # 查询选项
        col_opt1, col_opt2, col_opt3 = st.columns(3)

        with col_opt1:
            action = st.radio("操作", ["仅生成SQL", "生成并执行"])
            limit_results = st.number_input("结果限制", min_value=1, max_value=10000, value=100)

        with col_opt2:
            show_relevant = st.checkbox("显示相关表", value=True)
            auto_limit = st.checkbox("自动添加LIMIT", value=True)
            prefer_priority = st.checkbox("优先在优先库查询", value=True)

        with col_opt3:
            show_sql = st.checkbox("显示原始SQL", value=True)
            explain_query = st.checkbox("解释查询", value=False)

        # 执行查询按钮
        if st.button("🚀 开始智能查询", type="primary", use_container_width=True) and user_query:
            if st.session_state.query_generator is None:
                st.error("请先训练数据库")
                return

            if not hasattr(st.session_state.query_generator, 'is_trained') or not st.session_state.query_generator.is_trained:
                st.error("请先训练数据库")
                return

            query_generator = st.session_state.query_generator
            db_info = st.session_state.db_info

            # 步骤1: 智能生成查询
            with st.spinner("🔍 正在分析查询需求..."):
                query_result = query_generator.generate_smart_query(user_query, db_info)

            if not query_result['success']:
                st.error(f"生成查询失败: {query_result.get('error', '未知错误')}")
                return

            # 显示匹配类型
            match_type = query_result.get('match_type', 'unknown')
            if match_type == 'exact_table':
                st.success("🎯 已精确匹配到表名!")
            elif match_type == 'vanna_generated':
                st.info("🤖 使用Vanna智能生成")

            # 显示相关信息
            if show_relevant and query_result['relevant_info']['total_matches'] > 0:
                st.markdown("#### 🎯 相关数据库和表")

                relevant_info = query_result['relevant_info']

                for db_name, db_data in relevant_info['databases'].items():
                    is_priority = db_data.get('priority', False)
                    priority_badge = " 🎯" if is_priority else ""

                    with st.expander(f"📁 {db_name}{priority_badge} ({db_data['table_count']}个相关表)", expanded=is_priority):
                        for table_name, table_info in db_data['tables'].items():
                            st.write(f"**表: {table_name}**")
                            for match in table_info['matches'][:3]:
                                st.write(f"  • {match}")

            # 显示生成的SQL
            st.markdown("#### 📄 生成的SQL")

            sql = query_result['sql']

            # 添加LIMIT子句
            if auto_limit and 'limit' not in sql.lower() and action == "生成并执行":
                if sql.strip().endswith(';'):
                    sql = sql[:-1] + f" LIMIT {limit_results};"
                else:
                    sql += f" LIMIT {limit_results}"

            st.markdown(f'<div class="sql-container">{sql}</div>', unsafe_allow_html=True)

            # 执行查询
            if action == "生成并执行":
                with st.spinner("⚡ 正在执行查询..."):
                    # 确定查询的数据库
                    databases_to_query = query_result.get('used_databases', [])

                    # 如果没有指定数据库，从SQL中提取
                    if not databases_to_query:
                        # 从SQL中提取数据库名
                        pattern = r'`?(\w+)`?\.`?(\w+)`?'
                        matches = re.findall(pattern, sql)
                        for db_match, _ in matches:
                            if db_match in db_info.get('databases', {}):
                                databases_to_query.append(db_match)

                    # 如果还是没有，在所有数据库中尝试
                    if not databases_to_query:
                        if prefer_priority and st.session_state.priority_databases:
                            databases_to_query = list(st.session_state.priority_databases)[:3]
                        else:
                            databases_to_query = list(db_info['databases'].keys())[:3]

                    all_results = {}
                    errors = []

                    for db in databases_to_query:
                        try:
                            results, error = db_manager.execute_query(host, db, sql)

                            if error:
                                errors.append(f"{db}: {error}")
                            elif results:
                                all_results[db] = pd.DataFrame(results)
                        except Exception as e:
                            errors.append(f"{db}: {str(e)}")

                    # 显示结果
                    if all_results:
                        st.markdown("#### 📊 查询结果")

                        total_records = 0
                        priority_results = 0
                        normal_results = 0

                        # 显示结果
                        for db, df in all_results.items():
                            total_records += len(df)

                            is_priority = db in st.session_state.priority_databases
                            if is_priority:
                                priority_results += len(df)
                            else:
                                normal_results += len(df)

                            priority_badge = " 🎯" if is_priority else ""
                            with st.expander(f"✅ 数据库: {db}{priority_badge} ({len(df)} 条记录)", expanded=is_priority):
                                st.dataframe(df, use_container_width=True)

                                # 数据统计
                                col_stat1, col_stat2 = st.columns(2)
                                with col_stat1:
                                    st.write(f"**数据维度**: {df.shape[0]} 行 × {df.shape[1]} 列")
                                with col_stat2:
                                    st.write(f"**数据大小**: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")

                                # 下载按钮
                                csv = df.to_csv(index=False).encode('utf-8')
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                st.download_button(
                                    f"📥 下载 {db} 的数据",
                                    csv,
                                    f"{db}_query_{timestamp}.csv",
                                    "text/csv",
                                    key=f"download_{db}"
                                )

                        # 显示总体统计
                        st.success(f"✅ 总共在 {len(all_results)} 个数据库中找到了 {total_records} 条记录")
                        if priority_results > 0:
                            st.info(f"🎯 其中 {priority_results} 条来自优先数据库")

                    elif errors:
                        st.error("❌ 查询执行失败")
                        with st.expander("查看错误详情"):
                            for error in errors:
                                st.error(error)
                    else:
                        st.info("ℹ️ 查询成功，但未找到匹配的数据")

        # 数据库概览
        if st.session_state.db_info is not None:
            st.markdown("---")
            st.markdown("### 📋 数据库概览")

            info = st.session_state.db_info
            priority_dbs = st.session_state.priority_databases

            # 显示统计
            col_overview1, col_overview2, col_overview3 = st.columns(3)
            with col_overview1:
                st.metric("总数据库", info['total_databases'])
                st.caption(f"优先: {len(priority_dbs)}")
            with col_overview2:
                st.metric("总表数", info['total_tables'])
            with col_overview3:
                avg_tables = info['total_tables'] / max(1, info['total_databases'])
                st.metric("平均表数", f"{avg_tables:.1f}")

            # 显示数据库列表
            with st.expander("📁 查看所有数据库", expanded=False):
                # 先显示优先数据库
                if priority_dbs:
                    st.markdown("#### 🎯 优先数据库")
                    for db_name in priority_dbs:
                        if db_name in info['databases']:
                            db_data = info['databases'][db_name]
                            col_db1, col_db2 = st.columns([3, 1])
                            with col_db1:
                                st.markdown(f"**{db_name}** 🎯")
                                table_list = ", ".join(db_data['tables'][:5])
                                if len(db_data['tables']) > 5:
                                    table_list += f" 等 {db_data['table_count']} 个表"
                                st.write(f"表: {table_list}")
                            with col_db2:
                                st.write(f"{db_data['table_count']} 个表")

                # 显示其他数据库
                other_dbs = [db for db in info['databases'].keys() if db not in priority_dbs]
                if other_dbs:
                    st.markdown("#### 📊 其他数据库")
                    for db_name in other_dbs[:10]:
                        db_data = info['databases'][db_name]
                        col_db1, col_db2 = st.columns([3, 1])
                        with col_db1:
                            st.markdown(f"**{db_name}**")
                            table_list = ", ".join(db_data['tables'][:3])
                            if len(db_data['tables']) > 3:
                                table_list += f" 等 {db_data['table_count']} 个表"
                            st.write(f"表: {table_list}")
                        with col_db2:
                            st.write(f"{db_data['table_count']} 个表")

                    if len(other_dbs) > 10:
                        st.info(f"还有 {len(other_dbs)-10} 个数据库未显示")

    with tab2:
        # 手动训练界面
        if vn and st.session_state.db_info is not None:
            # 创建或获取训练管理器
            if st.session_state.query_generator is not None:
                training_manager = st.session_state.query_generator.training_manager
            else:
                training_manager = VannaTrainingManager(vn)

            show_manual_training_interface(
                training_manager,
                db_manager,
                host,
                st.session_state.db_info
            )
        else:
            st.warning("请先初始化Vanna并发现数据库")

            if not vn:
                st.error("Vanna未初始化")
            if st.session_state.db_info is None:
                st.error("数据库未发现")

# 运行应用
if __name__ == "__main__":
    main()