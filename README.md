# Weather-Aware Truck Routing

A dispatcher enters an origin, destination, departure time, and load weight. The app asks OpenRouteService for up to three truck routes, samples weather along each route at the truck's arrival time, and recommends the safest option. A map shows the routes, checkpoints, and a 0–48 hour corridor forecast.

## Run it locally

You need Python 3.12+, Node 20+, and a free [OpenRouteService](https://openrouteservice.org/dev/#/signup) API key. Weather comes from Open-Meteo and does not need a key.

```powershell
copy .env.example .env
# Put your key in OPENROUTESERVICE_API_KEY

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py test
python manage.py runserver

cd ..\frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to Django on port 8000.

Docker is the more reliable setup for a walkthrough, because a free host can be asleep:

```powershell
docker compose up --build
```

The UI is on http://localhost:5173 and the API is on http://localhost:8000.

## What the recommendation does

Each checkpoint is scored from wind, rain, and snow. The checkpoint level is the worst of the three after the load rules. Where two printed bands share an edge (rain at 0.25 in/hr, snow at 1.0 in/hr), the more severe band wins.

Wind (mph): under 25 low, 25–34 moderate, 35–44 high, 45–54 severe, 55 or more no travel.

Rain (in/hr): under 0.10 low, 0.10–0.25 moderate, 0.25–0.50 high, 0.50–1.00 severe, over 1.00 no travel.

Snow (in/hr): under 0.5 low, 0.5–1.0 moderate, 1.0–2.0 high, 2.0–3.0 severe, over 3.0 no travel.

Load rules upgrade wind only:

- 55 mph or more is no travel for every load
- 45–54 mph and more than 30,000 lb becomes no travel
- 35–44 mph and more than 40,000 lb becomes severe
- Exactly 30,000 lb and exactly 40,000 lb do not upgrade

Miles are counted on the stretch between checkpoints. That stretch takes the worse of its two ends, so the truck is charged for driving into a storm. Unknown weather is not counted as low. If one end is unknown and the known end is only low or moderate, the stretch stays unknown. A known high, severe, or no-travel end is kept.

Average risk is the mile-weighted mean: low 1, moderate 2, high 3, severe 4, no travel 5.

Routes are ordered by fewest no-travel miles, then fewest severe miles, then fewest high miles, then fewest unknown miles, then lowest average risk, then shortest travel time. No-travel is ranked first because it is the stricter band in the same table. The app still names a winner when every route has no-travel miles, and it says there is no fully safe route.

Checkpoints use the forecast hour of the truck's ETA. The slider is separate: it shows the corridor from the current hour through 48 hours. Scrubbing it does not call the network. The departure mark on the slider is only a reference.

## Assumptions

- 10, 25, and 50 miles are a spacing choice. The default is 25. The app does not invent a third route when the road network returns fewer.
- OpenRouteService `driving-hgv` is asked for two alternatives when the cities are within about 56 miles. Longer trips skip that call, because the alternative-route algorithm rejects anything over 100 km, then the app also asks for the fastest and shortest routes and keeps the ones that differ. The response is capped at three. Weight is sent as metric tonnes.
- Sampling follows the road geometry, scaled to the API's road miles. ETA comes from the route's step distance and duration, not a flat 55 mph.
- Open-Meteo `rain` is millimetres per hour converted with 25.4, and `snowfall` is centimetres per hour converted with 2.54. Wind is requested in mph.
- The heatmap is a grid inside a 25 mile buffer, capped at about 250 points, and it uses the same load rules as the checkpoints.
- Forecasts are cached for 30 minutes by coordinates rounded to two decimals. Run Gunicorn with one worker so that cache is shared (`--workers 1 --threads 4`).

## API

`GET /api/v1/health`

`POST /api/v1/analyze`

```json
{
  "origin": "Chicago, IL",
  "destination": "Detroit, MI",
  "departure": "2026-10-18T15:00:00Z",
  "load_lb": 35000,
  "sample_miles": 25
}
```

`departure` must include a timezone offset. `sample_miles` must be 10, 25, or 50.

The response includes `recommended_route_id`, a `reason`, per-route summaries, colored segments, checkpoints (ETA, wind, rain, snow, level, and the rules that fired), and heatmap points whose `risks` arrays are 49 hours long. Risk codes are 0 unknown, 1 low, 2 moderate, 3 high, 4 severe, 5 no travel.

## Tests

```powershell
cd backend
python manage.py test routing
```

The tests cover the printed wind, rain, and snow edges, both load cutovers, segment miles, the route sort, sampling, and a mocked end-to-end trip where the shorter route loses because the wind closes it.

## Deploy

Backend: [Render](https://render.com) blueprint in `render.yaml` (root directory `backend`). Set `OPENROUTESERVICE_API_KEY` and `CORS_ALLOWED_ORIGINS` to the frontend origin, for example `https://your-app.vercel.app`.

Frontend: Vercel, project root `frontend`. Set `VITE_API_URL` to the Render URL, with no trailing slash, before the build. Vite bakes that value into the client.

```powershell
cd frontend
npx vercel --prod
```

## Walkthrough

1. Score Chicago to Detroit with a 35,000 lb load and 25 mile spacing.
2. Open a checkpoint and show the ETA, the wind, and a load rule when one fires.
3. Compare the cards: a longer route can win because it has fewer severe or no-travel miles.
4. Drag the 0–48 hour slider and show that the network panel stays idle.
5. Mention one limit: the road network sometimes returns only one or two routes, and the forecast does not cover a departure more than a week out.
