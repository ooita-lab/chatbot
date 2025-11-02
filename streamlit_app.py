import streamlit as st
import google.generativeai as genai

# タイトルと説明
st.title("💬 Chatbot")
st.write(
    "Google Geminiモデルを使ったシンプルなチャットボットです。"
    "利用にはGemini APIキーが必要です。APIキーは [こちら](https://ai.google.dev/gemini-api/docs/api-key) から取得できます。"
)

# Gemini APIキー入力欄
gemini_api_key = st.text_input("Gemini API Key", type="password")
if not gemini_api_key:
    st.info("APIキーを入力してください。", icon="🗝️")
else:
    # Geminiクライアントの設定
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")

    # チャット履歴の保存
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 履歴の表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザー入力欄
    if prompt := st.chat_input("メッセージを入力してください"):
        # 履歴へ追加＆表示
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Gemini API用の履歴変換
        history = []
        for m in st.session_state.messages:
            if m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            else:
                history.append({"role": "model", "parts": [m["content"]]})

        # Geminiへリクエスト
        response = model.generate_content(history)

        # レスポンス本文抽出
        output = response.text if hasattr(response, "text") else str(response)
        with st.chat_message("assistant"):
            st.markdown(output)
        st.session_state.messages.append({"role": "assistant", "content": output})
