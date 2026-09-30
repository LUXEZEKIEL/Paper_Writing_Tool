"""算法伪代码 Web 聊天助手 —— 本地网页聊天界面

用法:
  export DEEPSEEK_API_KEY=sk-xxx   # 或 DASHSCOPE_API_KEY（通义千问）
  .venv/bin/python app.py
然后浏览器打开 http://127.0.0.1:7860

特性: 多轮对话（可追问"改成递归版本"）、流式输出、LaTeX 代码块一键复制、历史保存在浏览器 localStorage。
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openai import OpenAI

# ---------- API 配置（与 code2pseudo.py 一致，支持 DeepSeek 或 DashScope） ----------
api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
base_url = (
    "https://api.deepseek.com"
    if os.environ.get("DEEPSEEK_API_KEY")
    else "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
model_name = "deepseek-chat" if os.environ.get("DEEPSEEK_API_KEY") else "qwen-plus"
has_key = bool(api_key)

client = OpenAI(api_key=api_key or "no-key", base_url=base_url)

SYSTEM_PROMPT = r"""你是一位计算机算法论文排版助手。
请将用户提供的算法逻辑/Python代码，转换成符合 IEEE/ACM 顶会期刊标准的 LaTeX 伪代码。

【排版要求】:
1. 使用 standard algorithmicx / algpseudocode 宏包环境（\begin{algorithm} ... \begin{algorithmic} ... \end{algorithmic} \end{algorithm}）。
2. 包含规范的 \Require (输入), \Ensure (输出)。
3. 数学变量用 $...$ 包裹，包含清晰的循环、条件分支和步骤注释。
4. 伪代码必须放在 ```latex 代码块中，可配一两句简短说明，不要长篇大论。
"""

# ---------- 网页（内嵌，保持单文件可拷贝；注意必须用 r-string，避免 Python 吞掉 JS 里的 \n） ----------
HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>算法伪代码助手</title>
<style>
  :root {
    --bg: #0f1117; --panel: #171a23; --panel2: #1e2230;
    --text: #e6e8ee; --muted: #9aa1b5; --accent: #4f8cff;
    --user: #2b4a8f; --border: #2a2f3e; --code: #0b0d13;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text); height: 100vh;
    display: flex; flex-direction: column; align-items: center;
  }
  header {
    width: 100%; max-width: 780px; padding: 14px 20px 10px;
    display: flex; align-items: center; gap: 10px;
  }
  header h1 { font-size: 17px; margin: 0; font-weight: 600; }
  header .badge {
    font-size: 12px; color: var(--muted); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 999px;
  }
  .banner {
    width: 100%; max-width: 780px; margin: 6px auto 0; padding: 10px 20px;
    background: #3a2a12; border: 1px solid #6b4d1d; border-radius: 10px;
    font-size: 13px; color: #f0c674;
  }
  .cfg-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .cfg-row select, .cfg-row input {
    background: var(--bg); border: 1px solid var(--border); color: var(--text);
    border-radius: 8px; padding: 6px 10px; font-size: 13px; outline: none;
  }
  .cfg-row input { flex: 1; min-width: 200px; }
  .cfg-row button {
    background: var(--accent); color: #fff; border: none; border-radius: 8px;
    padding: 6px 16px; font-size: 13px; cursor: pointer;
  }
  #keyStatus { color: #7dbf7d; }
  .cfg-note { margin-top: 6px; color: var(--muted); font-size: 12px; }
  #chat {
    flex: 1; width: 100%; max-width: 780px; padding: 16px 20px;
    overflow-y: auto; display: flex; flex-direction: column; gap: 14px;
  }
  .row { display: flex; }
  .row.user { justify-content: flex-end; }
  .bubble {
    max-width: 88%; padding: 10px 14px; border-radius: 14px;
    font-size: 14.5px; line-height: 1.65; white-space: normal;
    word-break: break-word; overflow-wrap: anywhere;
  }
  .row.user .bubble { background: var(--user); border-bottom-right-radius: 4px; }
  .row.assistant .bubble {
    background: var(--panel); border: 1px solid var(--border); border-bottom-left-radius: 4px;
  }
  .row.assistant .bubble .streaming-cursor::after {
    content: "▍"; color: var(--accent); animation: blink 1s steps(1) infinite;
  }
  @keyframes blink { 50% { opacity: 0; } }
  .codeblock { margin: 8px 0; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
  .codebar {
    display: flex; justify-content: space-between; align-items: center;
    background: var(--panel2); padding: 5px 12px; font-size: 12px; color: var(--muted);
  }
  .copy-btn {
    background: none; border: 1px solid var(--border); color: var(--muted);
    border-radius: 6px; padding: 2px 10px; font-size: 12px; cursor: pointer;
  }
  .copy-btn:hover { color: var(--text); border-color: var(--accent); }
  .codeblock pre {
    margin: 0; padding: 12px 14px; background: var(--code);
    overflow-x: auto; font-size: 13px; line-height: 1.6;
    font-family: "SF Mono", Menlo, Consolas, monospace;
  }
  .bubble code {
    background: var(--panel2); padding: 1px 5px; border-radius: 4px;
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 13px;
  }
  footer {
    width: 100%; max-width: 780px; padding: 8px 20px 16px;
  }
  .toolbar { display: flex; gap: 8px; margin-bottom: 8px; }
  .toolbar button {
    background: none; border: 1px solid var(--border); color: var(--muted);
    border-radius: 8px; padding: 4px 12px; font-size: 12.5px; cursor: pointer;
  }
  .toolbar button:hover { color: var(--text); border-color: var(--accent); }
  .inputwrap {
    display: flex; gap: 10px; align-items: flex-end;
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 14px; padding: 10px 12px;
  }
  .inputwrap:focus-within { border-color: var(--accent); }
  textarea {
    flex: 1; background: none; border: none; outline: none; resize: none;
    color: var(--text); font-size: 14.5px; line-height: 1.6;
    font-family: inherit; max-height: 180px;
  }
  textarea::placeholder { color: var(--muted); }
  #sendBtn {
    background: var(--accent); color: #fff; border: none; border-radius: 10px;
    padding: 8px 18px; font-size: 14px; cursor: pointer; flex-shrink: 0;
  }
  #sendBtn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
</head>
<body>
<header>
  <h1>📐 算法伪代码助手</h1>
  <span class="badge">{{MODEL}}</span>
</header>
<div class="banner" id="keyBanner" hidden>
  <div class="cfg-row">
    <select id="providerSel">
      <option value="deepseek">DeepSeek</option>
      <option value="dashscope">通义千问 (DashScope)</option>
    </select>
    <input type="password" id="keyInput" placeholder="在这里粘贴 API Key (sk-...)">
    <button id="saveKeyBtn">保存</button>
    <span id="keyStatus"></span>
  </div>
  <div class="cfg-note">Key 只保存在本机浏览器 localStorage，随请求发送给所选模型服务；也可改用环境变量 <code>DEEPSEEK_API_KEY</code> / <code>DASHSCOPE_API_KEY</code> 后重启。</div>
</div>
<div id="chat"></div>
<footer>
  <div class="toolbar">
    <button id="sampleBtn">填入示例算法</button>
    <button id="clearBtn">清空对话</button>
  </div>
  <div class="inputwrap">
    <textarea id="input" rows="1" placeholder="粘贴算法逻辑或 Python 代码，Enter 发送，Shift+Enter 换行…"></textarea>
    <button id="sendBtn">发送</button>
  </div>
</footer>
<script>
const chatEl = document.getElementById('chat');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const keyBanner = document.getElementById('keyBanner');
const keyInput = document.getElementById('keyInput');
const providerSel = document.getElementById('providerSel');
const keyStatus = document.getElementById('keyStatus');
const HAS_KEY = {{HAS_KEY}};
let messages = [];   // [{role, content}]
let streaming = false;

// 浏览器端保存的 API Key（仅本机 localStorage）
let apiCfg = null;
try { apiCfg = JSON.parse(localStorage.getItem('api_cfg') || 'null'); } catch (e) {}
if (!HAS_KEY) {
  keyBanner.hidden = false;
  if (apiCfg) {
    keyInput.value = apiCfg.key;
    providerSel.value = apiCfg.provider;
    keyStatus.textContent = '已保存 ✓';
  }
}
document.getElementById('saveKeyBtn').onclick = () => {
  const key = keyInput.value.trim();
  if (!key) { keyStatus.textContent = 'Key 为空'; return; }
  apiCfg = { key, provider: providerSel.value };
  localStorage.setItem('api_cfg', JSON.stringify(apiCfg));
  keyStatus.textContent = '已保存 ✓';
};

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function codeBlock(code, lang) {
  return '<div class="codeblock"><div class="codebar"><span>' + esc(lang) +
    '</span><button class="copy-btn" onclick="copyCode(this)">复制</button></div>' +
    '<pre><code>' + esc(code) + '</code></pre></div>';
}

function renderInline(s) {
  let h = esc(s);
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\n/g, '<br>');
  return h;
}

function renderContent(text) {
  const re = /```(\w*)\n?([\s\S]*?)```/g;
  let out = '', last = 0, m;
  while ((m = re.exec(text))) {
    out += renderInline(text.slice(last, m.index));
    out += codeBlock(m[2].trim(), m[1] || 'code');
    last = re.lastIndex;
  }
  out += renderInline(text.slice(last));
  return out;
}

function addRow(role) {
  const row = document.createElement('div');
  row.className = 'row ' + role;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  row.appendChild(bubble);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function copyCode(btn) {
  const code = btn.closest('.codeblock').querySelector('pre').innerText;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = '已复制 ✓';
    setTimeout(() => { btn.textContent = '复制'; }, 1500);
  }).catch(() => {});
}

function restore() {
  try {
    const saved = JSON.parse(localStorage.getItem('algo_chat') || '[]');
    saved.forEach(m => {
      if (m.role === 'user') { addRow('user').innerHTML = renderContent(m.content); }
      else { addRow('assistant').innerHTML = renderContent(m.content); }
      messages.push(m);
    });
  } catch (e) {}
}

function save() {
  try { localStorage.setItem('algo_chat', JSON.stringify(messages)); } catch (e) {}
}

function setStreaming(on) {
  streaming = on;
  sendBtn.disabled = on;
}

async function send() {
  const text = inputEl.value.trim();
  if (!text || streaming) return;
  inputEl.value = ''; inputEl.style.height = 'auto';
  addRow('user').innerHTML = renderContent(text);
  messages.push({ role: 'user', content: text });
  setStreaming(true);
  const bubble = addRow('assistant');
  bubble.classList.add('streaming-cursor');
  let acc = '';
  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        api_key: apiCfg ? apiCfg.key : '',
        provider: apiCfg ? apiCfg.provider : 'deepseek'
      })
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx); buf = buf.slice(idx + 2);
        for (const line of raw.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6);
          if (payload === '[DONE]') {
            finish(); return;
          }
          try {
            const obj = JSON.parse(payload);
            if (obj.error) { acc += '\n\n⚠️ ' + obj.error; finish(); return; }
            if (obj.delta) {
              acc += obj.delta;
              bubble.innerHTML = esc(acc);
              chatEl.scrollTop = chatEl.scrollHeight;
            }
          } catch (e) {}
        }
      }
    }
    finish();
  } catch (e) {
    acc += '\n\n⚠️ 请求失败: ' + e.message;
    finish();
  }
  function finish() {
    bubble.classList.remove('streaming-cursor');
    bubble.innerHTML = renderContent(acc);
    if (acc.trim()) messages.push({ role: 'assistant', content: acc });
    save();
    setStreaming(false);
    chatEl.scrollTop = chatEl.scrollHeight;
  }
}

const SAMPLE = `算法名称: Dynamic Subcomponent Optimizer
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
3. 返回非支配解集作为 P_best`;

document.getElementById('sampleBtn').onclick = () => {
  inputEl.value = SAMPLE; inputEl.focus();
  inputEl.style.height = 'auto';
  inputEl.style.height = inputEl.scrollHeight + 'px';
};
document.getElementById('clearBtn').onclick = () => {
  if (streaming) return;
  messages = [];
  chatEl.innerHTML = '';
  save();
};
sendBtn.onclick = send;
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 180) + 'px';
});

restore();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = (HTML.replace("{{MODEL}}", model_name)
                        .replace("{{HAS_KEY}}", "true" if has_key else "false")
                        .encode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            history = (payload.get("messages") or [])[-12:]  # 只带最近 12 条，控制 token
        except Exception:
            payload = {}
            history = []

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.close_connection = True  # SSE 结束后即断开连接，作为流结束信号

        def emit(obj):
            self.wfile.write(
                ("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8")
            )
            self.wfile.flush()

        # 环境变量优先；否则用浏览器页面里保存的 key
        req_key = payload.get("api_key") or ""
        provider = payload.get("provider") or "deepseek"
        if not has_key and req_key:
            url = (
                "https://api.deepseek.com"
                if provider == "deepseek"
                else "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            mdl = "deepseek-chat" if provider == "deepseek" else "qwen-plus"
            req_client = OpenAI(api_key=req_key, base_url=url)
        else:
            url, mdl, req_client = base_url, model_name, client

        if not has_key and not req_key:
            emit({"error": "未设置 API Key：请在上方输入框粘贴 Key（选择 DeepSeek 或通义千问）并点「保存」；或设置 DEEPSEEK_API_KEY / DASHSCOPE_API_KEY 环境变量后重启 app.py"})
            return

        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + [
            {"role": m.get("role"), "content": m.get("content")}
            for m in history
            if m.get("content")
        ]
        try:
            stream = req_client.chat.completions.create(
                model=mdl, messages=msgs, temperature=0.1, stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    emit({"delta": chunk.choices[0].delta.content})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as e:
            emit({"error": f"调用 {mdl} 失败: {e}"})

    def log_message(self, fmt, *args):  # 安静模式
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"🚀 算法伪代码助手已启动: http://127.0.0.1:{port}  (Ctrl+C 退出)")
    print(f"   模型: {model_name}" + ("  ⚠️ 未设置 API Key，页面会提示" if not has_key else ""))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 已退出")
