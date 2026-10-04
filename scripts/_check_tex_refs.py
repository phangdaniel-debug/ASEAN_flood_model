import re
import sys

t = open(sys.argv[1], encoding="utf-8").read()
cites = set()
for m in re.findall(r"\\cite\{([^}]*)\}", t):
    for k in m.split(","):
        cites.add(k.strip())
items = set(re.findall(r"\\bibitem\{([^}]*)\}", t))
print("cited not defined:", sorted(cites - items))
print("defined not cited:", sorted(items - cites))
print(f"n_cite_keys={len(cites)} n_bibitems={len(items)}")
print("braces { }:", t.count("{"), t.count("}"))
print("begin/end document:", t.count(r"\begin{document}"), t.count(r"\end{document}"))
print("label refs:", sorted(set(re.findall(r"\\label\{([^}]*)\}", t))))
print("ref keys:", sorted(set(re.findall(r"\\ref\{([^}]*)\}", t))))
