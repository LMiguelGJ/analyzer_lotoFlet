#!c:/Users/LMiguelGJ/Desktop/LotePy/.venv/Scripts/python.exe
import subprocess
import re
import os

def get_predictions(order_value):
    """Get predictions for a specific order value"""
    # Create temporary file with modified order
    with open('MarkovPY.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified_content = re.sub(r'NUMERO_ORDER = \d+', f'NUMERO_ORDER = {order_value}', content)
    temp_file = f'temp_order_{order_value}.py'
    
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        # Run analysis
        result = subprocess.run(['python', temp_file], capture_output=True, text=True, encoding='utf-8')
        output = result.stdout
        
        # Extract predictions
        return {
            'global': re.search(r'🌍 Global: (Par|Impar)', output),
            'context': re.search(r'🔍 Contexto: (Par|Impar)', output),
            'combined': re.search(r'🏆 Combinada: (PAR|IMPAR)', output)
        }
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

def main():
    """Run analysis for orders 3, 4, 5, 6 with final count summary"""
    print("🎲 Markov Analysis Runner")
    
    # Track predictions
    predictions = {'global': [], 'context': [], 'combined': []}
    
    for order in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
        print(f"\n{'='*50}")
        print(f"Order {order} Analysis")
        print(f"{'='*50}")
        
        try:
            preds = get_predictions(order)
            
            # Extract values
            global_val = preds['global'].group(1) if preds['global'] else 'N/A'
            context_val = preds['context'].group(1) if preds['context'] else 'N/A'
            combined_val = preds['combined'].group(1).lower().capitalize() if preds['combined'] else 'N/A'
            
            print(f"Global: {global_val}")
            print(f"Context: {context_val}")
            print(f"Combined: {combined_val}")
            
            # Store valid predictions
            for pred_type, value in [('global', global_val), ('context', context_val), ('combined', combined_val)]:
                if value in ['Par', 'Impar']:
                    predictions[pred_type].append(value)
                    
        except Exception as e:
            print(f"Error with order {order}: {e}")
    
    # Final count summary
    print(f"\n{'='*50}")
    print("📊 FINAL COUNT SUMMARY")
    print(f"{'='*50}")
    
    for pred_type in ['global', 'context', 'combined']:
        par_count = predictions[pred_type].count('Par')
        impar_count = predictions[pred_type].count('Impar')
        label = pred_type.capitalize() + (" Predictions:" if pred_type != 'combined' else " Recommendations:")
        print(f"\n{label}")
        print(f"  🟢 Par: {par_count}")
        print(f"  🔴 Impar: {impar_count}")
    
    print(f"\n✅ Analysis complete!")
    
    # Conteo final total
    total_par = sum(predictions[pred_type].count('Par') for pred_type in ['global', 'context', 'combined'])
    total_impar = sum(predictions[pred_type].count('Impar') for pred_type in ['global', 'context', 'combined'])
    print(f"\n📈 TOTAL FINAL:")
    print(f"  🟢 Par: {total_par}")
    print(f"  🔴 Impar: {total_impar}")

if __name__ == "__main__":
    main()