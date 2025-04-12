
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

no_results = "I couldn't find any relevant information in the database"

def execute_cypher(state: dict, graph) -> dict:
    records = graph.query(state.get("cypher_statement"))
    state["database_records"] = records if records else no_results
    state["next_action"] = "end"
    state["steps"].append("execute_cypher")
    return {
        "database_records": records if records else no_results,
        "next_action": "end",
        "steps": ["execute_cypher"],
    }

def generate_final_answer(state: dict, llm: ChatOpenAI, graph) -> dict:
    generate_final_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant who can analyse the json data and provide correct response to user queries."
            ),
            (
                "human",
                ("""Use the following results retrieved from neo4j database using the CYPHER query which has the SCHEMA to provide a succinct, definitive answer to the user's question. The results of query might be in json format.  Respond as if you are answering the question directly.

SCHEMA: {schema}
QUESTION: {question}
CYPHER: {cypher}
RESULTS: {results}

For the above question and results of query, reply to user question and provide all the important details to help user understand the answer.""")
            ),
        ]
    )
    generate_final_chain = generate_final_prompt | llm | StrOutputParser()
    logging.info(f"GRAPH EXECUTED RESULTS {state.get('database_records')}")

    final_answer = generate_final_chain.invoke(
        {
            "question": state.get("question"),
            "schema": graph.schema,
            "cypher": state.get("cypher_statement"),
            "results": state.get("database_records"),
        }
    )
    logging.info(f"Final Answer: {final_answer}")
    state["answer"] = final_answer
    state["steps"].append("generate_final_answer")
    return {"answer": final_answer, "steps": ["generate_final_answer"]}