from cognition.planner import Planner

p = Planner(None, None)

samples = [
    "```json\n[\n    {action: write_file, data: {path: 'out.txt', content: 'hello',},},\n]\n```",
    "[{'action': write_file, 'data': {'path': file.txt, 'content': None, 'flag': True}}]",
]

for s in samples:
    print("--- SAMPLE ---")
    print(s)
    candidate = p._extract_json(s)
    print("CANDIDATE_REPR:", repr(candidate))
    print("CANDIDATE:", candidate)
    repaired = p._attempt_repair_json(candidate)
    print("REPAIRED_REPR:", repr(repaired))
    print("REPAIRED:", repaired)
    try:
        import json
        parsed = json.loads(repaired)
        print("PARSED:", parsed)
    except Exception as e:
        print("PARSE_ERROR:", e)

print("done")
