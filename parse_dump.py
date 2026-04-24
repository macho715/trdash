import re

content = open('gantt_dump.html', encoding='utf-8').read()

# Find all rect elements with id
pattern = r'<rect[^>]+id="([^"]+)"[^>]*>'
matches = re.findall(pattern, content)
print('RECT IDs:')
for m in matches[:20]:
    print(' ', m)

# Find rect near bd2
idx = content.find('id="bd2"')
if idx >= 0:
    print('\nFOUND rect id=bd2 at index', idx)
    print(content[max(0,idx-50):idx+300])
else:
    print('\nNO rect id=bd2 found')
    # Search for bd2 anywhere
    for m in re.finditer(r'bd2', content):
        start = max(0, m.start()-30)
        print('  bd2 context:', repr(content[start:m.start()+100]))
