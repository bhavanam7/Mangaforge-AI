
import os
import torch
import laya

MODEL_DIR = "/home/cis/Desktop/Swayam/Projects/Manga/ai_pipeline/ai_models/laya_model"

if not os.path.isdir(MODEL_DIR):
    raise FileNotFoundError(f"Model path not found: {MODEL_DIR}")

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading Laya Agent on {device}...")
agent = laya.load(MODEL_DIR, device=device)


def evaluate_initial_prompt(prompt: str) -> dict:
    """Evaluate whether the initial prompt is sufficient for story generation."""
    state = {"document": prompt}
    questions = {
        "sufficiency": {
            "type": "choice",
            "instructions": (
                "Determine whether this prompt contains enough information "
                "to serve as a complete story premise."
            ),
            "criteria": {
                "sufficient": (
                    "Contains a specific character, setting, situation, "
                    "conflict, goal, plot hook, or enough narrative context."
                ),
                "insufficient": (
                    "Too short, vague, or missing core narrative elements, "
                    "such as 'write a story' or 'tell me a tale'."
                ),
            },
        }
    }

    result = agent.predict(state, questions)
    answer = result["answers"]["sufficiency"]

    return {
        "is_sufficient": answer["choice"] == "sufficient",
        "confidence": answer["answer_confidence"],
        "state": result.get("state", state),
    }


def classify_enhancement(prompt: str, story_state: dict) -> dict:
    """Classify an enhancement using the current story state as context."""
    state = {**story_state, "document": prompt}
    questions = {
        "category": {
            "type": "choice",
            "instructions": (
                "Classify the enhancement according to the primary aspect "
                "of the story it modifies. Use the existing story state "
                "as context."
            ),
            "criteria": {
                "character": (
                    "Modifies a character's personality, appearance, "
                    "emotions, motivation, flaws, abilities, relationships, "
                    "or backstory."
                ),
                "background": (
                    "Modifies the world, setting, environment, scenery, "
                    "atmosphere, lore, history, culture, locations, "
                    "or world rules."
                ),
                "scene_and_dialogue": (
                    "Modifies a specific scene or interaction, including "
                    "dialogue, actions, pacing, conversations, or action "
                    "sequences."
                ),
                "story": (
                    "Modifies the overall story, including premise, plot, "
                    "conflict, objective, theme, narrative direction, "
                    "major events, structure, or ending."
                ),
            },
        }
    }

    result = agent.predict(state, questions)
    answer = result["answers"]["category"]

    category_map = {
        "character": "character_enhancement",
        "background": "background_enhancement",
        "scene_and_dialogue": "scene_and_dialogue_enhancement",
        "story": "story_enhancement",
    }

    return {
        "category": category_map.get(answer["choice"], answer["choice"]),
        "confidence": answer["answer_confidence"],
        "state": result.get("state", state),
    }


def print_state(state: dict) -> None:
    """Display the current story state."""
    print("\n--- Current Story State ---")
    for key, value in state.items():
        print(f"{key}: {value}")
    print("-" * 50)


def get_initial_story_state() -> dict:
    """Continuously request an initial prompt until it is sufficient."""
    while True:
        prompt = input("\nEnter your initial story prompt: ").strip()

        if not prompt:
            print("Prompt cannot be empty.")
            continue

        print("Evaluating initial prompt with Laya...")
        result = evaluate_initial_prompt(prompt)

        if result["is_sufficient"]:
            print(
                f"✅ SUFFICIENT "
                f"(Confidence: {result['confidence']:.2%})"
            )
            state = result["state"]
            state["document"] = prompt
            return state

        print(
            f"❌ INSUFFICIENT "
            f"(Confidence: {result['confidence']:.2%})"
        )
        print("Add details such as:")
        print("  - Main character")
        print("  - Setting/time")
        print("  - Main conflict or goal")


def run_pipeline() -> None:
    """Run the interactive story enhancement pipeline."""
    print("\n" + "=" * 60)
    print("       STORY PROMPT EVALUATOR & CLASSIFIER")
    print("=" * 60)

    story_state = get_initial_story_state()

    print("\nPrompt accepted. Story enhancement phase started.")
    print("Commands: 'state' to view state | 'exit' to quit")
    print("-" * 60)

    while True:
        prompt = input("\nEnter an enhancement prompt: ").strip()

        if prompt.lower() in {"exit", "quit"}:
            print("Exiting pipeline. Goodbye!")
            break

        if prompt.lower() == "state":
            print_state(story_state)
            continue

        if not prompt:
            continue

        result = classify_enhancement(prompt, story_state)
        story_state = result["state"]

        print("\n--- Prediction ---")
        print(f"Prompt:     {prompt}")
        print(f"Category:   {result['category']}")
        print(f"Confidence: {result['confidence']:.2%}")

        print_state(story_state)


if __name__ == "__main__":
    run_pipeline()

