import json, sys

meta = {
    "owner": sys.argv[1],
    "repo": sys.argv[2],
    "full_repo": sys.argv[3],
    "pr_number": int(sys.argv[4]),
    "head_sha": sys.argv[5],
    "title": sys.argv[6],
}
with open(sys.argv[7], "w") as f:
    json.dump(meta, f, indent=2)
