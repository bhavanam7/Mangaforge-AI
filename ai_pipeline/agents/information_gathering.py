import sys
from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from prompts.agents_prompt import REFINEMENT_SYSTEM_PROMPT
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

def refine_enriched_context(current_context: str, user_feedback: str, model_name: str = "llama3.2:3b") -> str:
    """Refines existing enriched context string using user-provided feedback or additions."""
    llm = ChatOllama(model=model_name, temperature=0.1)

    combined_input = f"Current Scene Context:\n{current_context}\n\nUser Feedback/Enhancements:\n{user_feedback}"

    refined_response = llm.invoke([
        SystemMessage(content=REFINEMENT_SYSTEM_PROMPT),
        HumanMessage(content=combined_input)
    ])

    return refined_response.content.strip()