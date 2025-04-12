

from functools import partial
from typing import Literal
from typing import Annotated, List
from typing_extensions import TypedDict

import logging
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, START, StateGraph
from langchain_openai import ChatOpenAI

from src.config import get_graph, get_llm, logger
from src.agent_nodes.guardrails import guardrails, InputState, OverallState
from src.agent_nodes.cypher_generator import generate_cypher
from src.agent_nodes.cypher_validator import validate_cypher, correct_cypher
from src.executor import execute_cypher, generate_final_answer



def guardrails_condition(state: OverallState
) -> Literal["generate_cypher", "generate_final_answer"]:
    # Decide next branch based on guardrails output
    if state.get("next_action") == "end":
        return "generate_final_answer"
    elif state.get("next_action") == "microstructure":
        return "generate_cypher"

def validate_cypher_condition(state: OverallState
) -> Literal["generate_final_answer", "correct_cypher", "execute_cypher"]:
    if state.get("next_action") == "end":
        return "generate_final_answer"
    elif state.get("next_action") == "correct_cypher":
        return "correct_cypher"
    elif state.get("next_action") == "execute_cypher":
        return "execute_cypher"


class OutputState(TypedDict):
    answer: str
    steps: List[str]
    cypher_statement: str



def build_pipeline() -> StateGraph:
    llm = get_llm()
    graph = get_graph()
    
    logger.info(f"Setting langgraph.....")
    langgraph = StateGraph(OverallState, input=InputState, output=OutputState)
    # Build a state graph (pipeline) instance.
    langgraph.add_node("guardrails", partial(guardrails, llm=llm))
    langgraph.add_node("generate_cypher", partial(generate_cypher, llm=llm, graph=graph))
    langgraph.add_node("validate_cypher", partial(validate_cypher, llm=llm, graph=graph))
    langgraph.add_node("correct_cypher", partial(correct_cypher, llm=llm, graph=graph))
    langgraph.add_node("execute_cypher", partial(execute_cypher, graph=graph))
    langgraph.add_node("generate_final_answer", partial(generate_final_answer, llm=llm, graph=graph))

    
    langgraph.add_edge(START, "guardrails")
    langgraph.add_conditional_edges("guardrails", guardrails_condition)
    langgraph.add_edge("generate_cypher", "validate_cypher")
    langgraph.add_conditional_edges("validate_cypher", validate_cypher_condition)
    langgraph.add_edge("execute_cypher", "generate_final_answer")
    langgraph.add_edge("correct_cypher", "validate_cypher")
    langgraph.add_edge("generate_final_answer", END)
    return langgraph.compile()

if __name__ == "__main__":
    pipeline = build_pipeline()
    # Example usage; you can change the question
    result = pipeline.invoke({"question": "Highest Number of Dislocations in a Pileup"})
    print(100*"-")
    print(100*"-")
    print(100*"-")
    print(result)
