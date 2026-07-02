# BUCT_Card_Report

北京化工大学校园卡消费数据分析报告生成器。

## 功能

- 从校园卡系统自动拉取消费流水（支持近10个月数据）
- 内置多维度消费分析（月度趋势、分类统计、商户排名、用餐时段）
- 生成精美的 HTML 可视化报告
- 可选接入大模型（DeepSeek/通义千问/硅基流动）生成个性化洞察

## 快速开始

```bash
pip install -r requirements.txt
playwright install chromium
python app.py
# 打开 http://localhost:5000
```

## 使用方法

1. 在企业微信中打开校园卡页面
2. 复制页面链接（包含 openid 参数）
3. 粘贴到本应用的输入框
4. 等待数据拉取完成，选择分析方式
5. 生成并下载报告

## 可选：大模型增强

设置环境变量即可启用 LLM 个性化分析：

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.deepseek.com/v1"   # DeepSeek
# export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 通义千问
# export LLM_BASE_URL="https://api.siliconflow.cn/v1"  # 硅基流动
export LLM_MODEL="deepseek-chat"
```
