#!/usr/bin/env python3
"""
Script to evaluate the accuracy of agent execution results.

Scoring criteria:
- Score 1: If success is true AND the expected tool is found among the executed tools
- Score 0.5: For multi-instruction cases where each expected tool gets 0.5 points
- Score 0: If the expected tool is not found or execution failed

The script maps API names to tool names:
- "ToolName.get_tool" -> "list_transformation_ToolName_tool"
- "ToolName.apply_tool" -> "apply_ToolName_tool"
"""

import json

from pathlib import Path

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
        # Handle other patterns if needed
        return api_name

def evaluate_instruction(instruction_data):

    expected_apis = instruction_data.get("expected_apis", [])
    execution_results = instruction_data.get("execution_results", [])
    
    if not expected_apis:
        return 0.0
    
    # Map expected APIs to tool names
    expected_tools = [map_api_to_tool_name(api) for api in expected_apis]
    
    # Get successfully executed tools
    successful_tools = []
    for result in execution_results:
        if result.get("success", False):
            successful_tools.append(result.get("tool_name", ""))
    
    # Calculate score
    if len(expected_tools) == 1:
        # Single tool expected - score 1 if found, 0 if not
        expected_tool = expected_tools[0]
        return 1.0 if expected_tool in successful_tools else 0.0
    else:
        # Multiple tools expected - 0.5 points for each found tool
        score = 0.0
        points_per_tool = 0.5 if len(expected_tools) == 2 else (1.0 / len(expected_tools))
        
        for expected_tool in expected_tools:
            if expected_tool in successful_tools:
                score += points_per_tool
        
        return min(score, 1.0)  # Cap at 1.0

def evaluate_file(file_path):
    """
    Evaluate all instructions in a JSON file and return the average accuracy.
    
    Args:
        file_path: Path to the JSON file containing execution results
        
    Returns:
        tuple: (average_accuracy, detailed_results)
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return 0.0, []
    
    if not isinstance(data, list):
        return 0.0, []
    
    detailed_results = []
    total_score = 0.0
    
    for i, instruction_data in enumerate(data):
        score = evaluate_instruction(instruction_data)
        total_score += score
        
        detailed_results.append({
            "instruction_index": i,
            "instruction": instruction_data.get("instruction", ""),
            "expected_apis": instruction_data.get("expected_apis", []),
            "score": score,
            "success_tools": [
                result.get("tool_name", "") 
                for result in instruction_data.get("execution_results", [])
                if result.get("success", False)
            ]
        })
    
    average_accuracy = total_score / len(data) if data else 0.0
    return average_accuracy, detailed_results

def evaluate_and_report(file_path, version_name, results_summary):
    """Generic function to evaluate a version and add to results summary."""
    if file_path.exists():
        print(f"Evaluating: {file_path.name}")
        accuracy, details = evaluate_file(file_path)
        print(f"{version_name} Accuracy: {accuracy:.3f} ({accuracy*100:.1f}%)")
        print(f"Total Instructions: {len(details)}")
        print()
        results_summary[version_name.lower().replace(" ", "_")] = {
            "file": file_path.name,
            "accuracy": accuracy,
            "total_instructions": len(details)
        }
        return accuracy, details
    else:
        print(f"{version_name} file not found: {file_path}")
        return 0.0, []

def main():
    """Main function to evaluate all result files."""
    
    # Define the paths to the result files
    outputs_dir = Path(__file__).parent
    agent_logs_dir = outputs_dir / "agent_version_logs"
    ablation_dir = outputs_dir / "ablation_test"
    
    # File mappings: (file_path, display_name)
    files_to_evaluate = [
        (agent_logs_dir / "agent_execution_results_MCPAgent_baseline_20251020_134540.json", "Baseline"),
        (outputs_dir / "minimal_prompt_v0_file.json", "V0"),
        (outputs_dir / "prompt_v1.json", "V1"),
        (outputs_dir / "prompt_V2.json", "V2"),
        (ablation_dir / "agent_execution_results_MCPAgent_reduced_tools_20251020_122115.json", "Reduced Tools"),
    ]
    
    print("=== Agent Execution Results Accuracy Evaluation ===\n")
    
    results_summary = {}
    
    # Evaluate all versions using the generic function
    for file_path, version_name in files_to_evaluate:
        evaluate_and_report(file_path, version_name, results_summary)
    
    # Compare results
    if len(results_summary) > 1:
        print("=== Accuracy Comparison ===")
        accuracies = [(name, data["accuracy"]) for name, data in results_summary.items()]
        accuracies.sort(key=lambda x: x[1], reverse=True)
        
        for i, (name, accuracy) in enumerate(accuracies):
            rank = i + 1
            print(f"{rank}. {name.replace('_', ' ').title()}: {accuracy:.3f} ({accuracy*100:.1f}%)")
        print()
        
    # Save detailed results to a file
    if results_summary:
        summary_file = outputs_dir / "accuracy_evaluation_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        print(f"Detailed results saved to: {summary_file}")

if __name__ == "__main__":
    main()