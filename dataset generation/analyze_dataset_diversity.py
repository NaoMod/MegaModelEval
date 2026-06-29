import os
import json
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist
from sklearn.metrics.pairwise import cosine_similarity
import re
from openai import OpenAI
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=env_path)

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found.")


client = OpenAI(api_key=api_key)

EMBEDDING_MODEL = "text-embedding-3-small"
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)



def load_seed_instructions(seed_file_path: str) -> List[str]:
    """Unchanged from the original script: extracts instruction text from a Python file
    containing Seed(...) definitions via regex on `instruction="..."`."""
    with open(seed_file_path, 'r') as f:
        content = f.read()

    pattern = r'instruction="(.*?)",?\n'
    matches = re.findall(pattern, content, re.DOTALL)

    return matches


def load_megamodel_instructions(json_file_path: Path) -> List[str]:
    """Loads a megamodel-guided dataset file (outputs/atl_tools/simple_500_dataset.json or
    multi_500_dataset.json) -- same flat-list-of-items-with-instruction-field shape as the
    original script's load_generated_instructions, unchanged logic."""
    with open(json_file_path, 'r') as f:
        data = json.load(f)

    instructions = [item.get("instruction", "") for item in data if item.get("instruction")]

    return instructions


def load_and_split_generated_instructions(json_file_path: str) -> Dict[str, List[str]]:
    """Loads toolllm_1000_dataset.json (single+multi combined) and splits it into
    single-tool vs multi-tool instruction text lists based on the "pattern" field:
    no comma -> single-tool (e.g. "apply", "get");
    comma present -> multi-tool (e.g. "apply, get", "apply, apply").
    """
    with open(json_file_path, 'r') as f:
        data = json.load(f)

    single_instructions = []
    multi_instructions = []

    for item in data:
        instr = item.get("instruction", "")
        if not instr:
            continue
        pattern = item.get("pattern", "")
        if "," in pattern:
            multi_instructions.append(instr)
        else:
            single_instructions.append(instr)

    return {"single": single_instructions, "multi": multi_instructions}


def get_embeddings(texts: List[str]) -> np.ndarray:
    batch_size = 100
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch
        )
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return np.array(all_embeddings)


def compute_distance(embeddings: np.ndarray) -> float:
    pairwise_distances = pdist(embeddings, metric='euclidean')
    return np.mean(pairwise_distances)


def compute_dispersion(embeddings: np.ndarray) -> float:
    normalized_embeddings = embeddings / np.linalg.norm(embeddings, axis=1)[:, np.newaxis]
    similarities = cosine_similarity(normalized_embeddings)

    n = similarities.shape[0]
    mask = ~np.eye(n, dtype=bool)
    avg_similarity = similarities[mask].mean()

    return 1.0 - avg_similarity


def compute_isocontour_radius(embeddings: np.ndarray) -> float:
    std_devs = np.std(embeddings, axis=0)
    std_devs = std_devs[std_devs > 0]

    if len(std_devs) == 0:
        return 0.0

    return np.exp(np.mean(np.log(std_devs)))


