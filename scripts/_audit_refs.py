import re, sys
path = sys.argv[1]
tex = open(path, encoding="utf-8").read()
cited = set()
for m in re.findall(r"\\cite\{([^}]*)\}", tex):
    for k in m.split(","):
        cited.add(k.strip())
defined = re.findall(r"\\bibitem\{([^}]*)\}", tex)
defset = set(defined)
print(f"== {path} ==")
print("cited keys:", len(cited), "| bibitems:", len(defined))
dups = sorted({k for k in defined if defined.count(k) > 1})
print("UNDEFINED:", sorted(cited - defset) or "none")
print("ORPHAN:", sorted(defset - cited) or "none")
print("DUPLICATE:", dups or "none")
