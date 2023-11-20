#!/usr/bin/env python3
import sys, argparse
parser = argparse.ArgumentParser()
parser.add_argument('-s', help='subject of the email', required=True)
args = parser.parse_args()

subject = repr(args.s)

emails = []

with open("bridge.txt", encoding="utf-8") as f:
    emails = f.readlines()

safe_n = 980

groups = len(emails) // safe_n + 1
# print(groups)

group = 0
count = 0

prefix = '''curl -s --user 'api:<PRIVATE_API_KEY>' \\
    https://api.mailgun.net/v3/galacticpuzzlehunt.com/messages \\
    -F from='Galactic Puzzlesetters <contact@galacticpuzzlehunt.com>' \\
    -F to=info@galacticpuzzlehunt.com \\
    -F bcc=<YOUR_EMAIL_ADDRESS> \\
'''

suffix = f'''    -F text=@body.txt \\
    -F html=@body.html \\
    -F subject={subject}
'''

fs = [open(f"mg-auto-bridge-{group}", "w", encoding="utf-8") for group in range(groups)]

for f in fs:
    f.writelines(prefix)

for email in emails:
    if count >= safe_n:
        group += 1
        count = 0

    fs[group].write("    -F bcc="+email.strip()+" \\\n")
    count += 1

for f in fs:
    f.writelines(suffix)

with open (f"mg-auto-test", "w", encoding="utf-8") as f:
    f.writelines(prefix)
    f.writelines(suffix)

print(f"generated mailgun scripts for {len(emails)} recipients with {groups} groups")
print(f"with subject: {subject}")
