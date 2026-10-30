import os
from huggingface_hub import snapshot_download

# Define your custom local directory
LOCAL_PATH = "/home/cis/Desktop/Swayam/Projects/Manga/ai_pipeline/ai_models/laya_model"

os.makedirs(LOCAL_PATH, exist_ok=True)

print(f"Downloading ONLY the English base model to {LOCAL_PATH}...")

snapshot_download(
    repo_id="convaiinnovations/laya",
    local_dir=LOCAL_PATH,
    local_dir_use_symlinks=False,
    # Ignore multilingual and typed-decisions subfolders to download only the English root files (~843 MB)
    ignore_patterns=["multilingual/*", "typed-decisions/*", ".git*"]
)

print("Download complete!")