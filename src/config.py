
import os
import logging
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()  

def get_graph() -> Neo4jGraph:
    graph = Neo4jGraph(
        url=os.environ["NEO4J_URI"],
        username=os.environ["NEO4J_USERNAME"],
        password=os.environ["NEO4J_PASSWORD"],
    )
    logging.info(f"GRAPH SCHEMA {graph.schema}")
    return graph

def get_llm() -> ChatOpenAI:
    # You can choose the model as needed.
    return ChatOpenAI(model="gpt-4o", temperature=0)
