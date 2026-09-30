from agents.enhancement_scene import enhance_scene
from agents.enhancement_scene import enhance_background
import sys
from pathlib import Path

PROJECT_ROOT = Path("/home/cis/Desktop/Swayam/Projects/Manga")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents.information_gathering import information_gathering, refine_enriched_context
from agents.turn_extraction_output import process_manga_turn
from agents.enhancement_scene import enhancement_character

if __name__ == "__main__":
    user_prompt = input("Enter manga turn: ")

    # Step 1: Interactive Context Gathering
    enriched_context = information_gathering(user_prompt)

    # Step 2: Context Refinement Loop
    while True:
        print("\n--- Current Enriched Context ---")
        print(enriched_context)

        user_choice = (
            input("\nDo you want to add/modify anything in this context? (yes/no): ")
            .strip()
            .lower()
        )
        if user_choice in ["yes", "y"]:
            feedback = input("Enter enhancements/changes: ")
            enriched_context = refine_enriched_context(enriched_context, feedback)
        elif user_choice in ["no", "n"]:
            break
        else:
            print("Invalid input. Please try again.")

    parsed_output = process_manga_turn(enriched_context)
    print("\n--- Parsed Output ---")
    print(parsed_output.model_dump_json(indent=2))

    parsed_output = enhancement_character(parsed_output)

    # Step 5: Final Output
    # print("\n--- Final Structured Output ---")
    # print(parsed_output.model_dump_json(indent=2))

    parsed_output = enhance_background(parsed_output)

    # Step 6: Scene State Review & Enhancement
    parsed_output = enhance_scene(parsed_output)

    # Step 7: Final Output
    print("\n--- Final Structured Output ---")
    print(parsed_output.model_dump_json(indent=2))
