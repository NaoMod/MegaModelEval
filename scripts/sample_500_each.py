
import argparse
import json
import random


def sample_and_write(input_path, output_path, n, seed_offset=0, seed=None):
    with open(input_path, "r") as f:
        data = json.load(f)

    total = len(data)
    if seed is not None:
        random.seed(seed + seed_offset)

    if total <= n:
        # Can't sample more than exists -- just take everything, shuffled so
        # the output order isn't tied to the original file's generation order.
        sampled = data[:]
        random.shuffle(sampled)
        print(f"{input_path}\n  -> only {total} entries available (<= requested {n}); "
              f"using all {total}, shuffled.")
    else:
        sampled = random.sample(data, n)
        print(f"{input_path}\n  -> {total} entries available; sampled {len(sampled)}.")

    with open(output_path, "w") as f:
        json.dump(sampled, f, indent=2)
    print(f"  Written to: {output_path}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--toolllm-input", required=True)
    ap.add_argument("--toolllm-output", required=True)
    ap.add_argument("--megamodel-input", required=True)
    ap.add_argument("--megamodel-output", required=True)
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=None,
                     help="Optional seed for reproducibility. Omit for a fresh random draw each run.")
    args = ap.parse_args()

    sample_and_write(args.toolllm_input, args.toolllm_output, args.n, seed_offset=0, seed=args.seed)
    sample_and_write(args.megamodel_input, args.megamodel_output, args.n, seed_offset=1, seed=args.seed)
    # seed_offset differs between the two calls so that, even when --seed is
    # set, the two draws aren't identical samplings of two differently-sized
    # pools (this matters less here since one pool is taken whole, but keeps
    # the script correct/general if dataset sizes change later).


if __name__ == "__main__":
    main()