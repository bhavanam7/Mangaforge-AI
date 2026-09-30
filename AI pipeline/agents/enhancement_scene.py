from prompts.llm_prompt import SCENE_SUMMARY_SYSTEM_PROMPT
from prompts.llm_prompt import SCENE_ENHANCEMENT_SYSTEM_PROMPT
from models.model import SceneState
from prompts.llm_prompt import BACKGROUND_SUMMARY_SYSTEM_PROMPT
from models.model import BackgroundState
from prompts.llm_prompt import BACKGROUND_ENHANCEMENT_SYSTEM_PROMPT
import sys
from pathlib import Path

PROJECT_ROOT = Path("/home/cis/Desktop/Swayam/Projects/Manga")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from models.model import CharacterSceneInfo, TurnExtractionOutput
from prompts.llm_prompt import (
    CHARACTER_ENHANCEMENT_SYSTEM_PROMPT,
    CHARACTER_SUMMARY_SYSTEM_PROMPT,
)


def generate_character_paragraph_summary(
    char_info: CharacterSceneInfo, llm: ChatOllama
) -> str:
    """Uses LLM to summarize CharacterSceneInfo into a single readable paragraph."""
    prompt_payload = f"CHARACTER DATA:\n{char_info.model_dump_json(indent=2)}"

    response = llm.invoke(
        [
            SystemMessage(content=CHARACTER_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=prompt_payload),
        ]
    )

    return response.content.strip()


def enhancement_character(
    parsed_output: TurnExtractionOutput, model_name: str = "llama3.2:3b"
) -> TurnExtractionOutput:
    """Summarizes character info into a narrative paragraph and updates CharacterSceneInfo based on user feedback."""
    if not parsed_output.characters:
        print("\nNo characters found in the extracted scene to enhance.")
        return parsed_output

    llm = ChatOllama(model=model_name, temperature=0.1)
    structured_llm = llm.with_structured_output(CharacterSceneInfo)

    print("\n" + "=" * 60)
    print("         CHARACTER SCENE REVIEW & ENHANCEMENT         ")
    print("=" * 60)

    for idx, char_info in enumerate(parsed_output.characters):
        canon = char_info.canon

        # 1. Generate narrative paragraph summary using LLM
        summary_paragraph = generate_character_paragraph_summary(char_info, llm)

        # 2. Display formatted character summary
        print(f"\nCharacter ID :- {canon.id}")
        print(f"Character Name :- {canon.name or 'N/A'}")
        print(f"Character Summary :- {summary_paragraph}\n")

        # 3. Prompt user for updates
        user_choice = (
            input(
                f"Do you want to update/enhance '{canon.name or canon.id}'? (yes/no): "
            )
            .strip()
            .lower()
        )

        if user_choice in ["yes", "y"]:
            user_feedback = input(
                f"Enter changes/enhancements for {canon.name or canon.id}: "
            ).strip()

            prompt_payload = (
                f"PREVIOUS CHARACTER DATA:\n{char_info.model_dump_json(indent=2)}\n\n"
                f"USER ENHANCEMENT FEEDBACK:\n{user_feedback}"
            )

            # 4. LLM generates updated CharacterSceneInfo merging old context + user feedback
            updated_char_info: CharacterSceneInfo = structured_llm.invoke(
                [
                    SystemMessage(content=CHARACTER_ENHANCEMENT_SYSTEM_PROMPT),
                    HumanMessage(content=prompt_payload),
                ]
            )

            # 5. Sync permanent physical changes to canon array if flagged
            if (
                updated_char_info.state.causes_permanent_canon_change
                and updated_char_info.state.permanent_change_description
            ):
                desc = updated_char_info.state.permanent_change_description
                if desc not in updated_char_info.canon.permanent_physical_changes:
                    updated_char_info.canon.permanent_physical_changes.append(desc)

            # 6. Replace character info in parsed output
            parsed_output.characters[idx] = updated_char_info
            print(f"✓ Character '{canon.name or canon.id}' successfully updated!")
        elif user_choice in ["no", "n"]:
            continue
        else:
            print("Invalid input. Please try again.")

    return parsed_output


def generate_background_paragraph_summary(
    bg_info: BackgroundState, llm: ChatOllama
) -> str:
    """Uses LLM to summarize BackgroundInfo into a single narrative paragraph."""
    prompt_payload = f"BACKGROUND DATA:\n{bg_info.model_dump_json(indent=2)}"

    response = llm.invoke(
        [
            SystemMessage(content=BACKGROUND_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=prompt_payload),
        ]
    )

    return response.content.strip()


