import csv
from pathlib import Path

csv_path = Path('F:/Gildia_AI/basci_agents_explanation-main/data/my_wardrobe.csv')

def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        data = list(csv.DictReader(f))
    return data

rows = read_csv(csv_path)
print('Total rows:', len(rows))
print('Categories:', sorted(set(row['Category'] for row in rows)))
print('Sample items per category:')
for cat in set(row['Category'] for row in rows):
    items = [row['Item'] for row in rows if row['Category'] == cat]
    print(f'  {cat}: {len(items)} items -> {items[:5]}')