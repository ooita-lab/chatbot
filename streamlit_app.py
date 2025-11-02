import streamlit as st
import requests
import pandas as pd
import json # JSON処理をより明示的にするためにインポート

# 💡 システム命令の定義
# これがチャットボットの「人格」と「ルール」を定義します。
SYSTEM_INSTRUCTION = """
あなたは、工学部の学生向けの意見文専門のピアレビューアシスタントです。
あなたの役割は、学生が入力した文章に含まれる「工学の意見文として不適切な用語」「曖昧な表現」「論理の飛躍」を指摘することに限定されます。

以下のルールを厳守してください。

1.  **完全な添削や修正後の文章を提供してはいけません。**
2.  **指導的なトーンを維持し、指摘箇所について学生自身に考えさせるような質問やヒントを提供してください。**
3.  具体的にどの単語やフレーズが不適切か、またはなぜその用語が曖昧なのかを明確に指摘し、「なぜこの単語を使うのが適切ではないか考えよう」「この概念を工学分野でより専門的に表現する用語は何だろうか」といった質問を投げかけてください。
4.  出力は指摘形式（例: 箇条書き）で簡潔に行い、解説を加えてください。
"""

# API endpointとヘッダー
API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
HEADERS = {"Content-Type": "application/json"}
TIMEOUT = 30

# アプリのタイトルと説明
st.title("💡 工学部レポート チェッカー")
st.write("このアシスタントは、**手動入力**または**CSVファイルアップロード**された文章を読み、工学レポートとして不適切な用語や表現のみを指摘し、学生自身に修正させるためのヒントを提供します。")

# Streamlit Community CloudのSecretsからAPIキーを取得
gemini_api_key = st.secrets.get("GEMINI_API_KEY")

if not gemini_api_key:
    st.info("Streamlit Community CloudのSecretsに `GEMINI_API_KEY` を設定してください。", icon="🗝️")
