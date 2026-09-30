# Deployment guide: Render (backend) + Vercel (frontend)

Both have free tiers and deploy straight from GitHub. You need the code on GitHub first (see README §12).

## 0. What gets deployed

| Part | Platform | Root directory | Build | Start / output |
|---|---|---|---|---|
| FastAPI backend | Render (Web Service) | `backend` | `pip install -r requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| React frontend | Vercel (or Netlify) | `frontend` | `npm run build` | output folder `dist` |

The two talk over HTTPS. The frontend needs the backend URL (`VITE_API_URL`); the backend needs the frontend URL (`CORS_ORIGINS`). So deploy the backend first, then the frontend, then go back and set CORS.

## 1. Backend on Render

**Option A: Blueprint (uses `render.yaml` in the repo)**
1. render.com → **New → Blueprint** → connect GitHub → select the repository.
2. Render reads `render.yaml` and asks for the three secret values:
   * `LLM_API_KEY`: paste your **free Groq key** (create one at console.groq.com/keys), or leave blank for a Demo-only site. `render.yaml` already sets `LLM_PROVIDER=groq`, the free open-source Llama model.
   * `REAL_MODE_ACCESS_CODE`: choose any passphrase (strongly recommended if you set a key, otherwise anyone who finds the site can spend your credit).
   * `CORS_ORIGINS`: put a placeholder such as `http://localhost:5173` for now.
3. **Apply**. Wait for the deploy to go green.

**Option B: manual**: New → Web Service → repo → Root Directory `backend` → Runtime Python → build/start commands from the table → add the environment variables above plus `PYTHON_VERSION=3.12.8`.

Copy the service URL, e.g. `https://prompt-lab-api.onrender.com`, and check:
```bash
curl https://<your-service>.onrender.com/api/health      # {"status":"ok"}
```

## 2. Frontend on Vercel

1. vercel.com → **Add New → Project** → import the same repository.
2. **Root Directory:** `frontend`. Framework preset: Vite (auto-detected). Build command `npm run build`, output `dist`.
3. **Environment Variables:** `VITE_API_URL` = `https://<your-service>.onrender.com` (**no trailing slash**). It is baked in at build time, so if you change it you must redeploy.
4. **Deploy**, then copy the site URL, e.g. `https://prompt-lab.vercel.app`.

*Netlify instead:* Base directory `frontend`, build `npm run build`, publish directory `frontend/dist`, same `VITE_API_URL` variable.

## 3. Connect them (CORS)

In Render → your service → Environment: set `CORS_ORIGINS` to the exact frontend origin, e.g. `https://prompt-lab.vercel.app` (no path, no trailing slash; comma-separate several). Save; Render restarts the service.

## 4. Test the live application (checklist)

**API from your terminal**
```bash
API=https://<your-service>.onrender.com
curl $API/api/health
curl $API/api/config                       # real_available true/false; must NOT contain your key
curl -X POST $API/api/experiments -H "Content-Type: application/json" \
     -d '{"task":"Explain what a hash table is.","mode":"demo"}'      # 201 + 6 results
curl -X POST $API/api/experiments -H "Content-Type: application/json" -d '{"task":""}'   # 422 (validation works)
```
**In the browser (open the Vercel URL)**
- [ ] Page loads and the amber *Demo Mode* banner appears (first load can take ~1 min while a free Render service wakes up).
- [ ] Click an example chip → **Run experiment** → 6 rows in the metric table, charts, green *Recommended prompt*.
- [ ] Change weights → **Re-score** → ranking updates without a delay.
- [ ] **Export CSV / JSON** downloads a file; the demo rows say `demo (simulated)`.
- [ ] **History** tab lists the run; Open / Delete work.
- [ ] *(If you set a key)* switch to **Real (API)**, enter the access code, run a task: *REAL · model* badge, tokens marked without `~`, latency measured. Try a wrong code → a clear 401 message.
- [ ] Open DevTools → Network: no response contains your API key. No red CORS errors.
- [ ] Phone-width check (DevTools device toolbar): no sideways page scroll.

**Troubleshooting**
| Symptom | Fix |
|---|---|
| "Cannot reach the backend" in the UI | `VITE_API_URL` wrong/missing (redeploy frontend after changing it), or the Render service is still waking up |
| CORS error in the console | `CORS_ORIGINS` must equal the frontend origin exactly (https, no trailing slash) |
| *Real (API)* button is greyed out | `LLM_API_KEY` not set on Render (hover the button to see the reason) |
| 401 in Real Mode | wrong `REAL_MODE_ACCESS_CODE` |
| Real-mode variants show "Authentication failed" | the key is invalid or revoked |
| Build fails on Render with a Python error | set `PYTHON_VERSION=3.12.8` |

## 5. Free-tier limits you should know

* **Cold starts:** a free Render service sleeps after ~15 minutes idle; the next request takes up to a minute.
* **History is not durable on Render's free plan.** Its disk is ephemeral, so the SQLite file is wiped on every redeploy/restart. Options:
  * *Persistent disk (paid plan):* add a disk mounted at `/var/data` and set `DATABASE_URL=sqlite:////var/data/prompt_lab.db`.
  * *Free hosted Postgres (e.g. Neon, Supabase):* add `psycopg2-binary` to `backend/requirements.txt` and set `DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME`. SQLAlchemy should need no other code change (the project is developed and tested on SQLite only, so test this before relying on it).
* **Real Mode uses your key's free quota, shared by every visitor.** Keep `REAL_MODE_ACCESS_CODE` set on a public deployment so strangers cannot use it up, and expect rate-limit (429) messages if many people run experiments at once. If you switch to a paid provider, also set a spending limit in its console.
* **Keys live only in Render's environment settings.** Never put a key in the Vercel/frontend variables (anything there is public) and never commit `.env`.
