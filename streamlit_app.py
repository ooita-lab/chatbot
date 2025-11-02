import streamlit as st
import requests
import pandas as pd # 💡 追加: pandasをインポート

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
st.write("このアシスタントは、**手動入力**または**CSVファイルアップロード**された文章を読み、工学レポートとして不適切な用語や表現のみを指摘し、学生自身に修正させるためのヒントを提供します。")

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

    # ----------------------------------------------------
    # CSVファイルアップロードセクションの追加
    # ----------------------------------------------------
    uploaded_file = st.file_uploader("CSVファイルをアップロードしてください（B列の文章をチェックします）", type="csv")
    
    if uploaded_file:
        st.subheader("CSVファイルの一括チェックを実行中...")
        
        # CSVファイルの読み込み
        try:
            # ヘッダーがあることを想定し、最初の行をヘッダーとして使用
            df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
            st.stop()
            
        # B列のインデックス（インデックス1）が存在するかチェック
        if df.shape[1] < 2:
             st.warning("アップロードされたCSVにはB列（インデックス1）が存在しません。")
             st.stop()

        # B列の名前を取得（ヘッダー行 B1）
        b_column_name = df.columns[1]

        # B2以降の行を処理 (インデックス1から最後まで)
        texts_to_check = df.iloc[1:, 1].dropna().tolist() # B2 (インデックス1) から最後までをリスト化し、欠損値を除外
        
        if not texts_to_check:
            st.info("B2以降のセルにチェックすべき有効な文章が見つかりませんでした。")
        else:
            st.info(f"合計 {len(texts_to_check)} 個の文章をチェックします。")
            
            # 結果を格納するためのコンテナ
            results_container = st.container()

            # 各文章を繰り返し処理してAPIに送信
            for i, text_prompt in enumerate(texts_to_check):
                # 処理中の文章を表示
                results_container.markdown(f"#### 📄 文章 {i + 2} (B{i + 2}セル):")
                results_container.text(text_prompt)

                # Gemini API endpoint
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_api_key}"

                headers = {"Content-Type": "application/json"}
                data = {
                    "systemInstruction": {
                        "parts": [{"text": SYSTEM_INSTRUCTION}]
                    },
                    # 💡 注意: 一括チェック時はチャット履歴を使わず、現在のテキストのみをcontentsに渡す
                    "contents": [{"role": "user", "parts": [{"text": text_prompt}]}],
                    "generationConfig": {
                        "temperature": 0.5, 
                        "topP": 0.8
                    }
                }

                try:
                    with results_container.spinner(f"文章 {i + 2} の指摘を生成中..."):
                        response = requests.post(api_url, headers=headers, json=data, timeout=30)
                        response.raise_for_status()
                        
                        result = response.json()
                        
                        gemini_reply = "API応答を解析できませんでした。"
                        if "candidates" in result and result["candidates"]:
                            candidate = result["candidates"][0]
                            if "content" in candidate and \
                               "parts" in candidate["content"] and \
                               candidate["content"]["parts"]:
                                
                                gemini_reply = candidate["content"]["parts"][0]["text"]
                            
                        # 結果を表示
                        results_container.markdown(f"**指摘 ({model_name}):**")
                        results_container.markdown(gemini_reply)
                        results_container.markdown("---") # 区切り線
                
                except requests.exceptions.RequestException as e:
                    error_message = f"文章 {i + 2} のAPIリクエストエラー: {e}"
                    results_container.error(error_message)
                    results_container.markdown("---")
                except Exception as e:
                    error_message = f"文章 {i + 2} で予期せぬエラーが発生しました: {e}"
                    results_container.error(error_message)
                    results_container.markdown("---")

            st.success("CSVファイルの一括チェックが完了しました！")
    
    # ----------------------------------------------------
    # 通常のチャットセクション (ファイルがアップロードされていない場合のみ表示)
    # ----------------------------------------------------
    if not uploaded_file:
        if "messages" not in st.session_state:
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
