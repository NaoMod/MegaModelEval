

import argparse
import json
import random

def classify(entry):

    relevant_apis = entry.get("relevant_apis", [])
    if len(relevant_apis) == 1:
        return "single"
    elif len(relevant_apis) >= 2:
        return "multi"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to toolllm_1000_dataset.json")
    ap.add_argument("--output", required=True, help="Path to write the sampled ablation_test.json")
    ap.add_argument("--n-single", type=int, default=100, help="Number of single-tool instructions to sample")
    ap.add_argument("--n-multi", type=int, default=100, help="Number of multi-tool instructions to sample")
    ap.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility (omit for a fresh random draw each run)")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    with open(args.input, "r") as f:
        data = json.load(f)

    single_entries = [e for e in data if classify(e) == "single"]
    multi_entries = [e for e in data if classify(e) == "multi"]

    print(f"Total instructions in input: {len(data)}")
    print(f"  Single-tool pool: {len(single_entries)}")
    print(f"  Multi-tool pool:  {len(multi_entries)}")

    if len(single_entries) < args.n_single:
        raise ValueError(f"Requested {args.n_single} single-tool samples but only {len(single_entries)} available.")
    if len(multi_entries) < args.n_multi:
        raise ValueError(f"Requested {args.n_multi} multi-tool samples but only {len(multi_entries)} available.")

    sampled_single = random.sample(single_entries, args.n_single)
    sampled_multi = random.sample(multi_entries, args.n_multi)

    # Tag each entry with its category for easier manual review/filtering later,
    # without mutating any of the original fields.
    for e in sampled_single:
        e["_sample_category"] = "single"
    for e in sampled_multi:
        e["_sample_category"] = "multi"

    combined = sampled_single + sampled_multi
    random.shuffle(combined)  # interleave single/multi so review isn't biased by order

    with open(args.output, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\nSampled {len(sampled_single)} single-tool + {len(sampled_multi)} multi-tool "
          f"= {len(combined)} total instructions.")
    print(f"Written to: {args.output}")


if __name__ == "__main__":
    main()