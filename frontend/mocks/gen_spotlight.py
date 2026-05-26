"""Generate market_spotlight.json for the Microsoft spotlight market."""

import json
import random
from datetime import date, timedelta

random.seed(42)

EVENTS = [
    {
        "date": "2026-04-29",
        "label": "MSRC: critical NuGet RCE patched",
        "note": "Microsoft patches a SYSTEM-level RCE in the NuGet client used by Visual Studio and the dotnet CLI, drawing scrutiny to the package ecosystem.",
        "delta": 0.05,
    },
    {
        "date": "2026-05-06",
        "label": "BitLocker bypass PoC published",
        "note": "Researcher publishes working proof-of-concept for bypassing BitLocker via TPM bus sniffing on unpatched Surface and Azure Stack hardware.",
        "delta": 0.10,
    },
    {
        "date": "2026-05-13",
        "label": "Suspicious MSAL.js dependency flagged",
        "note": "A GitHub issue surfaces suspicious transitive deps in MSAL.js, used in millions of Azure-integrated apps. Microsoft opens internal audit.",
        "delta": 0.07,
    },
    {
        "date": "2026-05-20",
        "label": "Microsoft announces NuGet audit",
        "note": "Microsoft confirms a proactive security audit of all first-party NuGet packages and announces mandatory code-signing for official feeds.",
        "delta": -0.06,
    },
]

event_map = {e["date"]: e["delta"] for e in EVENTS}

start = date(2026, 4, 25)
end = date(2026, 5, 25)

prob = 0.05
history = []
current = start

while current <= end:
    ds = current.strftime("%Y-%m-%d")
    if ds in event_map:
        prob += event_map[ds]
    prob += random.gauss(0, 0.007)
    prob = round(max(0.02, min(0.40, prob)), 3)
    history.append({"date": ds, "prob": prob})
    current += timedelta(days=1)

spotlight = {
    "id": "mkt-microsoft-spotlight",
    "title": "Will Microsoft suffer a supply chain attack via NuGet or GitHub Actions by Jun 30?",
    "description": "A confirmed supply chain compromise affecting Microsoft-owned packages on NuGet or GitHub Actions runners, with downstream impact on Azure or enterprise customers.",
    "grade": "A",
    "price": 100,
    "payout": 2000,
    "end_date": "2026-06-30T00:00:00Z",
    "status": "open",
    "bet_count": 892,
    "company": {
        "id": "microsoft",
        "title": "Microsoft",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg",
    },
    "probability_history": history,
    "events": EVENTS,
}

out = "market_spotlight.json"
with open(out, "w") as f:
    json.dump(spotlight, f, indent=2)

print(f"Wrote {len(history)} data points and {len(EVENTS)} events to {out}")
