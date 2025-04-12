
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_neo4j import Neo4jVector
from langchain_openai import OpenAIEmbeddings

def get_example_selector():
    examples = [
        {
            "question": "What are the microstructures which has total number of dislocations less than 10 ?",
            "query": "MATCH (m:Microstructure)-[:HAS_PILEUP]->(:Pileup)-[:CONTAINS]->(d:Dislocation) WITH m, count(d) AS totalDislocations WHERE totalDislocations < 10 RETURN m",
        },
        {
            "question": "For micostructure with ms_200, find pileup with direction greater than 0.1 radians ? ",
            "query": "MATCH (m:Microstructure {id: 'ms_200'})-[:HAS_PILEUP]->(p:Pileup) WHERE p.direction > 0.1 RETURN p",
        },
        {
            "question": "How many microstructures have no associated pileups?", 
            "query": "MATCH (m:Microstructure) WHERE NOT (m)-[:HAS_PILEUP]->(:Pileup) RETURN m"
        },
        {
            "question": "Are there microstructures whose pileups' directions change significantly (for example, having high variance in direction)?", 
            "query": """
MATCH (ms:Microstructure)-[:HAS_PILEUP]->(p:Pileup)
WITH ms, collect(p.direction) AS directions
WHERE size(directions) > 1
WITH ms, directions, reduce(total = 0.0, d in directions | total + d) / size(directions) AS mean
WITH ms, mean, directions, [d IN directions | (d - mean) * (d - mean)] AS squaredDiffs
WITH ms, sqrt(reduce(total = 0.0, s in squaredDiffs | total + s) / size(squaredDiffs)) AS stDev
WHERE stDev > 10.0
RETURN ms, stDev
ORDER BY stDev DESC
"""
        }
    ]
    return SemanticSimilarityExampleSelector.from_examples(
        examples, OpenAIEmbeddings(), Neo4jVector, k=5, input_keys=["question"]
    )

def generate_cypher(state: dict, llm: ChatOpenAI, graph) -> dict:
    from operator import add  # if you need it
    NL = "\n"
    example_selector = get_example_selector()
    fewshot_examples = (NL * 2).join(
        [
            f"Question: {el['question']}{NL}Cypher:{el['query']}"
            for el in example_selector.select_examples({"question": state.get("question")})
        ]
    )
    text2cypher_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                ("Given an input question, convert it to a Cypher query. No pre-amble."
                 "Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!")
            ),
            (
                "human",
                ("""You are a Neo4j expert. Given an input question, create a syntactically correct Cypher query to run.
Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!
Here is the schema information
{schema}

Below are a number of examples of questions and their corresponding Cypher queries.

{fewshot_examples}

User input: {question}
Cypher query:""")
            ),
        ]
    )
    from langchain_core.output_parsers import StrOutputParser
    text2cypher_chain = text2cypher_prompt | llm | StrOutputParser()

    logging.info("Generating cypher: ...")
    generated_cypher = text2cypher_chain.invoke(
        {
            "question": state.get("question"),
            "fewshot_examples": fewshot_examples,
            "schema": graph.schema,
        }
    )
    logging.info(f"Generated cypher: {generated_cypher}")

    state["cypher_statement"] = generated_cypher
    state["steps"].append("generate_cypher")
    return {"cypher_statement": generated_cypher, "steps": ["generate_cypher"]}

