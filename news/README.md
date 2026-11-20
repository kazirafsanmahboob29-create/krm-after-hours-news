# After Hours headlines

The EIA Today in Energy and Federal Reserve Board All Press Releases feeds supply attributed headlines and links for the city news board. Generate the JSON locally with:

```sh
python3 news/fetch_news.py --out docs/news.json
```

For the dedicated GitHub repository, copy this `news/` directory and `.github/workflows/news.yml` from the project root. In Settings → Pages, choose GitHub Actions as the source. Run **Update news** once manually. The workflow deploys the generated JSON directly to Pages and runs hourly afterward. A failed feed run leaves the last successful Pages deployment available.

Before setting `newsUrl` in `city/places.js`, verify that the deployed `news.json` contains items and returns a CORS header allowing the portfolio origin.
