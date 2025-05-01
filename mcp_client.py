import sys, asyncio
from dotenv import load_dotenv
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# .env から API キー等を読み込む
load_dotenv()

# 定数：モデル名と最大トークン数
MODEL = "claude-3-5-sonnet-20241022"
MAX_TOKENS = 1000

# セッションから使えるツール一覧を取得
async def list_tools(session):
    resp = await session.list_tools()
    return [
        {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
        for t in resp.tools
    ]

# Anthropic Messages API 呼び出しラッパー
# → system 指示はトップレベル引数として渡す
def llm_call(anth, messages, tools=None, system=None):
    params = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
    }
    if tools:
        params["tools"] = tools
    if system:
        params["system"] = system
    return anth.messages.create(**params)

# ツール使用時の一連の処理
async def handle_tool(part, session, anth, messages, llm_text):
    # ツール呼び出し前の説明テキストを追加
    prompt = getattr(part, "text", "")
    if prompt:
        llm_text.append(prompt)
        messages.append({"role": "assistant", "content": prompt})

    # 実際にツールを呼ぶ
    result = await session.call_tool(part.name, part.input)

    # ツール結果を user メッセージ化して会話に追加
    if isinstance(result.content, str):
        user_input = result.content
    else:
        user_input = "".join(getattr(item, "text", str(item)) for item in result.content)
    messages.append({"role": "user", "content": user_input})

    # フォローアップの LLM 呼び出しと結果処理
    followup = llm_call(anth, messages)
    for p in followup.content:
        if p.type == "text":
            llm_text.append(p.text)
            messages.append({"role": "assistant", "content": p.text})

# メイン処理：MCP サーバ接続から対話のループまで
async def main(server_script: str, query: str):
    # サーバ実行コマンド判定 (.py → python, .js → node)
    cmd = "python" if server_script.endswith(".py") else "node"
    params = StdioServerParameters(command=cmd, args=[server_script])

    # stdio 経由で MCP サーバに接続しセッション開始
    async with stdio_client(params) as (stdio, write), ClientSession(stdio, write) as session:
        await session.initialize()

        # ツール一覧取得 & LLM クライアント生成
        tools = await list_tools(session)
        anth = Anthropic()

        # 最初のユーザー質問を messages に格納
        messages = [{"role": "user", "content": query}]
        ai_resp = llm_call(anth, messages, tools=tools)
        
        # LLM の返答パートを順次処理しつつコンソール出力
        llm_text: list[str] = []
        for part in ai_resp.content:
            if part.type == "text":
                llm_text.append(part.text)
                messages.append({"role": "assistant", "content": part.text})
            elif part.type == "tool_use":
                await handle_tool(part, session, anth, messages, llm_text)
            # 最後に追加されたテキストを表示
            print(llm_text[-1])

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python client.py <path_to_server.py|.js> <query>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
