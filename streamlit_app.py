import streamlit as st
import google.generativeai as genai

# Show title and description.
st.title("💬 Chatbot")
st.write(
    "This is a simple chatbot that uses Google's Gemini model to generate responses. "
    "To use this app, you need to provide a Gemini API key, which you can get [here](https://ai.google.dev/gemini-api/docs/api-key). "
    "You can also learn how to build this app step by step by [following our tutorial](https://docs.streamlit.io/develop/tutorials/llms/build-conversational-apps)."
)

# Ask user for their Gemini API key via `st.text_input`.
gemini_api_key = st.text_input("Gemini API Key", type="password")
if not gemini_api_key:
    st.info("Please add your Gemini API key to continue.", icon="🗝️")
else:
    # Configure Gemini client
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-pro")

    # Create a session state variable to store the chat messages.
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display the existing chat messages via `st.chat_message`.
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Create a chat input field to allow the user to enter a message.
    if prompt := st.chat_input("What is up?"):
        # Store and display the current prompt.
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # GeminiのAPIはOpenAIとは異なり、roleの指定をサポートしませんが、履歴としてuser/assistantプロンプトを送ることはできます。
        history = []
        for m in st.session_state.messages:
            if m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            else:
                history.append({"role": "model", "parts": [m["content"]]})

        # Geminiモデルに履歴を渡して応答を生成
        response = model.generate_content(history)

        # レスポンスの本文部分を抽出
        output = response.text if hasattr(response, "text") else str(response)

        with st.chat_message("assistant"):
            st.markdown(output)
        st.session_state.messages.append({"role": "assistant", "content": output})
