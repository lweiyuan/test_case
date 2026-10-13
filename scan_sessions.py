import zstandard, json, os, glob, sys

sdir = r"C:\Users\15735\.dsh\sessions\--D-code-nic_project-~5929~874E--"
sessions = [
    "session-ab18fddc-2768-4a67-9ced-95589520ab0a",
    "session-6ae2e628-7878-4d77-b49e-015e75553f75",
    "session-f769749d-681c-4632-97c4-8567c1316785",
    "session-664ff4d0-6885-4ba9-aba4-bb912cd5f945",
    "session-f82085fe-3675-40ef-a99a-d2017928c36c",
]
kw = ["技巧", "VF测试设计", "VF", "测试用例", "等价类", "边界值", "场景法"]

dctx = zstandard.ZstdDecompressor()
def load(path):
    with open(path, "rb") as f:
        data = f.read()
    return dctx.decompress(data)

for sid in sessions:
    p = os.path.join(sdir, sid, "session.jsonl.zstd")
    if not os.path.exists(p):
        print("[missing] " + sid)
        continue
    try:
        raw = load(p).decode("utf-8", errors="replace")
    except Exception as e:
        print("[ERR] " + sid + ": " + str(e))
        continue
    lines = raw.splitlines()
    hits = 0
    for ln in lines:
        if any(k in ln for k in kw):
            hits += 1
    print("[%s] lines=%d kw_hits=%d" % (sid, len(lines), hits))
    # dump matched lines to a sidecar for inspection
    with open(os.path.join(sdir, sid, "_scan_kw.txt"), "w", encoding="utf-8") as fo:
        for ln in lines:
            if any(k in ln for k in kw):
                fo.write(ln + "\n")
