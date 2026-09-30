from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_ollama import ChatOllama
from models.model import TurnExtractionOutput
from prompts.llm_prompt import TURN_EXTRACTION_OUTPUT_PROMPT 


def process_manga_turn(user_message: str, model_name: str = "llama3.2:3b") -> TurnExtractionOutput:
    llm = ChatOllama(
        model=model_name,
        temperature=0.6,
    )

    structured_llm = llm.with_structured_output(TurnExtractionOutput)

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=TURN_EXTRACTION_OUTPUT_PROMPT),
        HumanMessagePromptTemplate.from_template("{user_input}")
    ])

    chain = prompt | structured_llm

    result: TurnExtractionOutput = chain.invoke({"user_input": user_message})
    return result