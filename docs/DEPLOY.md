# Public hackathon demo deployment

Use an **isolated, disposable public demo** without real customer data. This app is an unauthenticated interactive sandbox, not a secure production observability system.

## Render (Docker, GitHub repo)
1. Publish this source directory to a **new public GitHub repository**. Verify `.env`, keys and any `data/*.db` are **not** committed.
2. Log in to Render, create a Web Service from the repository (Docker runtime), or use the supplied `render.yaml` blueprint if your account supports its chosen plan.
3. Set `PUBLIC_DEMO=1`, `PORT=8000` (or your platform's port; `run_demo.py` reads `PORT`).
4. Wait until `/api/health` answers. The service boots order/inventory/payment as child processes inside the same container; only the control-plane endpoint binds publicly.
5. Open the URL and choose **Run guided investigation**. Test the full review, approval and verification workflow.
6. Share the public URL only after checking it in an incognito browser. If the hosting service spins down or resets storage on restart, warm it up before recording your demo.

**Do not add AI provider keys to a public deployment until you have enabled appropriate account limits.** Public visitors can trigger AI requests and spend your quota. For a judge-accessible demo, offline grounded mode is acceptable; alternatively run AI in your local recording and keep the public demo offline.

## Railway / other container hosts
Deploy using the provided Dockerfile, expose the `PORT` environment variable, and set `PUBLIC_DEMO=1`. Only the main FastAPI control plane is publicly bound. Do not expose ports 8001–8003.

## Local container
```bash
docker build -t tracemind-ai .
docker run --rm -p 8000:8000 -e PUBLIC_DEMO=1 tracemind-ai
```
Visit http://localhost:8000.

## Security, scale & limitations
- This is **not an authenticated app**. Anyone with the link can reset the demo state or use simulated faults; throttling is a basic in-memory limit, not abuse protection.
- All failure conditions, including the DB pool, are simulated; service-to-service HTTP requests and captured events are real.
- Uses a SQLite database stored inside the container by default; some free hosting plans use ephemeral storage, so incidents may disappear on restarts.
- Use a single instance (multiple instances would not share in-memory payment configuration), no persistent user data, and no production access.
- Optional `OPENAI_API_KEY` or `GROQ_API_KEY` must be injected using the hosting provider's **secret environment variables**, never committed or typed into a public app.
