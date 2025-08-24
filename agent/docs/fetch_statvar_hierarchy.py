import json
import urllib.request
import urllib.parse
import time

# Main categories
categories = [
    "dc/g/Agriculture",
    "dc/g/Demographics", 
    "dc/g/Economy",
    "dc/g/Education",
    "dc/g/Energy",
    "dc/g/Environment",
    "dc/g/Health",
    "dc/g/Housing",
    "dc/g/Crime",
    "dc/g/AboutDataCommons",
    "dc/g/UN",
    "dc/g/SDG"
]

url = "https://datacommons.org/api/variable-group/info"
headers = {
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json',
    'origin': 'https://datacommons.org',
    'referer': 'https://datacommons.org/tools/statvar',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
}

def fetch_data(dcid):
    """Fetch data for a given dcid"""
    data = json.dumps({"dcid": dcid, "entities": [], "numEntitiesExistence": 0}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers)
    
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

hierarchy = {}

# Get root level first
print("Fetching root level...")
root_info = fetch_data("dc/g/Root")

hierarchy["root"] = {
    "name": root_info.get("absoluteName", ""),
    "categories": []
}

# Process each main category
for cat_group in root_info.get("childStatVarGroups", []):
    cat_id = cat_group["id"]
    cat_name = cat_group["displayName"]
    cat_count = cat_group["descendentStatVarCount"]
    
    print(f"Fetching {cat_name}...")
    category_entry = {
        "id": cat_id,
        "name": cat_name,
        "count": cat_count,
        "subcategories": []
    }
    
    try:
        # Get subcategories
        cat_info = fetch_data(cat_id)
        for subcat in cat_info.get("childStatVarGroups", []):
            category_entry["subcategories"].append({
                "id": subcat["id"],
                "name": subcat["displayName"],
                "count": subcat["descendentStatVarCount"]
            })
    except Exception as e:
        print(f"  Error fetching {cat_name}: {e}")
    
    hierarchy["root"]["categories"].append(category_entry)
    time.sleep(0.1)  # Be nice to the API

# Save to JSON
with open("datacommons_statvar_hierarchy.json", "w") as f:
    json.dump(hierarchy, f, indent=2)

print("\nHierarchy saved to datacommons_statvar_hierarchy.json")

# Create a simpler text format as well
with open("datacommons_statvar_hierarchy.txt", "w") as f:
    f.write("DATA COMMONS STATISTICAL VARIABLE HIERARCHY\n")
    f.write("=" * 50 + "\n\n")
    
    for category in hierarchy["root"]["categories"]:
        f.write(f"{category['name']} ({category['count']:,} variables)\n")
        for subcat in category["subcategories"]:
            f.write(f"  ├── {subcat['name']} ({subcat['count']:,})\n")
        if not category["subcategories"]:
            f.write("  (no subcategories)\n")
        f.write("\n")

print("Text version saved to datacommons_statvar_hierarchy.txt")

# Print summary
print("\nSummary:")
print(f"Total main categories: {len(hierarchy['root']['categories'])}")
total_subcats = sum(len(cat['subcategories']) for cat in hierarchy['root']['categories'])
print(f"Total subcategories: {total_subcats}")
