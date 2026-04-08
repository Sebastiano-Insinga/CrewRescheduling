"""
File di test per visualizzare il contenuto del file di disruption
"""
import json
from TimeFormat import getDisplayedTimeFormat

def test_disruption_file(disruption_file_path):
    """
    Legge e stampa il contenuto del file di disruption
    """
    print(f"\n{'='*60}")
    print(f"Test disruption file: {disruption_file_path}")
    print(f"{'='*60}\n")
    
    try:
        # Leggi il file JSON raw
        with open(disruption_file_path, 'r') as f:
            disruption_data = json.load(f)
        
        print("Raw JSON data:")
        print(json.dumps(disruption_data, indent=2))
        
        # Estrai i valori come fa readDisruption
        print(f"\n{'='*60}")
        print("Processed values (using readDisruption logic):")
        print(f"{'='*60}\n")
        
        disruption_start = getDisplayedTimeFormat(3, disruption_data["disruption_start"])
        disruption_end = getDisplayedTimeFormat(3, disruption_data["disruption_end"])
        disrupted_sections = disruption_data["disrupted_sections"]
        
        print(f"Disruption Start: {disruption_start}")
        print(f"Disruption End: {disruption_end}")
        print(f"Disrupted Sections: {disrupted_sections}")
        print(f"Number of disrupted sections: {len(disrupted_sections)}")
        
    except FileNotFoundError:
        print(f"ERROR: File not found: {disruption_file_path}")
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON in file: {disruption_file_path}")
    except KeyError as e:
        print(f"ERROR: Missing key in JSON: {e}")


if __name__ == "__main__":
    # Modifica questo percorso con il tuo file di disruption
    disruption_file = "C://Users//sebastiano insinga//Desktop//WU//Crew Rescheduling//Disruption_Files//manuel-01-A-50T-10L-randomized-disrupted_1.json"
    
    test_disruption_file(disruption_file)
