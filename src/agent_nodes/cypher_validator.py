
import logging
from neo4j.exceptions import CypherSyntaxError
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic.v1 import BaseModel, Field
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_neo4j.chains.graph_qa.cypher_utils import CypherQueryCorrector, Schema

# Define a model for properties if needed
class Property(BaseModel):
    node_label: str = Field(..., description="Node label")
    property_key: str = Field(..., description="Property key")
    property_value: str = Field(..., description="Property value")

class ValidateCypherOutput(BaseModel):
    errors: Optional[List[str]] = Field(
        description="A list of syntax or semantical errors in the Cypher statement."
    )
    filters: Optional[List[Property]] = Field(
        description="A list of property-based filters applied in the Cypher statement."
    )

validate_cypher_system = """
You are a Cypher expert reviewing a statement written by a junior developer.
"""
validate_cypher_user = """You must check the following:
* Are there any syntax errors in the Cypher statement?
* Are there any missing or undefined variables in the Cypher statement?
* Are any node labels missing from the schema?
* Are any relationship types missing from the schema?
* Are any of the properties not included in the schema?
* Does the Cypher statement include enough information to answer the question?

Schema:
{schema}

The question is:
{question}

The Cypher statement is:
{cypher}

Make sure you don't make any mistakes!"""

validate_cypher_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", validate_cypher_system),
        ("human", validate_cypher_user),
    ]
)

def validate_cypher(state: dict, llm: ChatOpenAI, graph) -> dict:
    errors = []
    mapping_errors = []
    try:
        # Check the statement with an EXPLAIN call
        graph.query(f"EXPLAIN {state.get('cypher_statement')}")
    except CypherSyntaxError as e:
        logging.info(f"Query error {e.message}")
        errors.append(e.message)
    

    # Cypher query corrector is experimental
    corrector_schema = [
        Schema(el["start"], el["type"], el["end"])
        for el in graph.structured_schema.get("relationships")
    ]
    cypher_query_corrector = CypherQueryCorrector(corrector_schema)

    corrected_cypher = cypher_query_corrector(state.get("cypher_statement"))
    if not corrected_cypher:
        errors.append("The generated Cypher statement doesn't fit the graph schema")
    if not corrected_cypher == state.get("cypher_statement"):
        print("Relationship direction was corrected")
    # Validate with the LLM chain
    validate_cypher_chain = validate_cypher_prompt | llm.with_structured_output(ValidateCypherOutput)
    llm_output = validate_cypher_chain.invoke(
        {
            "question": state.get("question"),
            "schema": graph.schema,
            "cypher": state.get("cypher_statement"),
        }
    )
    logging.info(f"ERRORS so far {errors}")
    logging.info(f"cypher_statement {state.get('cypher_statement')}")
    logging.info(f"validate_cypher llm_output {llm_output}")
    if llm_output.errors:
        errors.extend(llm_output.errors)
    
    # if llm_output.filters:
        # for filter in llm_output.filters:
        #     # Do mapping only for string values
        #     if (
        #         not [
        #             prop
        #             for prop in graph.structured_schema["node_props"][
        #                 filter.node_label
        #             ]
        #             if prop["property"] == filter.property_key
        #         ][0]["type"]
        #         == "STRING"
        #     ):
        #         continue
        #     mapping = graph.query(
        #         f"MATCH (n:{filter.node_label}) WHERE toLower(n.`{filter.property_key}`) = toLower($value) RETURN 'yes' LIMIT 1",
        #         {"value": filter.property_value},
        #     )
        #     if not mapping:
        #         print(
        #             f"Missing value mapping for {filter.node_label} on property {filter.property_key} with value {filter.property_value}"
        #         )
        #         mapping_errors.append(
        #             f"Missing value mapping for {filter.node_label} on property {filter.property_key} with value {filter.property_value}"
        #         )

    if mapping_errors:
        next_action = "end"
    elif errors:
        next_action = "correct_cypher"
    else:
        next_action = "execute_cypher"
    
    state["next_action"] = next_action
    state["cypher_errors"] = errors
    state["steps"].append("validate_cypher")
    return {
        "next_action": next_action,
        "cypher_statement": corrected_cypher,
        "cypher_errors": errors,
        "steps": ["validate_cypher"],
    }

def correct_cypher(state: dict, llm: ChatOpenAI, graph) -> dict:
    correct_cypher_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                ("You are a Cypher expert reviewing a statement written by a junior developer. "
                 "You need to correct the Cypher statement based on the provided errors. No pre-amble."
                 "Do not wrap the response in any backticks or anything else. Respond with a Cypher statement only!")
            ),
            (
                "human",
                ("""Check for invalid syntax or semantics and return a corrected Cypher statement.

Schema:
{schema}

Note: Do not include any explanations or apologies in your responses.
Do not wrap the response in any backticks or anything else.
Respond with a Cypher statement only!

The question is:
{question}

The Cypher statement is:
{cypher}

The errors are:
{errors}

Corrected Cypher statement:""")
            ),
        ]
    )
    correct_cypher_chain = correct_cypher_prompt | llm | StrOutputParser()
    corrected_cypher = correct_cypher_chain.invoke(
        {
            "question": state.get("question"),
            "errors": state.get("cypher_errors"),
            "cypher": state.get("cypher_statement"),
            "schema": graph.schema,
        }
    )
    state["cypher_statement"] = corrected_cypher
    state["next_action"] = "validate_cypher"
    state["steps"].append("correct_cypher")
    
    return {
        "next_action": "validate_cypher",
        "cypher_statement": corrected_cypher,
        "steps": ["correct_cypher"],
    }