else:
    # ユーザーがモデルを選択できるようにする
    model_name = st.selectbox(
        "使用する Gemini モデルを選択",
        (
            "gemini-2.5-flash", 
            "gemini-2.5-pro"
        ),
        index=0 # flashをデフォルトにする
    )

    # ----------------------------------------------------
    # CSVファイルアップロードセクション
    # ----------------------------------------------------
    uploaded_file = st.file_uploader("CSVファイルをアップロードしてください（B列の文章をチェックします）", type="csv")
    
    if uploaded_file:
        # 💡 修正: CSV処理全体をst.spinner()で囲む
        with st.spinner("CSVファイルの一括チェックを実行中..."):
            
            # CSVファイルの読み込みとエンコーディングの対応
            try:
                uploaded_file.seek(0) # ファイルポインタを先頭に戻す
                try:
                    # 1. Shift JISで試行（Windows環境で一般的な形式）
                    df = pd.read_csv(uploaded_file, encoding='shift_jis')
                    st.warning("ファイルをShift JISで読み込みました。")
                except UnicodeDecodeError:
                    # 2. Shift JISで失敗した場合、UTF-8で再試行（WebやMac環境で一般的）
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding='utf-8')
                    st.warning("ファイルをUTF-8で読み込みました。")
            except Exception as e:
                st.error(f"CSVファイルの読み込み中にエラーが発生しました。エンコーディングを確認してください: {e}")
                st.stop()
            
            # B列（インデックス1）の存在チェック
            if df.shape[1] < 2:
                 st.warning("アップロードされたCSVにはB列（インデックス1）が存在しません。")
                 st.stop()

            # --- 💡 C列の確保と初期化（結果の書き込み先） ---
            # df.shape[1] < 3 の場合は、C列(インデックス2)が存在しない
            if df.shape[1] < 3:
                new_column_name = 'Gemini指摘'
                # pandasのDataFrameに新しい列を挿入 (C列 = インデックス2)
                df.insert(loc=2, column=new_column_name, value=None)
            else:
                # 既にC列がある場合は、その列名を使用
                new_column_name = df.columns[2]
                
            st.info(f"評価結果はCSVの **'{new_column_name}' 列 (C列) の2行目以降** に反映されます。")
            
            texts_processed = 0
            results_container = st.container()

            # ヘッダー行 (index 0) をスキップして、データ行 (index 1 = B2以降) を処理
            # df.index[1:] でデータ行のインデックスを取得
            for index in df.index[1:]:
                # B列（インデックス1）の値を取得
                text_prompt = df.iloc[index, 1]
                
                # B列が有効なテキストである場合のみ処理
                if pd.notna(text_prompt) and isinstance(text_prompt, str) and text_prompt.strip():
                    texts_processed += 1
                    
                    results_container.markdown(f"#### 📄 文章 {index + 1} 行目 (B{index + 1}セル):")
                    results_container.text(text_prompt)

                    api_url = API_URL_TEMPLATE.format(model_name=model_name, api_key=gemini_api_key)

                    # APIペイロード (履歴なし)
                    data = {
                        "systemInstruction": {
                            "parts": [{"text": SYSTEM_INSTRUCTION}]
                        },
                        "contents": [{"role": "user", "parts": [{"text": text_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.5, 
                            "topP": 0.8
                        }
                    }

                    try:
                        response = requests.post(api_url, headers=HEADERS, json=data, timeout=TIMEOUT)
                        response.raise_for_status()
                        
                        result = response.json()
                        
                        gemini_reply = "API応答を解析できませんでした。"
                        if "candidates" in result and result["candidates"]:
                            candidate = result["candidates"][0]
                            if "content" in candidate and \
                               "parts" in candidate["content"] and \
                               candidate["content"]["parts"]:
                                
                                gemini_reply = candidate["content"]["parts"][0]["text"]
                            
                        # --- 💡 結果をDataFrameに書き込む (C列 = インデックス2) ---
                        df.iloc[index, 2] = gemini_reply 
                            
                        # 結果を表示
                        results_container.markdown(f"**指摘 ({model_name}):**")
                        results_container.markdown(gemini_reply)
                        results_container.markdown("---")
                    
                    except requests.exceptions.RequestException as e:
                        error_message = f"文章 {index + 1} 行目のAPIリクエストエラー: {e}"
                        results_container.error(error_message)
                        df.iloc[index, 2] = f"APIエラー: {e}" # エラーもC列に記録
                        results_container.markdown("---")
                    except Exception as e:
                        error_message = f"文章 {index + 1} 行目で予期せぬエラーが発生しました: {e}"
                        results_container.error(error_message)
                        df.iloc[index, 2] = f"予期せぬエラー: {e}" # エラーもC列に記録
                        results_container.markdown("---")

            if texts_processed > 0:
                st.success(f"CSVファイルの一括チェックが完了しました！合計 {texts_processed} 個の文章を処理しました。")
                
                # --- 💡 文字化け修正 (再修正): to_csv()の結果を直接バイトデータとして扱う ---
                # to_csvの結果はすでにエンコードされた文字列なので、さらに.encode('utf-8')すると二重エンコードになる
                # バイト列を取得するため io.StringIO と .getvalue().encode('utf-8') を使用するか、
                # pandas 1.0以降であれば .to_csv(..., encoding='utf-8-sig') はバイト列を返す。
                # しかし、ここではStreamlitが推奨する io.BytesIO を使ってより確実にバイト列を渡す。
                import io
                
                # io.StringIOを使って文字列として書き出し、それをエンコードする
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                
                # バイトデータとして準備
                csv_output = csv_buffer.getvalue().encode('utf-8-sig')


                st.download_button(
                    label="📝 結果をダウンロード (C列に指摘事項を追記)",
                    data=csv_output,
                    file_name='report_check_results.csv',
                    mime='text/csv',
                    help="ダウンロードしたCSVファイルをExcelなどで開くとC列に指摘事項が文字化けせず確認できます。"
                )
            else:
                st.info("B2以降のセルにチェックすべき有効な文章が見つかりませんでした。")

    
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

            api_url = API_URL_TEMPLATE.format(model_name=model_name, api_key=gemini_api_key)

            # チャットモード時のAPIペイロード (履歴を含む)
            data = {
                "systemInstruction": {
                    "parts": [{"text": SYSTEM_INSTRUCTION}]
                },
                "contents": gemini_messages,
                "generationConfig": {
                    "temperature": 0.5, 
                    "topP": 0.8
                }
            }

            try:
                # 💡 修正: st.spinner()を単独で使用
                with st.spinner(f"{model_name} が指摘を生成中..."):
                    response = requests.post(api_url, headers=HEADERS, json=data, timeout=TIMEOUT)
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
                        
                
                # スピナーブロックの外でメッセージを表示する
                with st.chat_message("assistant"):
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
