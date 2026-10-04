"""Remove EF's scaffolded UpdateData statements for seed rows (HasData uses DateTime.UtcNow, so every
`migrations add` emits them). Usage: python strip_seed_noise.py <migration .cs file>"""
import io
import re
import sys

path = sys.argv[1]
s = io.open(path, encoding='utf-8').read()
pattern = re.compile(r'\n[ \t]*migrationBuilder\.UpdateData\((?:.|\n)*?\);\n')
s, n = pattern.subn('\n', s)
# collapse the blank lines left behind
s = re.sub(r'\n{3,}', '\n\n', s)
note = ("        // Note: EF also scaffolded UpdateData statements for seed rows (HasData uses DateTime.UtcNow, so the\n"
        "        // model always looks changed). They were removed on purpose.\n\n")
if 'were removed on purpose' not in s:
    s = re.sub(r'(public partial class \w+ : Migration\s*\{\n)', r'\1' + note.replace('\\', '\\\\'), s, count=1)
io.open(path, 'w', encoding='utf-8', newline='').write(s)
print(f'removed {n} UpdateData blocks from {path}')
