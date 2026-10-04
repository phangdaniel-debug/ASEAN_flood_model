import fsspec, zipfile
url="https://data.4tu.nl/file/1da2e70f-6c4d-4b03-86bd-b53e789cc629/672eba4c-1334-44c6-8119-8879ded25912"
fs=fsspec.filesystem("http")
f=fs.open(url)
zf=zipfile.ZipFile(f)
names=zf.namelist()
print("total entries:", len(names), flush=True)
print("first 5:", names[:5], flush=True)
hit=[n for n in names if "N13E100" in n]
print("N13E100 match:", hit, flush=True)
print("N14E100 match:", [n for n in names if "N14E100" in n], flush=True)
