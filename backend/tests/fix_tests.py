"""Script to fix test file"""
import re

with open('test_wallet_complete.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix User creation - replace username with name and add id
content = re.sub(
    r'user = User\(email="([^"]+)",\s*username="([^"]+)",\s*password_hash="([^"]+)"(?:,\s*stripe_customer_id="([^"]+)")?\)',
    lambda m: f'user = User(id="user_test123", email="{m.group(1)}", name="{m.group(2)}", password_hash="{m.group(3)}"' + (f', stripe_customer_id="{m.group(4)}")' if m.group(4) else ')'),
    content
)

# Fix str(user.id) to user.id since id is already string
content = re.sub(r'str\(user\.id\)', 'user.id', content)

# Fix event_id from string to int in Bet creation
content = re.sub(r'event_id=f"event_(\d+)"', r'event_id=\1', content)
content = re.sub(r'event_id="event_([^"]+)"', lambda m: f'event_id={hash(m.group(1)) % 1000000}', content)

with open('test_wallet_complete.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed!")

