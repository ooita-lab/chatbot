import streamlit as st
import requests

# 💡 システム命令の定義
# これがチャットボットの「人格」と「ルール」を定義します。
SYSTEM_INSTRUCTION = """
あなたは、工学部の学生向けのレポート専門のピアレビューアシスタントです。
あなたの役割は、学生が入力した文章に含まれる「工学レポートとして不適切な用語」「曖昧な表現」「論理の飛躍」を指摘することに限定されます。

以下のルールを厳守してください。

1.  **完全な添削や修正後の文章を提供してはいけません。**
2.  **指導的なトーンを維持し、指摘箇所について学生自身に考えさせるような質問やヒントを提供してください。**
3.  具体的にどの単語やフレーズが不適切か、またはなぜその用語が曖昧なのかを明確に指摘し、「なぜこの単語を使うのが適切ではないか考えよう」「この概念を工学分野でより専門的に表現する用語は何だろうか」といった質問を投げかけてください。
4.  出力は指摘形式（例: 箇条書き）で簡潔に行い、解説を加えてください。
"""

# タイトルと説明の表示
st.title("💡 工学部レポート チェッカー")
st.write("このアシスタントは、あなたが入力した文章を読み、**工学レポートとして不適切**な用語や表現のみを指摘し、学生自身に修正させるためのヒントを提供します。")

# Streamlit Community CloudのSecretsからAPIキーを取得
gemini_api_key = st.secrets.get("GEMINI_API_KEY")

if not gemini_api_key:
    st.info("Streamlit Community CloudのSecretsに `GEMINI_API_KEY` を設定してください。", icon="🗝️")
else:
    # ユーザーがモデルを選択できるようにする（正しいモデル名表記を使用）
    model_name = st.selectbox(
        "使用する Gemini モデルを選択",
        (
            "gemini-2.5-flash", 
            "gemini-2.5-pro"
        ),
        index=0 # flashをデフォルトにする
    )

    if "messages" not in st.session_state:
        # 初期のメッセージリストをセッションステートに作成
        st.session_state.messages = []

    # 既存のチャットメッセージを表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザーがメッセージを入力するためのチャット入力フィールド
    if prompt := st.chat_input("レポートの文章を入力してください（例: この実験はすごく成功した）"):

        # ユーザーのプロンプトを保存・表示
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Gemini API用にメッセージ形式を準備（ロールを "user" または "model" に変換）
        # NOTE: systemInstructionを使用するため、チャット履歴はそのままcontentsに渡します。
        gemini_messages = []
        for m in st.session_state.messages:
            # StreamlitのロールをAPIのロールにマッピング
            api_role = "user" if m["role"] == "user" else "model"
            gemini_messages.append(
                {
                    "role": api_role,
                    "parts": [{"text": m["content"]}]
                }
            )

        # Gemini API endpoint
        # V1 Beta APIを使用するため、URLを修正
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_api_key}"

        headers = {"Content-Type": "application/json"}
        data = {
            # 💡 追加: モデルの役割を定義するシステム命令
            "systemInstruction": {
                "parts": [{"text": SYSTEM_INSTRUCTION}]
            },
            "contents": gemini_messages,
            "generationConfig": {
                # 💡 修正: 温度を下げ、論理的・集中的な回答を促す
                "temperature": 0.5, 
                "topP": 0.8
            }
        }

        try:
            # アシスタントの応答をチャットメッセージコンテナ内に表示
            with st.chat_message("assistant"):
                with st.spinner(f"{model_name} が指摘を生成中..."):
                    response = requests.post(api_url, headers=headers, json=data, timeout=30)
                    response.raise_for_status() # HTTPエラーがあれば例外を発生
                    
                    result = response.json()
                    
                    # APIからのレスポンス構造のチェックと応答の取得
                    gemini_reply = "API応答を解析できませんでした。"
                    if "candidates" in result and result["candidates"]:
                        candidate = result["candidates"][0]
                        if "content" in candidate and \
                           "parts" in candidate["content"] and \
                           candidate["content"]["parts"]:
                            
                            gemini_reply = candidate["content"]["parts"][0]["text"]
                        
                    st.markdown(gemini_reply)
            
            # アシスタントの応答をセッションステートに保存
            st.session_state.messages.append({"role": "assistant", "content": gemini_reply})

        except requests.exceptions.RequestException as e:
            error_message = f"APIリクエストエラーが発生しました。インターネット接続、またはAPIキーが有効か確認してください。詳細: {e}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
        except Exception as e:
            error_message = f"予期せぬエラーが発生しました。詳細: {e}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
