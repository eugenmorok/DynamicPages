import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dynamicpages.settings')

import django
django.setup()

from django.template import Template, Context
from django.template.loader import render_to_string
from django.test import RequestFactory
from pages.context_processors import common_settings

# Check base template is valid
try:
    from django.template.loader import get_template
    t = get_template('base.html')
    print("base.html: template OK")
except Exception as e:
    print(f"base.html: TEMPLATE ERROR - {e}")

# Check template renders
try:
    ctx = common_settings(None)
    ctx['categories'] = []
    html = t.render(ctx)
    print(f"base.html: rendered OK ({len(html)} chars)")
    
    # Check if Bootstrap Icons link is in rendered output
    if 'bootstrap-icons' in html:
        print("  ✓ Bootstrap Icons link: PRESENT in HTML")
        # Find the link
        for line in html.split('\n'):
            if 'bootstrap-icons' in line:
                print(f"  → {line.strip()}")
    else:
        print("  ✗ Bootstrap Icons link: MISSING from HTML")
    
    # Check for icon class usage
    icon_count = html.count('bi bi-')
    print(f"  ✓ Icon class references: {icon_count}")
    
except Exception as e:
    print(f"base.html: RENDER ERROR - {e}")
    import traceback
    traceback.print_exc()

# Check CSP directives
from dynamicpages.settings import CONTENT_SECURITY_POLICY
directives = CONTENT_SECURITY_POLICY.get('DIRECTIVES', {})
print("\nCSP DIRECTIVES:")
for name, value in directives.items():
    if isinstance(value, (tuple, list)):
        print(f"  {name}: {value}")
