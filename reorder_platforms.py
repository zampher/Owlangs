import json

# Read the platforms.json file
with open('configs/platforms.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extract local platform
local_platform = data['platforms'].pop('local', None)

if local_platform:
    # Create new platforms dict with local first
    new_platforms = {'local': local_platform}
    # Add all other platforms
    new_platforms.update(data['platforms'])
    # Replace platforms
    data['platforms'] = new_platforms
    
    # Write back to file
    with open('configs/platforms.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("Successfully moved 'local' platform to the front")
else:
    print("'local' platform not found")
