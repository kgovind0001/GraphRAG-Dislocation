
from pydantic.v1 import BaseModel, Field
from typing import Literal, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import logging

from typing_extensions import TypedDict

class InputState(TypedDict):
    question: str

class OverallState(TypedDict):
    question: str
    next_action: str
    cypher_statement: str
    cypher_errors: List[str]
    database_records: List[dict]
    steps: List[str]

class GuardrailsOutput(BaseModel):
    decision: Literal["microstructure", "end"] = Field(
        description="Decision on whether the question is related to microstructure"
    )

guardrails_system = """
As an intelligent assistant, your primary objective is to decide whether a given question is related to microstructure/dislocations/pileups or not. 
If the question is related to microstructure/dislocations/pileups , output "microstructure". Otherwise, output "end".
To make this decision, assess the content of the question and determine if it refers to any microstructure, dislocations, grain boundary or related topics. Provide only the specified output: "microstructure" or "end".
"""

guardrails_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", guardrails_system),
        ("human", "{question}"),
    ]
)



def guardrails(state: InputState, llm: ChatOpenAI) -> OverallState:
    guardrails_chain = guardrails_prompt | llm.with_structured_output(schema=GuardrailsOutput)
    guardrails_output = guardrails_chain.invoke({"question": state.get("question")})
    logging.info(f"guardrails_output {guardrails_output}")
    database_records = None
    if guardrails_output.decision == "end":
        database_records = "This questions is not about microstructure or related topics. Therefore I cannot answer this question."
    return {
        "next_action": guardrails_output.decision,
        "database_records": database_records,
        "steps": ["guardrail"],
    }
