# TraceMind AI — 2 minute Wispr hackathon demo (record your actual app)

**00:00–00:15** — “When checkout fails across services, finding which dependency broke means hopping between logs. TraceMind AI connects the failure to evidence.” Show dashboard.

**00:15–00:35** — Click **Run guided investigation**. It triggers a real checkout request through separate order, inventory and payment HTTP services and injects a **simulated** pool capacity fault.

**00:35–00:55** — Open incident detail: “The evidence includes a payment HTTP 503, followed by an order HTTP 502. It is not an invented trace.” Show event list and trace ID.

**00:55–01:15** — Focus the copilot input and **actually dictate with Wispr Flow**: “Why did my payment checkout fail? Show the exact trace evidence.” Send. Mention whether response is offline evidence mode or connected to an actual LLM (do not claim online AI when offline).

**01:15–01:38** — Return to incident, show proposed runtime config diff. Click **Approve mitigation**, then **Apply & run 3 verification tests**.

**01:38–01:53** — Show PASS results from three real HTTP checkouts and Resolved incident. Show trace waterfall briefly.

**01:53–02:00** — “TraceMind turns service failures into explainable, reviewable, verified demo incidents. Built for backend developers.”

Capture your **Wispr Insights usage card separately** as submission proof. Never use generated or edited screenshots as proof of usage.
