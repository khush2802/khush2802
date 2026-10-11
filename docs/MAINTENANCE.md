# How this profile works

This repository is the GitHub profile README for [khush2802](https://github.com/khush2802). GitHub shows `README.md` on the profile page because the repository name matches the username and the repository is public.

## Files

| Path | What it is | Edited by |
| --- | --- | --- |
| `README.md` | The profile text | Hand |
| `scripts/render_dashboard.py` | Draws every image in `assets/generated/` (Python standard library only) | Hand |
| `scripts/test_render_dashboard.py` | Tests for the generator | Hand |
| `.github/workflows/dashboard.yml` | Re-runs the generator daily and commits the result | Hand |
| `assets/generated/header-{dark,light}.svg` | Name banner | Generator |
| `assets/generated/dashboard-{dark,light}.svg` | Contribution landscape and stats | Generator |
| `assets/generated/*-compact-{dark,light}.svg` | The same two images laid out for screens 600 px wide or less | Generator |
| `assets/generated/contributions.json` | The exact numbers behind the dashboard | Generator |
| `assets/languages-{dark,light}.svg` | "Main language by repository" card, a dated snapshot | Hand (one-off) |
| `assets/stack/*.svg` | Tech Stack chips: a Simple Icons 16.32.0 logo plus the name, with light and dark colours chosen by `prefers-color-scheme` | Hand (one-off) |

Don't edit files in `assets/generated/` by hand; the next run overwrites them. Nothing outside `assets/generated/` is touched by the workflow.

## What the dashboard shows

- **Window:** the last 365 days, ending on the day the workflow runs (UTC). The exact dates are printed on the image and stored in `contributions.json`.
- **Contributions:** the sum of the daily counts in that window, as reported by GitHub's contribution calendar. GitHub's own "N contributions in the last year" heading can differ by a few because it counts a slightly wider window; the dashboard counts exactly the days it draws.
- **Active days:** days in the window with at least one contribution.
- **Public repos:** public repositories owned by the account, forks included — the same number as the profile's Repositories tab.
- **By weekday:** contributions per weekday across the window.
- **Encoding:** a cube's colour is GitHub's own contribution level for that day; its height is the day's count on a log scale (one contribution is the smallest cube, the busiest day the tallest).

Contributions made by the workflow itself don't count: its commits are authored by `github-actions[bot]`, not by you.

## Automation

The workflow runs:

- every day at 00:41 UTC (06:11 IST),
- on any push to `main` that changes `scripts/` or the workflow,
- whenever you press **Run workflow** under **Actions → Refresh contribution dashboard**.

Each run tests the generator, fetches the data, renders the images and commits the result. `contributions.json` records when the data was fetched, so every successful run makes a commit; that daily commit is also what keeps GitHub from pausing the schedule. It needs **no secrets**: it uses the built-in `GITHUB_TOKEN`, which sees what a logged-out visitor sees, and the workflow grants it only `contents: write` so it can push the images.

If a run fails (GitHub API outage, failing test, network error), nothing is committed and the profile keeps showing the last good images. The "updated" date on the dashboard tells you how fresh they are, and GitHub emails you about the failed run.

GitHub pauses scheduled workflows in public repositories after 60 days without activity. The daily commits count as activity; if the schedule ever stops anyway, re-enable it from the Actions tab.

### Optional: `DASHBOARD_TOKEN`

Only add this if runs fail with permission or rate-limit errors from the GraphQL API.

1. Create a **fine-grained personal access token** (Settings → Developer settings → Personal access tokens → Fine-grained tokens) with **Repository access: Public repositories (read-only)**, no extra permissions, and an expiry date.
2. In this repository: Settings → Secrets and variables → Actions → **New repository secret**, name `DASHBOARD_TOKEN`, paste the token.

Never paste a token into a file in this repository. The workflow reads the secret at run time and falls back to `GITHUB_TOKEN` when it isn't set.

Keep the dashboard on public data: a token that also counts private contributions would print numbers visitors can't check against your public calendar.

## Run it locally

```bash
python3 -m unittest discover -s scripts                       # tests
GITHUB_TOKEN=<your token> python3 scripts/render_dashboard.py  # fetch and write assets/generated/
python3 scripts/render_dashboard.py --from-json assets/generated/contributions.json --out preview   # offline
```

`--from-json` re-renders from a saved `contributions.json` without calling the API — useful for trying design changes. The first images in this repository were produced that way, from the public contribution calendar, before the workflow had run; the first scheduled run replaces them with API data.

## Updating the README

- The language card doesn't update itself; its date is printed on it. To refresh it, take the main language GitHub shows for each repository on the **Repositories** tab, skip forks, repositories without code and this one, count each repository once, then update both SVGs, the image's `alt` text and the caption under it.
- When a project's status changes (finished, deployed, abandoned), update its sentence and links.
- Before featuring a repository, make sure it has a README, setup steps and a working demo link (or say there isn't one).
- List a technology under **Tech Stack** only when a public repository uses it.

## Credits

The isometric-calendar idea comes from [colincode0/github-readme](https://github.com/colincode0/github-readme). That repository has no license file, so none of its code is used here; `render_dashboard.py` is an independent implementation with its own projection, data window, metrics and tests.

Technology logos come from [Simple Icons](https://simpleicons.org) (CC0 1.0), recoloured; each logo remains a trademark of its owner. The [Git logo](https://git-scm.com/community/logos) by Jason Long is licensed under CC BY 3.0, and the JavaScript logo comes from [voodootikigod/logo.js](https://github.com/voodootikigod/logo.js) (MIT).
