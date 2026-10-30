import os
from enum import Enum
from typing import Dict, Any, Union
import torch
import laya
import math

# Path configuration
MODEL_DIR = "/home/cis/Desktop/Swayam/Projects/Manga/Mangaforge-AI/ai_pipeline/ai_models/laya_model"


class PipelineStage(str, Enum):
    """Pipeline stages for the story generation AI."""
    PROMPT_EVAL = "PROMPT_EVAL"
    ENRICHED_CONTENT = "ENRICHED_CONTENT"
    CHARACTER_ENHANCEMENT = "CHARACTER_ENHANCEMENT"
    BACKGROUND_ENHANCEMENT = "BACKGROUND_ENHANCEMENT"
    SCENE_DIALOGUE_ENHANCEMENT = "SCENE_DIALOGUE_ENHANCEMENT"
    FINALIZED = "FINALIZED"


class LayaAgentEvaluator:
    """Agent class to load model once and evaluate prompt efficiency across pipeline stages."""
    
    def __init__(self, model_dir: str = MODEL_DIR):
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(f"Model path not found: {model_dir}")
            
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading Laya Agent on {self.device}...")
        self.agent = laya.load(model_dir, device=self.device)



    def evaluate_prompt(
        self,
        user_content: str,
        stage: Union[PipelineStage, str]
    ) -> Dict[str, Any]:
        """
        Evaluates whether a user prompt is sufficient for story generation.

        Classification:
            Sufficient probability > 70%: sufficient
            Sufficient probability <= 70%: insufficient

        Laya response format:
            response["answers"]["sufficiency"]["probabilities"]
        """

        # Validate pipeline stage
        if isinstance(stage, str):
            try:
                stage_enum = PipelineStage(stage)
            except ValueError:
                valid_stages = [s.value for s in PipelineStage]
                raise ValueError(
                    f"Invalid stage '{stage}'. Must be one of: {valid_stages}"
                )
        elif isinstance(stage, PipelineStage):
            stage_enum = stage
        else:
            raise TypeError(
                "stage must be a PipelineStage or a valid string."
            )

        # Handle empty prompts
        cleaned_content = user_content.strip()

        if not cleaned_content:
            return {
                "is_efficient": False,
                "stage": stage_enum.value,
                "sufficiency": "insufficient",
                "confidence_score": 0.0,
                "raw_response": {
                    "reason": "User prompt is empty."
                }
            }

        # Prepare input for Laya
        state = {
            "document": cleaned_content
        }

        # Define prompt evaluation criteria
        questions = {
            "sufficiency": {
                "type": "choice",
                "instructions": (
                    f"Determine whether this prompt contains enough context and narrative substance "
                ),
                "criteria": {
                    "sufficient": (
                        "Contains a specific character, setting, situation, conflict, goal, plot hook, "
                        "or actionable context suitable for short story generation or continuation."
                    ),
                    "insufficient": (
                        "Too short, vague, ambiguous, or missing core narrative elements, "
                        "such as generic commands like 'write a story' or 'tell me a tale'."
                    ),
                },
            }
        }

        # Run Laya agent
        with torch.no_grad():
            response = self.agent.predict(
                state=state,
                questions=questions
            )

        # Default safely if probabilities are missing or invalid
        sufficient_probability = 0.0
        insufficient_probability = 0.0

        if isinstance(response, dict):
            answers = response.get("answers", {})
            sufficiency_data = answers.get("sufficiency", {})

            if isinstance(sufficiency_data, dict):
                probability_data = sufficiency_data.get(
                    "probabilities", {}
                )

                if isinstance(probability_data, dict):
                    try:
                        sufficient_probability = float(
                            probability_data.get("sufficient", 0.0)
                        )
                        insufficient_probability = float(
                            probability_data.get("insufficient", 0.0)
                        )

                        # Validate probabilities
                        valid_probabilities = (
                            math.isfinite(sufficient_probability)
                            and math.isfinite(insufficient_probability)
                            and 0.0 <= sufficient_probability <= 1.0
                            and 0.0 <= insufficient_probability <= 1.0
                        )

                        if not valid_probabilities:
                            sufficient_probability = 0.0
                            insufficient_probability = 0.0

                    except (TypeError, ValueError):
                        sufficient_probability = 0.0
                        insufficient_probability = 0.0

        # Convert probabilities to percentages
        sufficient_score = sufficient_probability * 100
        insufficient_score = insufficient_probability * 100

        # Classification threshold: strictly greater than 70%
        is_efficient = sufficient_score > 40.0

        sufficiency_result = (
            "sufficient"
            if is_efficient
            else "insufficient"
        )

        # Update stage based on classification
        result_stage = (
            "ENRICHED_CONTENT"
            if is_efficient
            else stage_enum.value
        )

        return {
            "is_efficient": is_efficient,
            "stage": result_stage,
            "sufficiency": sufficiency_result,
            "confidence_score": round(sufficient_score, 2),
            "probabilities": {
                "sufficient": round(sufficient_score, 2),
                "insufficient": round(insufficient_score, 2)
            },
            "raw_response": response
        }


_evaluator_instance = None


def evaluate_user_prompt(user_content: str, stage: Union[PipelineStage, str]) -> Dict[str, Any]:
    """Convenience function to evaluate user prompts using the shared Laya agent instance."""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = LayaAgentEvaluator()
    return _evaluator_instance.evaluate_prompt(user_content, stage)


# --- Example Usage ---
if __name__ == "__main__":
    sample_prompt = "A young alchemist in a desert city discovers an artifact that freezes time whenever water touches it."
    
    result = evaluate_user_prompt(
        user_content=sample_prompt,
        stage=PipelineStage.PROMPT_EVAL
    )
    
    print("\n--- Prompt Evaluation Result ---")
    print(f"Stage: {result['stage']}")
    print(f"Is Efficient: {result['is_efficient']}")
    print(f"Sufficiency Choice: {result['sufficiency']}")
    print(f"Raw Output: {result['raw_response']}")