import security_brain as sb, re
html = sb._fetch('https://portswigger.net/web-security/all-labs').decode('utf-8', 'ignore')
sections = re.findall(r'id="([a-z0-9\-]+)"[^>]*>([^<]{4,60})</h2>(.*?)(?=<h2|$)', html, re.S)
print('sections:', len(sections))
for sid, title, body in sections[:5]:
    n = len(re.findall(r'academy-labstatus', body))
    print(sid, '|', title, '| labs:', n)
