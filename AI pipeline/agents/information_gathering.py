from prompts.llm_prompt import REFINEMENT_SYSTEM_PROMPT
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from prompts.llm_prompt import ANALYSIS_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT


def information_gathering(initial_prompt: str, model_name: str = "llama3.2:3b") -> str:
    """Interactively gathers missing current-scene context and synthesizes it without time-skips."""
    llm = ChatOllama(model=model_name, temperature=0.1)

    # Step 1: Analyze prompt for current-scene missing context
    questions_response = llm.invoke([
        SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=initial_prompt)
    ])

    print("\n--- Additional Details Needed ---")
    print(questions_response.content)
    user_additional_info = input("\nProvide event/setting details: ")

    # Step 2: Synthesize strictly for the current scene
    combined_input = f"Initial Prompt: {initial_prompt}\n Question asked by LLM: {questions_response.content}\n User Answers: {user_additional_info}"
    
    enriched_summary = llm.invoke([
        SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=combined_input)
    ])
    return enriched_summary.content.strip()



def refine_enriched_context(current_context: str, user_feedback: str, model_name: str = "llama3.2:3b") -> str:
    """Refines existing enriched context string using user-provided feedback or additions."""
    llm = ChatOllama(model=model_name, temperature=0.1)

    combined_input = f"Current Scene Context:\n{current_context}\n\nUser Feedback/Enhancements:\n{user_feedback}"

    refined_response = llm.invoke([
        SystemMessage(content=REFINEMENT_SYSTEM_PROMPT),
        HumanMessage(content=combined_input)
    ])

    return refined_response.content.strip()