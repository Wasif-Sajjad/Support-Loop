import pandas as pd
from datasets import load_dataset
import random
import os

SEED = 42
random.seed(SEED)

def main():
    print("Loading Bitext dataset...")
    # Load the dataset from HuggingFace
    dataset = load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset", split="train")
    df = dataset.to_pandas()
    
    # We want ~10 few-shot examples per intent.
    # We also want a non-overlapping eval set of ~60-80 rows total.
    
    # Let's get unique intents
    intents = df['intent'].unique()
    print(f"Found {len(intents)} unique intents.")
    
    few_shot_data = []
    eval_data = []
    
    for intent in intents:
        intent_df = df[df['intent'] == intent].copy()
        
        # Shuffle for randomness
        intent_df = intent_df.sample(frac=1, random_state=SEED).reset_index(drop=True)
        
        # Take 10 for few-shot
        few_shot_samples = intent_df.head(10)
        
        for _, row in few_shot_samples.iterrows():
            few_shot_data.append({
                "instruction": row['instruction'],
                "intent": row['intent'],
                "category": row['category']
            })
            
        # Take 3 for eval set (27 intents * 3 = 81 rows)
        eval_samples = intent_df.iloc[10:13]
        
        for _, row in eval_samples.iterrows():
            eval_data.append({
                "ticket_text": row['instruction'],
                "correct_intent": row['intent'],
                "correct_decision": "",
                "notes": ""
            })
            
    print(f"Sampled {len(few_shot_data)} few-shot examples.")
    print(f"Sampled {len(eval_data)} eval set examples.")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    
    # Write few-shot examples to Python file
    few_shot_file = os.path.join(project_root, "backend", "app", "agents", "few_shot_examples.py")
    with open(few_shot_file, "w", encoding="utf-8") as f:
        f.write("# AUTO-GENERATED from Bitext dataset. Do not edit manually.\n")
        f.write("FEW_SHOT_EXAMPLES = [\n")
        for item in few_shot_data:
            # Escape strings carefully
            instruction = item['instruction'].replace('"', '\\"')
            intent = item['intent']
            category = item['category']
            f.write(f'    {{"instruction": "{instruction}", "intent": "{intent}", "category": "{category}"}},\n')
        f.write("]\n")
    print(f"Wrote {few_shot_file}")
    
    # Write eval set to CSV
    eval_df = pd.DataFrame(eval_data)
    
    eval_file = os.path.join(project_root, "docs", "eval_set.csv")
    
    # Ensure docs directory exists just in case
    os.makedirs(os.path.dirname(eval_file), exist_ok=True)
    
    eval_df.to_csv(eval_file, index=False)
    print(f"Wrote {eval_file}")

if __name__ == "__main__":
    main()
