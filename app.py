import streamlit as st
from dotenv import load_dotenv
from src.llm_query import build_pipeline
from src.config import logger
load_dotenv()

st.set_page_config(page_title="Dislocation Microstructure Query", layout="centered")

st.markdown("""
    <style>
    /* Chat message container */
    .chat-message {
        padding: 12px 20px;
        border-radius: 12px;
        margin-bottom: 10px;
        max-width: 90%;
        line-height: 1.6;
    }
    .chat-message.user {
        background-color: #e0f7fa;
        align-self: flex-end;
        margin-left: auto;
        font-weight: 500;
    }
    .chat-message.assistant {
        background-color: #f1f8e9;
        border-left: 4px solid #8bc34a;
        margin-right: auto;
    }

    .header {
        border-bottom: 2px solid #ddd;
        padding-bottom: 8px;
        margin-bottom: 20px;
    }

    .instructions {
        background-color: #f9f9f9;
        border-left: 5px solid #2196F3;
        padding: 16px;
        border-radius: 10px;
        margin-bottom: 20px;
    }

    </style>
""", unsafe_allow_html=True)

# Place the network visualization in the sidebar.
with st.sidebar:
    st.markdown("<h1 style='text-align: center; font-size: 30px;'>Microstructure Graph</h1>", unsafe_allow_html=True)
    try:
        with open('assets/network.html', 'r', encoding='utf-8') as html_file:
            network_html = html_file.read()
        st.components.v1.html(network_html, height=512, scrolling=False)
    except Exception as e:
        st.error("Network visualization not available. Please verify that 'assets/network.html' exists.")
    st.markdown("</div>", unsafe_allow_html=True)

# Title and intro
st.markdown("<h1 class='header'>🔗 Dislocation Microstructure GraphRAG Assistant</h1>", unsafe_allow_html=True)
st.markdown("""
<div class="instructions">
    <strong>Welcome!</strong> Ask anything about dislocation microstructure dataset. You may not ask any followup question. For example:
    <ul>
        <li>Find highest Number of Dislocations in a Pileup.</li>
        <li>How many dislocation microstructure we have in the dataset. </li>
        <li>Find the microstructure with the largest number of pileup.</li>
    </ul>
    🤖 This assistant combines <strong>graph knowledge</strong> and <strong>AI reasoning</strong> to get smart results!
</div>
""", unsafe_allow_html=True)

if "assistant" not in st.session_state:
    st.session_state.assistant =  build_pipeline()
    
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    css_class = f"chat-message {role}"
    st.markdown(f"<div class='{css_class}'>{content}</div>", unsafe_allow_html=True)


if prompt := st.chat_input("Ask your microstructure query question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.markdown(f"<div class='chat-message user'>{prompt}</div>", unsafe_allow_html=True)

    for m in st.session_state.messages:
        print(f"MESSAGES {m}")

    try:
        with st.spinner("Analyzing your query..."):
            logger.info(f"User Request: {prompt}")
            langgraph_response = st.session_state.assistant.invoke({"question": f"{prompt}"})
            logger.info(f"Langgraph Response: {langgraph_response}")
            assistant_answer= langgraph_response["answer"]
            st.markdown(f"<div class='chat-message assistant'>{assistant_answer}</div>", unsafe_allow_html=True)

        st.session_state.messages.append({"role": "assistant", "content": assistant_answer})
    except Exception as ex:
        logger.error(f"Got error processing request {ex}") 
        request_not_processed = "Could not process the request, please try later...."
        st.markdown(f"<div class='chat-message assistant'>{request_not_processed}</div>", unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": request_not_processed})