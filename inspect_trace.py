import json

with open("evidence/discovery_trace.json", encoding="utf-8") as f:
    t = json.load(f)

print("Provider:", t["llm_provider"])
print("Model:", t["llm_model"])
print("Total cycles:", t["total_cycles"])
print()

for c in t["cycles"]:
    d = c["model_decision"]
    action = d.get("action", "?")
    value = d.get("value")
    param = d.get("param_binding")
    thought = str(d.get("thought", ""))[:80]
    print(f"  Cycle {c['cycle']}: {action} | value={value} | param={param}")
    print(f"    thought: {thought}")
    print()
