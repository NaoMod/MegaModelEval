import json
import os
from pathlib import Path

def count_plan_steps(json_file):
    """Count total plan_steps items in a JSON file."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    total_steps = 0
    instruction_count = 0
    
    for item in data:
        if 'plan_steps' in item:
            steps = len(item['plan_steps'])
            total_steps += steps
            instruction_count += 1
    
    return total_steps, instruction_count

def main():
    base_dir = Path(__file__).parent
    
    
    total_all_steps = 0
    total_all_instructions = 0
    
    for i in range(1, 8):
        version_dir = base_dir / f"version_{i}"
        if not version_dir.exists():
            continue
        
        # Find JSON files that don't contain 'seeds' in the name
        json_files = [f for f in version_dir.glob("*.json") 
                      if 'seeds' not in f.name.lower()]
        
        for json_file in json_files:
            total_steps, instruction_count = count_plan_steps(json_file)
            total_all_steps += total_steps
            total_all_instructions += instruction_count
            
            print(f"version_{i:<4} {json_file.name:<55} {instruction_count:<15} {total_steps:<12}")
    
    print("-" * 70)
    print(f"{'TOTAL':<12} {'':<55} {total_all_instructions:<15} {total_all_steps:<12}")
    print("=" * 70)
    
    # Also show average steps per instruction
    if total_all_instructions > 0:
        avg = total_all_steps / total_all_instructions
        print(f"\nAverage plan steps per instruction: {avg:.2f}")

if __name__ == "__main__":
    main()
