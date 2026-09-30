import os
import sys
from openai import OpenAI

# 1. 配置 API 凭证与模型地址（支持 DeepSeek 或通义千问 DashScope）
api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
base_url = (
    "https://api.deepseek.com"
    if os.environ.get("DEEPSEEK_API_KEY")
    else "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
model_name = "deepseek-chat" if os.environ.get("DEEPSEEK_API_KEY") else "qwen-plus"

# 如果环境变量未设置，可以在下面直接填入你的 API Key（例如: api_key = "sk-xxxx"）
if not api_key:
    print("❌ 未检测到 API Key，请设置环境变量或直接在代码中填入 api_key。")
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url=base_url)

# 2. 专门针对学术顶会/顶刊格式的提示词
prompt_template = """你是一位计算机算法论文排版助手。
请将用户提供的算法逻辑/Python代码，转换成符合 IEEE/ACM 顶会期刊标准的 LaTeX 伪代码。

【排版要求】:
1. 使用 standard algorithmicx / algpseudocode 宏包环境（\\begin{{algorithm}} ... \\begin{{algorithmic}} ... \\end{{algorithmic}} \\end{{algorithm}}）。
2. 包含规范的 \\Require (输入), \\Ensure (输出)。
3. 数学变量用 $...$ 包裹，包含清晰的循环、条件分支和步骤注释。
4. 只输出纯 LaTeX 代码块，不要包含任何多余的开场白或解释。

【用户算法输入】:
{user_input}
"""

def generate_pseudocode(algo_text):
    print("⏳ 正在转换为学术级 LaTeX 伪代码...\n")
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt_template.format(user_input=algo_text)}],
        temperature=0.1
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    # 测试输入：一段简单的多目标优化/进化算法流程逻辑（后续可随时换成你自己的逻辑或 Python 代码）
    sample_input = """
    算法名称: Dynamic Subcomponent Optimizer
    输入: 种群 P, 最大代数 G_max, 变量分组列表 Groups
    输出: 最优解集合 P_best
    流程:
    1. 初始化种群 P，评估每个个体的适应度
    2. 循环代数 g 从 1 到 G_max:
       a. 遍历每个子组件分组 group:
          - 在当前分组上执行自适应变异和交叉操作
          - 计算局部子问题适应度
       b. 协同各个子组件，合并形成完整决策向量
       c. 执行非支配排序与拥挤度筛选，保留优质个体更新种群 P
    3. 返回非支配解集作为 P_best
    """
    
    latex_code = generate_pseudocode(sample_input)
    print("---- [生成的 LaTeX 伪代码] ----\n")
    print(latex_code)
    
    # 自动输出保存为 algo.tex 文件
    with open("algo.tex", "w", encoding="utf-8") as f:
        f.write(latex_code)
    print("\n✅ 已自动保存至当前目录下的 algo.tex！")