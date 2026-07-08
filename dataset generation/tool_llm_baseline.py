import os
import sys
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import signal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import argparse

load_dotenv()


EXCLUDED_ARGUMENTS = {"session_id"}


def _visible_arguments(arg_names: Sequence[str]) -> List[str]:
    return [a for a in arg_names if a not in EXCLUDED_ARGUMENTS]


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_llm() -> Optional[ChatOpenAI]:
    model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    if not os.getenv("OPENAI_API_KEY"):
        return None
    return ChatOpenAI(model=model_name, temperature=0.2, max_retries=2)


def _safe_invoke(llm: ChatOpenAI, prompt: str) -> str:
    msg = llm.invoke(prompt)
    return getattr(msg, "content", str(msg)).strip()


def _try_parse_json_instruction(response_text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(response_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"instruction": response_text.split("\n")[0].strip(), "relevant_apis": []}



class IncrementalWriter:
    def __init__(self, path: Path, target_total: int, label: str = ""):
        self.path = path
        self.target_total = target_total
        self.label = label
        self.items: List[Dict[str, Any]] = []
        self._interrupted = False
        self._install_signal_handler()

    def _install_signal_handler(self):
        def _handler():
            self._interrupted = True
            print(
                f"\n[{self.label}] Ctrl+C received -- saving {len(self.items)} items "
                f"generated so far to {self.path} before exiting."
            )
            self._flush()
            sys.exit(130)  # standard exit code for SIGINT

        signal.signal(signal.SIGINT, _handler)

    def _flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.items, indent=2))

    def append(self, item: Dict[str, Any]):
        self.items.append(item)
        self._flush()
        pct = (len(self.items) / self.target_total * 100) if self.target_total else 0
        preview = item.get("instruction", "")[:70].replace("\n", " ")
        print(f"[{self.label}] {len(self.items)}/{self.target_total} ({pct:.1f}%) -> {preview}...")

    @property
    def interrupted(self) -> bool:
        return self._interrupted


# ---------------------------------------------------------------------------
# 1) Single-tool instruction generation (ToolLLM I1: iterate over each tool)
# ---------------------------------------------------------------------------

