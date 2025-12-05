"""this script analyzes the execution results of an agent
on a dataset where certain tools were removed, to see which instructions
failed due to the missing tools. It generates a report and calculates
coverage metrics based on the missing tools."""

import json
import csv
import os
import matplotlib.pyplot as plt
import numpy as np

# Define 10 tools to remove (you can modify this list)
TOOLS_TO_REMOVE = [
    "list_transformation_KM32EMF_tool",
    "apply_KM32EMF_transformation_tool",
    "list_transformation_MySQL2KM3_tool",
    "apply_MySQL2KM3_transformation_tool",
    "list_transformation_Families2Persons_tool",
    "apply_Families2Persons_transformation_tool",
    "list_transformation_XML2Ant_tool",
    "apply_XML2Ant_transformation_tool",
    "list_transformation_Make2Ant_tool",
    "apply_Make2Ant_transformation_tool"
]


def load_execution_results(file_path):
    """Load execution results and organize by instruction index."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def map_api_to_tool_name(api_name):
    """Map API names to tool names."""
    if not api_name or '.' not in api_name:
        return api_name
    
    tool_base, action = api_name.split('.', 1)
    
    if action == "get_tool":
        return f"list_transformation_{tool_base}_tool"
    elif action == "apply_tool":
        return f"apply_{tool_base}_tool"
    elif action == "apply":
        return f"apply_{tool_base}_transformation_tool"
    else:
        return api_name

def evaluate_instruction(instruction_data):
    """Evaluate if an instruction succeeded based on expected vs executed tools."""
    expected_apis = instruction_data.get("expected_apis", [])
    execution_results = instruction_data.get("execution_results", [])
    
    if not expected_apis:
        return False, []
    
    # Map expected APIs to tool names
    expected_tools = [map_api_to_tool_name(api) for api in expected_apis]
    
    # Get successfully executed tools
    successful_tools = []
    for result in execution_results:
        if result.get("success", False):
            successful_tools.append(result.get("tool_name", ""))
    
    # Check if all expected tools were successfully executed
    success = all(tool in successful_tools for tool in expected_tools)
    
    return success, expected_tools

def main():
    current_dir = os.path.dirname(__file__)
    

    # Load both baseline and reduced tools results
    reduced_tools_data = load_execution_results(os.path.join(current_dir, 'agent_execution_results_MCPAgent_reduced_tools_seeds_20251030_140658.json'))
    baseline_data = load_execution_results(os.path.join(current_dir, 'agent_execution_results_MCPAgent_seeds_baseline_20251030_142008.json'))
    num_instructions = min(len(reduced_tools_data), len(baseline_data))


    print(f"Analyzing {num_instructions} instructions across 2 versions")
    print("-" * 60)

    # Create CSV report in agent_version_logs directory
    agent_logs_dir = os.path.join(os.path.dirname(current_dir), 'agent_version_logs')
    csv_file = os.path.join(agent_logs_dir, 'seeds_report_generation.csv')

    with open(csv_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Instruction_ID', 'Instruction', 'Missing_Tools', 'Score'])

        transformations_with_issues = {}

        # Use the same scoring as the accuracy script
        def map_api_to_tool_name(api_name):
            if not api_name or '.' not in api_name:
                return api_name
            tool_base, action = api_name.split('.', 1)
            if action == "get_tool":
                return f"list_transformation_{tool_base}_tool"
            elif action == "apply_tool":
                return f"apply_{tool_base}_tool"
            elif action == "apply":
                return f"apply_{tool_base}_transformation_tool"
            else:
                return api_name

        def score_instruction(instruction_data):
            expected_apis = instruction_data.get("expected_apis", [])
            execution_results = instruction_data.get("execution_results", [])
            if not expected_apis:
                return 0.0
            expected_tools = [map_api_to_tool_name(api) for api in expected_apis]
            successful_tools = [result.get("tool_name", "") for result in execution_results if result.get("success", False)]
            if len(expected_tools) == 1:
                return 1.0 if expected_tools[0] in successful_tools else 0.0
            else:
                score = 0.0
                points_per_tool = 0.5 if len(expected_tools) == 2 else (1.0 / len(expected_tools))
                for expected_tool in expected_tools:
                    if expected_tool in successful_tools:
                        score += points_per_tool
                return min(score, 1.0)

    with open(csv_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Instruction_ID', 'Instruction', 'Missing_Tools', 'Score'])

        unique_missing_tools = set()
        for i in range(num_instructions):
            reduced_tools_item = reduced_tools_data[i]
            baseline_item = baseline_data[i]
            instruction_text = reduced_tools_item.get('instruction', f'Instruction {i+1}')
            score_reduced = score_instruction(reduced_tools_item)
            score_baseline = score_instruction(baseline_item)
            # Only include instructions that fail in reduced tools but succeed in baseline
            if score_reduced < 1.0 and score_baseline == 1.0:
                expected_apis = reduced_tools_item.get("expected_apis", [])
                expected_tools = [map_api_to_tool_name(api) for api in expected_apis]
                execution_results = reduced_tools_item.get("execution_results", [])
                successful_tools = [result.get("tool_name", "") for result in execution_results if result.get("success", False)]
                missing_tools = [tool for tool in expected_tools if tool not in successful_tools]

                writer.writerow([
                    i + 1,
                    instruction_text[:100] + "..." if len(instruction_text) > 100 else instruction_text,
                    " | ".join(set(missing_tools)),
                    f"{score_reduced:.2f}"
                ])

                # Collect unique missing tools
                unique_missing_tools.update(missing_tools)

                # Extract transformations with issues
                for tool in missing_tools:
                    if "transformation" in tool:
                        if "list_transformation_" in tool:
                            transfo_name = tool.replace("list_transformation_", "").replace("_tool", "")
                            transformations_with_issues[transfo_name] = transformations_with_issues.get(transfo_name, 0) + 1
                        elif "apply_" in tool and "_transformation_tool" in tool:
                            transfo_name = tool.replace("apply_", "").replace("_transformation_tool", "")
                            transformations_with_issues[transfo_name] = transformations_with_issues.get(transfo_name, 0) + 1

        # Filter and sort transformations that appear more than 3 times
        frequent_issues = {k: v for k, v in transformations_with_issues.items() if v > 3}
        sorted_frequent = sorted(frequent_issues.items(), key=lambda x: x[1], reverse=True)

        # Add transformations with issues as last row in CSV
        if sorted_frequent:
            transformations_summary = " | ".join([f"{transfo}({count})" for transfo, count in sorted_frequent])
            writer.writerow(['SUMMARY', 'Transformations with issues (>3 times)', transformations_summary, ''])

        # Add unique missing tools as the final row
        if unique_missing_tools:
            writer.writerow(['ALL_MISSING_TOOLS', 'Unique missing tools across all failures', " | ".join(sorted(unique_missing_tools)), ''])
                
if __name__ == "__main__":
    main()

    # --- Minimal coverage calculation and chart ---
    # Parse ALL_MISSING_TOOLS from CSV
    csv_file = os.path.join(os.path.dirname(__file__), '..', 'agent_version_logs', 'seeds_report_generation.csv')
    all_missing_tools = set()
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Instruction_ID'] == 'ALL_MISSING_TOOLS':
                all_missing_tools = set([t.strip() for t in row['Missing_Tools'].split(' | ') if t.strip()])

    # Tool coverage
    total_tools = len(TOOLS_TO_REMOVE)
    detected_tools = sum(1 for t in TOOLS_TO_REMOVE if t in all_missing_tools)
    tool_coverage = detected_tools / total_tools if total_tools else 0

    # Transformation coverage
    transformation_tools = set()
    transformation_to_tools = {}
    for tool in TOOLS_TO_REMOVE:
        if "transformation" in tool:
            tname = None
            if tool.startswith("list_transformation_"):
                tname = tool.replace("list_transformation_", "").replace("_tool", "")
            elif tool.startswith("apply_") and tool.endswith("_transformation_tool"):
                tname = tool.replace("apply_", "").replace("_transformation_tool", "")
            if tname:
                transformation_tools.add(tname)
                transformation_to_tools.setdefault(tname, []).append(tool)
    total_transformations = len(transformation_tools)
    detected_transformations = 0
    missing_transformations = []
    for tname in transformation_tools:
        if any(tool in all_missing_tools for tool in transformation_to_tools[tname]):
            detected_transformations += 1
        else:
            missing_transformations.append(tname)
    transformation_coverage = detected_transformations / total_transformations if total_transformations else 0

    print(f"\nTool coverage: {detected_tools}/{total_tools} ({tool_coverage*100:.1f}%)")
    print(f"Transformation coverage: {detected_transformations}/{total_transformations} ({transformation_coverage*100:.1f}%)")
    # --- Table output for detailed coverage ---
    print("\nDetailed Coverage Table:")
    print("{:<40} {:<15}".format("Removed Tool", "Detected as Missing"))
    print("-" * 55)
    for tool in TOOLS_TO_REMOVE:
        detected = "Yes" if tool in all_missing_tools else "No"
        print("{:<40} {:<15}".format(tool, detected))

    print("\nTransformation Coverage Table:")
    print("{:<30} {:<15}".format("Transformation", "Detected as Missing"))
    print("-" * 45)
    for tname in transformation_tools:
        detected = "Yes" if any(tool in all_missing_tools for tool in transformation_to_tools[tname]) else "No"
        print("{:<30} {:<15}".format(tname, detected))
    if missing_transformations:
        print(f"Missing transformations: {', '.join(missing_transformations)}")


    labels = ['Removed Tools', 'Transformations']
    # Only show the blue bar (Removed Tools)
    import matplotlib.gridspec as gridspec
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.axis('off')
    col_labels = ["Removed Tool", "Detected as Missing"]
    # Add coverage row at the top
    coverage_percent = int(tool_coverage * 100)
    table_data = [[f"Coverage: {coverage_percent}%", ""]]
    for tool in TOOLS_TO_REMOVE:
        detected = "Yes" if tool in all_missing_tools else "No"
        table_data.append([tool, detected])
    table = ax.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='left', colWidths=[0.7, 0.3])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.3)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_fontsize(13)
            cell.set_text_props(weight='bold')
            cell.set_facecolor('#e0e0e0')
        if col == 1 and row > 0:
            if cell.get_text().get_text() == "Yes":
                cell.set_facecolor('#b6e3b6')
            elif cell.get_text().get_text() == "No":
                cell.set_facecolor('#f7b6b6')

    plt.tight_layout()
    plots_dir = os.path.join(os.path.dirname(__file__), '..', 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    chart_path = os.path.join(plots_dir, 'coverage_chart_seeds.png')
    plt.savefig(chart_path, dpi=120)
    print(f"\nCoverage chart saved to: {chart_path}")

    # Minimal: Parse TOOLS_TO_REMOVE directly from file
    tools_file = os.path.join(os.path.dirname(__file__), '../scripts/run_agent_reduced_tools.py')
    TOOLS_TO_REMOVE = []
    with open(tools_file, 'r') as f:
        in_tools = False
        for line in f:
            if 'TOOLS_TO_REMOVE' in line and '=' in line:
                in_tools = True
                continue
            if in_tools:
                if ']' in line:
                    break
                line = line.strip().strip(',').strip('"').strip("'")
                if line and not line.startswith('#'):
                    TOOLS_TO_REMOVE.append(line)

    # Parse ALL_MISSING_TOOLS from CSV
    csv_file = os.path.join(os.path.dirname(__file__), '..', 'agent_version_logs', 'seeds_report_generation.csv')
    all_missing_tools = set()
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Instruction_ID'] == 'ALL_MISSING_TOOLS':
                all_missing_tools = set([t.strip() for t in row['Missing_Tools'].split(' | ') if t.strip()])

    # Tool coverage
    total_tools = len(TOOLS_TO_REMOVE)
    detected_tools = sum(1 for t in TOOLS_TO_REMOVE if t in all_missing_tools)
    tool_coverage = detected_tools / total_tools if total_tools else 0

    # Transformation coverage
    transformation_tools = set()
    transformation_to_tools = {}
    for tool in TOOLS_TO_REMOVE:
        if "transformation" in tool:
            tname = None
            if tool.startswith("list_transformation_"):
                tname = tool.replace("list_transformation_", "").replace("_tool", "")
            elif tool.startswith("apply_") and tool.endswith("_transformation_tool"):
                tname = tool.replace("apply_", "").replace("_transformation_tool", "")
            if tname:
                transformation_tools.add(tname)
                transformation_to_tools.setdefault(tname, []).append(tool)
    total_transformations = len(transformation_tools)
    detected_transformations = 0
    for tname in transformation_tools:
        if any(tool in all_missing_tools for tool in transformation_to_tools[tname]):
            detected_transformations += 1
    transformation_coverage = detected_transformations / total_transformations if total_transformations else 0

    print(f"\nTool coverage: {detected_tools}/{total_tools} ({tool_coverage*100:.1f}%)")
    print(f"Transformation coverage: {detected_transformations}/{total_transformations} ({transformation_coverage*100:.1f}%)")