def enhance_background(
    parsed_output: TurnExtractionOutput, model_name: str = "llama3.2:3b"
) -> TurnExtractionOutput:
    """Summarizes background info into a narrative paragraph and updates BackgroundInfo based on user feedback."""
    if not parsed_output.background:
        print("\nNo background info found in the extracted scene to enhance.")
        return parsed_output

    llm = ChatOllama(model=model_name, temperature=0.1)
    structured_llm = llm.with_structured_output(BackgroundState)

    print("\n" + "=" * 60)
    print("         BACKGROUND SCENE REVIEW & ENHANCEMENT         ")
    print("=" * 60)

    bg_info = parsed_output.background

    # 1. Generate narrative paragraph summary using LLM
    summary_paragraph = generate_background_paragraph_summary(bg_info, llm)

    # 2. Display formatted background summary
    print(f"\nLocation :- {bg_info.location or 'N/A'}")
    print(f"Time of Day :- {bg_info.time_of_day or 'N/A'}")
    print(f"Background Summary :- {summary_paragraph}\n")

    # 3. Prompt user for updates
    user_choice = (
        input("Do you want to update/enhance the background? (yes/no): ")
        .strip()
        .lower()
    )

    if user_choice in ["yes", "y"]:
        user_feedback = input("Enter changes/enhancements for the background: ").strip()

        prompt_payload = (
            f"PREVIOUS BACKGROUND DATA:\n{bg_info.model_dump_json(indent=2)}\n\n"
            f"USER ENHANCEMENT FEEDBACK:\n{user_feedback}"
        )

        # 4. LLM generates updated BackgroundInfo merging old context + user feedback
        updated_bg_info: BackgroundState = structured_llm.invoke(
            [
                SystemMessage(content=BACKGROUND_ENHANCEMENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt_payload),
            ]
        )

        # 5. Save updated background in parsed output
        parsed_output.background = updated_bg_info
        print("✓ Background successfully updated!")

    return parsed_output


def generate_scene_paragraph_summary(scene_state: SceneState, llm: ChatOllama) -> str:
    """Uses LLM to summarize SceneState (summary + dialogues) into a narrative paragraph."""
    prompt_payload = f"SCENE STATE DATA:\n{scene_state.model_dump_json(indent=2)}"

    response = llm.invoke(
        [
            SystemMessage(content=SCENE_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=prompt_payload),
        ]
    )

    return response.content.strip()


def enhance_scene(
    parsed_output: TurnExtractionOutput, model_name: str = "llama3.2:3b"
) -> TurnExtractionOutput:
    """Summarizes scene state into a narrative paragraph and updates SceneState based on user feedback."""
    if not parsed_output.scene:
        print("\nNo scene state found in the extracted scene to enhance.")
        return parsed_output

    llm = ChatOllama(model=model_name, temperature=0.1)
    structured_llm = llm.with_structured_output(SceneState)

    print("\n" + "=" * 60)
    print("           SCENE STATE REVIEW & ENHANCEMENT           ")
    print("=" * 60)

    scene_state = parsed_output.scene

    # 1. Generate narrative paragraph summary using LLM
    summary_paragraph = generate_scene_paragraph_summary(scene_state, llm)

    # 2. Display formatted scene state summary and dialogue lines
    print(f"\nScene Summary :- {summary_paragraph}")
    if scene_state.dialogues:
        print("Dialogues :-")
        for d in scene_state.dialogues:
            print(f'  • {d.character_id_or_name}: "{d.line}"')
    else:
        print("Dialogues :- None")
    print()

    # 3. Prompt user for updates
    user_choice = (
        input("Do you want to update/enhance the scene state? (yes/no): ")
        .strip()
        .lower()
    )

    if user_choice in ["yes", "y"]:
        user_feedback = input(
            "Enter changes/enhancements for the scene state: "
        ).strip()

        prompt_payload = (
            f"PREVIOUS SCENE STATE DATA:\n{scene_state.model_dump_json(indent=2)}\n\n"
            f"USER ENHANCEMENT FEEDBACK:\n{user_feedback}"
        )

        # 4. LLM generates updated SceneState merging old context + user feedback
        updated_scene_state: SceneState = structured_llm.invoke(
            [
                SystemMessage(content=SCENE_ENHANCEMENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt_payload),
            ]
        )

        # 5. Save updated scene state in parsed output
        parsed_output.scene = updated_scene_state
        print("✓ Scene State successfully updated!")

    return parsed_output