def generate_single_tool_instructions(
    tools: List[Dict[str, Any]],
    single_tool_seeds: List[Any],
    n_per_tool: int = 1,
    llm_max_calls: int = 1000,
    seed: Optional[int] = None,
    save_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    if seed is not None:
        random.seed(seed)

    llm = _get_llm()
    target_total = len(tools) * max(1, n_per_tool)
    writer = IncrementalWriter(save_path, target_total, label="single-tool") if save_path else None
    items: List[Dict[str, Any]] = writer.items if writer else []
    if llm is None or not tools:
        return items

    llm_calls = 0
    for tool in tools:
        name = tool.get("name", "")
        desc = tool.get("description", "")
        pattern = tool.get("pattern", "")
        arg_names = _visible_arguments(tool.get("arguments", []))
        args_str = ", ".join(arg_names) if arg_names else "(none)"

        pattern_seeds = [s for s in single_tool_seeds if _get(s, "pattern") == pattern]
        if not pattern_seeds:
            pattern_seeds = single_tool_seeds

        for _ in range(max(1, n_per_tool)):
            if llm_calls >= llm_max_calls:
                break

            selected_seeds = random.sample(pattern_seeds, min(3, len(pattern_seeds))) if pattern_seeds else []
            seed_examples = "\n".join(f"- {_get(s, 'instruction')}" for s in selected_seeds)

            prompt = (
                f"You will be provided with a tool, its description, and its required parameters. "
                f"Your task is to create ONE varied, innovative, detailed user query that uses this "
                f"tool. Don't ask which tool to use -- state the need directly. Don't ask for the "
                f"required parameters -- provide concrete values directly in the query (e.g. not "
                f"'a model' but an exact file path and model type). Make the query specific and "
                f"concrete, as if it were one of seven specific queries in a set of ten (not one of "
                f"the three complex/lengthy ones).\n\n"
                f"Tool: {name}\n"
                f"Pattern: {pattern}\n"
                f"Description: {desc}\n"
                f"Required arguments: {args_str}\n\n"
                f"Example queries for this pattern:\n{seed_examples}\n\n"
                f"Return ONLY valid JSON, no extra text:\n"
                '{"instruction": "...", "relevant_apis": [{"api_name": "' + name + '", "arguments": "..."}]}'
            )

            try:
                response_text = _safe_invoke(llm, prompt)
                llm_calls += 1
                parsed = _try_parse_json_instruction(response_text)
                instruction = parsed.get("instruction", "").strip()
                relevant_apis = parsed.get("relevant_apis") or [{"api_name": name, "arguments": ""}]
                if instruction:
                    item = {
                        "pattern": pattern,
                        "instruction": instruction,
                        "relevant_apis": relevant_apis,
                    }
                    if writer:
                        writer.append(item)
                    else:
                        items.append(item)
            except Exception as e:
                print(f"[single-tool] call failed for {name}: {e}")
                continue

        if llm_calls >= llm_max_calls:
            break

    return items


# ---------------------------------------------------------------------------
# 2) Multi-tool instruction generation (ToolLLM I2/I3: sample 2-5 tools from the SAME
#    category, with no type-compatibility filtering)
# ---------------------------------------------------------------------------


def sample_random_groups(
    tools: List[Dict[str, Any]],
    n_groups: int,
    group_size: int = 2,
    seed: Optional[int] = None,
) -> List[List[Dict[str, Any]]]:
    if seed is not None:
        random.seed(seed)

    if len(tools) < group_size:
        return []

    return [random.sample(tools, group_size) for _ in range(n_groups)]


def generate_multi_tool_instructions(
    tools: List[Dict[str, Any]],
    multi_tool_seeds: List[Any],
    n_instructions: int = 500,
    group_size: int = 2,
    llm_max_calls: int = 1000,
    seed: Optional[int] = None,
    save_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    if seed is not None:
        random.seed(seed)

    llm = _get_llm()
    writer = IncrementalWriter(save_path, n_instructions, label="multi-tool") if save_path else None
    items: List[Dict[str, Any]] = writer.items if writer else []
    if llm is None or not tools:
        return items

    groups = sample_random_groups(tools, n_groups=n_instructions, group_size=group_size, seed=seed)
    if not groups:
        return items

    llm_calls = 0
    for group in groups:
        if llm_calls >= llm_max_calls:
            break

        tool_names = [t["name"] for t in group]
        tool_block = "\n".join(
            f"- Tool: {t['name']} | Pattern: {t.get('pattern','')} | "
            f"Description: {t.get('description','')} | "
            f"Required arguments: {', '.join(_visible_arguments(t.get('arguments', []))) or '(none)'}"
            for t in group
        )
        pattern_key = ", ".join(t.get("pattern", "") for t in group[:2])  # ToolLLM seeds are pairwise-labeled
        pattern_seeds = [s for s in multi_tool_seeds if _get(s, "pattern") == pattern_key]
        if not pattern_seeds:
            pattern_seeds = multi_tool_seeds
        selected_seeds = random.sample(pattern_seeds, min(3, len(pattern_seeds))) if pattern_seeds else []
        seed_examples = "\n".join(f"- {_get(s, 'instruction')}" for s in selected_seeds)
        prompt = (
            f"You will be provided with several tools, their descriptions, and required "
            f"parameters. Your task is to create ONE varied, innovative, detailed user query "
            f"that uses MORE THAN ONE of these tools together -- a query using only one tool "
            f"will not be accepted. Don't ask which tool to use -- state the need directly. "
            f"Don't ask for the required parameters -- provide concrete values directly in the "
            f"query (e.g. not 'a model' but an exact file path and model type), using only the "
            f"arguments listed for each tool. Combine the tools in a meaningful, logically "
            f"ordered way.\n\n"
            f"Tools:\n{tool_block}\n\n"
            f"Example multi-tool queries:\n{seed_examples}\n\n"
            f"Return ONLY valid JSON, no extra text:\n"
            '{"instruction": "...", "relevant_apis": [{"api_name": "...", "arguments": "..."}, ...]}'
        )

        try:
            response_text = _safe_invoke(llm, prompt)
            llm_calls += 1
            parsed = _try_parse_json_instruction(response_text)
            instruction = parsed.get("instruction", "").strip()
            relevant_apis = parsed.get("relevant_apis") or [{"api_name": n, "arguments": ""} for n in tool_names]
            if instruction and relevant_apis:
                item = {
                    "pattern": pattern_key,
                    "instruction": instruction,
                    "relevant_apis": relevant_apis,
                    "sampled_group_size": len(group),
                }
                if writer:
                    writer.append(item)
                else:
                    items.append(item)
        except Exception as e:
            print(f"[multi-tool] call failed for group {tool_names}: {e}")
            continue

    return items

def validate_dataset(examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ok: List[Dict[str, Any]] = []
    for e in examples:
        if not isinstance(e, dict):
            continue
        instr = e.get("instruction")
        apis = e.get("relevant_apis", [])
        if instr and isinstance(apis, list) and apis and all(
            isinstance(a, dict) and a.get("api_name") for a in apis
        ):
            ok.append(e)
    return ok


def deduplicate(examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for e in examples:
        instr = e.get("instruction", "")
        if instr not in seen:
            seen.add(instr)
            deduped.append(e)
    return deduped


def generate_toolllm_dataset(
    tools: List[Dict[str, Any]],
    single_tool_seeds: List[Any],
    multi_tool_seeds: List[Any],
    n_single_per_tool: int = 1,
    n_multi_instructions: int = 500,
    multi_tool_group_size: int = 2,
    llm_max_calls: int = 2000,
    seed: int = 42,
    save_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    single_save = (save_dir / "_progress_single.json") if save_dir else None
    multi_save = (save_dir / "_progress_multi.json") if save_dir else None

    single_items = generate_single_tool_instructions(
        tools=tools,
        single_tool_seeds=single_tool_seeds,
        n_per_tool=n_single_per_tool,
        llm_max_calls=llm_max_calls,
        seed=seed,
        save_path=single_save,
    )

    multi_items = generate_multi_tool_instructions(
        tools=tools,
        multi_tool_seeds=multi_tool_seeds,
        n_instructions=n_multi_instructions,
        group_size=multi_tool_group_size,
        llm_max_calls=llm_max_calls,
        seed=seed,
        save_path=multi_save,
    )

    combined = validate_dataset(single_items + multi_items)
    combined = deduplicate(combined)

    target_total = len(tools) * n_single_per_tool + n_multi_instructions
    if len(combined) != target_total:
        print(
            f"[toolllm_baseline] WARNING: generated {len(combined)} validated/deduplicated "
        )

    return combined

def write_dataset(examples: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(examples, indent=2))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Standalone ToolLLM-style baseline generator")
    parser.add_argument("--tools-file", type=str, required=True,
                         help="JSON file: list of {name, description, pattern, arguments}")
    parser.add_argument("--single-seeds-file", type=str, required=True,
                         help="JSON file: list of {pattern, instruction}")
    parser.add_argument("--multi-seeds-file", type=str, required=True,
                         help="JSON file: list of {pattern, instruction}")
    parser.add_argument("--n-single-per-tool", type=int, default=1)
    parser.add_argument("--n-multi", type=int, default=500)
    parser.add_argument("--group-size", type=int, default=2,
                         help="Tools per multi-tool instruction (fixed at 2 for this domain)")
    parser.add_argument("--llm-max-calls", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="outputs/toolllm_baseline_dataset.json")
    args = parser.parse_args()

    with open(args.tools_file) as f:
        tools_in = json.load(f)
    with open(args.single_seeds_file) as f:
        single_seeds_in = json.load(f)
    with open(args.multi_seeds_file) as f:
        multi_seeds_in = json.load(f)

    out_path = Path(args.out)

    dataset = generate_toolllm_dataset(
        tools=tools_in,
        single_tool_seeds=single_seeds_in,
        multi_tool_seeds=multi_seeds_in,
        n_single_per_tool=args.n_single_per_tool,
        n_multi_instructions=args.n_multi,
        multi_tool_group_size=args.group_size,
        llm_max_calls=args.llm_max_calls,
        seed=args.seed,
        save_dir=out_path.parent,
    )
    all_tool_names = {t["name"] for t in tools_in}
    covered_names = {
        api.get("api_name") for item in dataset for api in item.get("relevant_apis", [])
    }
    missing = sorted(all_tool_names - covered_names)
    if missing:
        print(f"[toolllm_baseline] Coverage check: {len(missing)}/{len(all_tool_names)} "
              f"tools never appeared in any generated instruction: {missing}")
    else:
        print(f"[toolllm_baseline] Coverage check: all {len(all_tool_names)} tools appeared "
              f"at least once.")

    write_dataset(dataset, out_path)
    print(f"Generated {len(dataset)} validated instructions -> {out_path}")
    print(f"(Incremental progress files also saved at {out_path.parent}/_progress_single.json "
          f"and {out_path.parent}/_progress_multi.json)")