def tokenize_text(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return text.split()


def compute_vocabulary_size(texts: List[str]) -> int:
    all_tokens = []
    for text in texts:
        all_tokens.extend(tokenize_text(text))

    return len(set(all_tokens))


def compute_unique_ngrams(texts: List[str], n: int = 3) -> int:
    all_ngrams = []
    for text in texts:
        tokens = tokenize_text(text)
        if len(tokens) >= n:
            ngrams = [' '.join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]
            all_ngrams.extend(ngrams)

    return len(set(all_ngrams))


def compute_affinity(embeddings1: np.ndarray, embeddings2: np.ndarray) -> float:
    mean_embedding1 = np.mean(embeddings1, axis=0)
    mean_embedding2 = np.mean(embeddings2, axis=0)

    mean_embedding1 = mean_embedding1 / np.linalg.norm(mean_embedding1)
    mean_embedding2 = mean_embedding2 / np.linalg.norm(mean_embedding2)

    return np.dot(mean_embedding1, mean_embedding2)


def normalize_metrics(metrics_dict: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    normalized = {}
    metric_names = list(next(iter(metrics_dict.values())).keys())

    for dataset, metrics in metrics_dict.items():
        normalized[dataset] = {}

    for metric in metric_names:
        values = [metrics[metric] for metrics in metrics_dict.values()]
        min_val = min(values)
        max_val = max(values)

        if max_val == min_val:
            norm_values = [1.0 for _ in values]
        else:
            norm_values = [(v - min_val) / (max_val - min_val) for v in values]

        for i, dataset in enumerate(metrics_dict.keys()):
            normalized[dataset][metric] = norm_values[i]

    return normalized


def run_comparison(
    dataset_type: str,
    seed_file_path: Path,
    megamodel_instructions: List[str],
    toolllm_instructions: List[str],
):
    """Three-way comparison: Seed Dataset vs Megamodel-Guided Dataset vs ToolLLM Baseline
    Dataset, for one dataset_type ("single" or "multi"). Affinity is reported relative to
    the seed dataset for BOTH generated datasets, so you can directly compare which one
    preserves semantic alignment with the seeds better."""
    if not seed_file_path.exists():
        print(f"Seed file not found: {seed_file_path}")
        return

    seed_instructions = load_seed_instructions(seed_file_path)

    print(f"Seeds from: {seed_file_path}")
    print(f"Seed instructions: {len(seed_instructions)}")
    print(f"Megamodel-guided instructions ({dataset_type}): {len(megamodel_instructions)}")
    print(f"ToolLLM-baseline instructions ({dataset_type}): {len(toolllm_instructions)}")

    if not seed_instructions or not megamodel_instructions or not toolllm_instructions:
        print(f"Error: missing data for {dataset_type} comparison (one of the three "
              f"datasets is empty) -- skipping.")
        return

    for name, instrs in [("Seed", seed_instructions), ("Megamodel-guided", megamodel_instructions),
                          ("ToolLLM-baseline", toolllm_instructions)]:
        if len(instrs) < 2:
            print(f"Error: {name} dataset for {dataset_type} has only {len(instrs)} instruction(s) -- "
                  f"Distance/Dispersion require at least 2 to compute a pairwise metric "
                  f"(would otherwise silently produce NaN). Skipping {dataset_type} comparison.")
            return

    print(f"Computing embeddings for {dataset_type} seed dataset...")
    seed_embeddings = get_embeddings(seed_instructions)
    print(f"Computing embeddings for {dataset_type} megamodel-guided dataset...")
    megamodel_embeddings = get_embeddings(megamodel_instructions)
    print(f"Computing embeddings for {dataset_type} ToolLLM-baseline dataset...")
    toolllm_embeddings = get_embeddings(toolllm_instructions)

    datasets = {
        "Seed Dataset": (seed_instructions, seed_embeddings),
        "Megamodel-Guided Dataset": (megamodel_instructions, megamodel_embeddings),
        "ToolLLM Baseline Dataset": (toolllm_instructions, toolllm_embeddings),
    }

    print("Computing diversity metrics...")

    metrics: Dict[str, Dict[str, float]] = {name: {} for name in datasets}
    for name, (instrs, embs) in datasets.items():
        metrics[name]["Distance"] = compute_distance(embs)
        metrics[name]["Dispersion"] = compute_dispersion(embs)
        metrics[name]["Isocontour Radius"] = compute_isocontour_radius(embs)
        metrics[name]["Vocabulary Size"] = compute_vocabulary_size(instrs)
        metrics[name]["Unique 3-grams"] = compute_unique_ngrams(instrs)

    # Affinity relative to seeds, for BOTH generated datasets -- this is the number that
    # directly answers "which generation strategy stays semantically closer to the seeds."
    affinity_megamodel = compute_affinity(seed_embeddings, megamodel_embeddings)
    affinity_toolllm = compute_affinity(seed_embeddings, toolllm_embeddings)

    results = []
    for metric in metrics["Seed Dataset"].keys():
        results.append({
            "Metric": metric,
            "Seed Dataset": metrics["Seed Dataset"][metric],
            "Megamodel-Guided Dataset": metrics["Megamodel-Guided Dataset"][metric],
            "ToolLLM Baseline Dataset": metrics["ToolLLM Baseline Dataset"][metric],
        })

    results.append({
        "Metric": "Affinity (vs. Seeds)",
        "Seed Dataset": "N/A",
        "Megamodel-Guided Dataset": affinity_megamodel,
        "ToolLLM Baseline Dataset": affinity_toolllm,
    })

    df_results = pd.DataFrame(results)

    print("\n" + "="*80)
    print(f"ATL {dataset_type.upper()}-TOOL: SEEDS vs MEGAMODEL-GUIDED vs TOOLLLM-BASELINE")
    print("="*80)
    print(df_results.to_string(index=False))
    print("="*80 + "\n")

    out_dir = OUTPUT_DIR / "three_way_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"atl_{dataset_type}_tool_three_way_diversity.csv"
    df_results.to_csv(csv_path, index=False)
    print(f"Results saved to {csv_path}")


def main():
    # Real ATL seed files
    single_seed_path = SCRIPT_DIR / "seeds" / "model_transformation_seeds" / "all_tools" / "single_tool_seeds.py"
    multi_seed_path = SCRIPT_DIR / "seeds" / "model_transformation_seeds" / "all_tools" / "multi_tool_seeds.py"

    # Real megamodel-guided dataset files (note: single-tool file is named "simple_500_dataset.json", not "single_500...")
    megamodel_single_path = OUTPUT_DIR / "atl_tools" / "simple_500_dataset.json"
    megamodel_multi_path = OUTPUT_DIR / "atl_tools" / "multi_500_dataset.json"

    # ToolLLM baseline: one combined file, split by pattern field
    toolllm_path = OUTPUT_DIR / "toolllm_1000_dataset.json"

    for path, label in [
        (megamodel_single_path, "megamodel-guided single-tool"),
        (megamodel_multi_path, "megamodel-guided multi-tool"),
        (toolllm_path, "ToolLLM baseline"),
    ]:
        if not path.exists():
            print(f"ERROR: {label} dataset not found at {path}")
            return

    print(f"Loading megamodel-guided datasets...")
    megamodel_single = load_megamodel_instructions(megamodel_single_path)
    megamodel_multi = load_megamodel_instructions(megamodel_multi_path)

    print(f"Loading and splitting ToolLLM-baseline dataset from: {toolllm_path}")
    toolllm_split = load_and_split_generated_instructions(toolllm_path)
    print(f"  -> {len(toolllm_split['single'])} single-tool items, "
          f"{len(toolllm_split['multi'])} multi-tool items")

    print("\n" + "="*80)
    print("THREE-WAY DIVERSITY ANALYSIS (ATL): SEEDS / MEGAMODEL-GUIDED / TOOLLLM-BASELINE")
    print("="*80 + "\n")

    run_comparison("single", single_seed_path, megamodel_single, toolllm_split["single"])
    run_comparison("multi", multi_seed_path, megamodel_multi, toolllm_split["multi"])


if __name__ == "__main__":
    main()