# nlp2sql-vanna
智能多数据库查询助手 (Intelligent Multi-Database Query Assistant)  这是一个基于Streamlit和Vanna框架构建的智能数据库查询平台，支持MySQL数据库的自动发现、智能学习和自然语言查询。
项目集成了阿里云Qwen大模型，能够将自然语言问题自动转换为SQL查询语句，大大简化了数据库查询流程。

# 智能多数据库查询助手 🤖

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B)](https://streamlit.io/)
[![MySQL](https://img.shields.io/badge/MySQL-5.7%2B-4479A1)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

一个基于人工智能的多数据库查询管理平台，能够将自然语言问题自动转换为SQL查询语句。

## ✨ 主要特性

### 🔍 智能数据库发现
- 自动扫描MySQL服务器中的所有数据库和表
- 实时展示数据库结构和统计信息
- 支持表结构分析和字段查看

### 🧠 智能查询生成
- 使用阿里云Qwen大模型进行SQL生成
- 支持自然语言到SQL的智能转换
- 自动匹配表名和字段名

### 🎯 优先数据库系统
- 可设置常用数据库为优先数据库
- 优先在常用数据库中查找相关表
- 优化查询效率和准确性

### 📚 多模式训练系统
1. **DDL训练** - 训练表的创建语句
2. **文档训练** - 训练表和字段的描述文档
3. **问题-SQL对训练** - 训练自然语言到SQL的映射
4. **AI批量生成** - 使用AI生成多样化的训练数据

### 🖥️ 现代化界面
- 基于Streamlit的响应式Web界面
- 直观的数据展示和交互
- 实时查询结果展示

## 🚀 快速开始

### 环境要求
- Python 3.8+
- MySQL 5.7+
- 阿里云DashScope API密钥

### 安装步骤

## 1.**克隆仓库**
```bash
cd nlp2sql-vanna
```
## 2.**配置环境变量**
### 数据库配置
DB_HOST=localhost  
DB_PORT=3306  
DB_USER=root  
DB_PASSWORD=your_password  

### 阿里云API配置
ALI_API_KEY=your_aliyun_api_key  
ALI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  
VANNA_MODEL=qwen-plus  

## 3.**运行程序**
```bash
streamlit run app.py
```

## 4.**访问界面**
localhost:8501
