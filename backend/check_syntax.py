import ast, os, sys

root = os.path.dirname(os.path.abspath(__file__))
errors = []
ok = []
for dirpath, _, files in os.walk(root):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(dirpath, f)
        try:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            ast.parse(src)
            ok.append(path.replace(root, ""))
        except SyntaxError as e:
            errors.append(f"SYNTAX ERROR in {path}: {e}")

for e in errors:
    print(e)
if not errors:
    print(f"All {len(ok)} Python files parse cleanly.")
else:
    sys.exit(1)
