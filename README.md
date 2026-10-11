<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/header-compact-dark.svg">
  <source media="(max-width: 600px)" srcset="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/header-compact-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/header-dark.svg">
  <img alt="Khush Meena — Software engineering · Applied AI · Systems" src="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/header-light.svg" width="100%">
</picture>

### Hi, I'm Khush

I'm an early-career developer — B.Tech in Computer Science, IIIT Pune, 2026 — and I'm most interested in what happens beneath the interface: where a login session actually lives, how a timeline turns into motion, how an algorithm's state changes one line at a time.

My loop is simple: take an idea, learn the theory behind it, build it, test it, and improve the design when something breaks. This page is the evidence trail for that loop — what's finished, what's in progress and what's still on paper, labelled as such.

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/dashboard-compact-dark.svg">
  <source media="(max-width: 600px)" srcset="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/dashboard-compact-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/dashboard-dark.svg">
  <img alt="Isometric 3D chart of my GitHub contributions over the last 365 days, with total contributions, active days, public repositories and a by-weekday breakdown" src="https://raw.githubusercontent.com/khush2802/khush2802/main/assets/generated/dashboard-light.svg" width="100%">
</picture>

<sub>Drawn by <a href="https://github.com/khush2802/khush2802/blob/main/scripts/render_dashboard.py">render_dashboard.py</a> from GitHub's contribution data and refreshed daily by a <a href="https://github.com/khush2802/khush2802/blob/main/.github/workflows/dashboard.yml">GitHub Action</a>. Colour is GitHub's own contribution level; height is the day's count on a log scale. Raw numbers: <a href="https://github.com/khush2802/khush2802/blob/main/assets/generated/contributions.json">contributions.json</a>.</sub>

## What I believe

**Knowing why it works is part of making it work.** I don't count a feature as done until I can explain the mechanism under it — why a login survives a server restart, why an animation eases the way it does, what a recursive call leaves on the stack.

**Edge cases are implementation, not cleanup.** A missing record, an empty API response, an expired token: these are branches of the program like any other, and they deserve the same design attention as the happy path.

**"It says it's done" isn't evidence — including from AI.** AI tools speed up how I learn and build, but generated code is a hypothesis until it builds, passes its tests and behaves correctly. Foreman, a system I've specified, is designed around exactly that rule.

**A good abstraction removes complexity instead of hiding it.** In UNIVERSE, my 3D portfolio, UI components never import fixtures or a database; they call one data-source interface, so the storage layer can change without touching the UI.

## What I'm building

### My Software Universe &nbsp;`in progress`

An interactive 3D portfolio where every public repository becomes a planet — generated from the repository itself instead of hand-written project cards.

- **Built with** Next.js 16 (App Router), TypeScript, React Three Fiber and three.js, Tailwind CSS v4, Zod.
- **Decisions:** one `DataSource` seam between the UI and storage; synthetic fixtures that show up in development but are excluded from production builds by default; forks (such as a Node.js fork) deliberately left out so the site never implies authorship; reduced-motion and WebGL-support checks with a non-3D fallback.
- **Status:** the design system, hero and 3D universe are built and deployed. The repository analyser that fills each planet isn't built yet, so most entries still read "Not analysed yet". I'm building it in spec-driven chunks with an AI pair-programmer.

[Live site](https://universe-zmtx.vercel.app/) · [Source](https://github.com/khush2802/UNIVERSE)

### Hostel Adda &nbsp;`finished · 2025`

A hostel-listing web app: sign up, publish a listing with photos and a location, see it on a map, and review other listings.

- **Built with** Node.js, Express, MongoDB with Mongoose, EJS, Passport (local strategy), express-session with connect-mongo, Multer and Cloudinary, Mapbox, Joi.
- **What's interesting:** authentication and authorisation are separate middleware layers — `isLoggedIn` guards routes, while `isOwner` and `isReviewAuthor` check the resource against the signed-in user. Locations are geocoded when a listing is created and stored as GeoJSON points for the map. A Mongoose `findOneAndDelete` hook removes a listing's reviews with it, and sessions live in MongoDB rather than server memory.
- **Context:** an early full-stack project, built on a widely taught listing-app pattern and re-themed for hostels.

[Source](https://github.com/khush2802/Hostel-Adda)

### GTA VI landing-page recreation &nbsp;`finished · 2025`

A fan recreation of the GTA VI website intro, built to learn timeline-driven animation.

- **Built with** React 19, Vite, GSAP (`useGSAP`), Tailwind CSS v4; deployed to GitHub Pages.
- **Techniques:** an SVG `<mask>` reveals the scene through the "VI" glyph, which a GSAP timeline then rotates and scales away. Once the timeline passes 90%, the overlay is removed and the main scene eases in. A `mousemove` handler moves the sky, city and title layers at different rates to create depth.

[Live demo](https://khush2802.github.io/GTA-5/) · [Source](https://github.com/khush2802/GTA-5)

## What I'm exploring

**Designing before building.** I've written IEEE 830-style requirement specifications for two systems I plan to build. Neither is implemented yet; the specs are where I work out the hard parts first.

- **AlgoTrace** records a Python program's execution line by line, checks user-declared invariants at every step, and jumps straight to the first step where one breaks. The hard parts: running untrusted code in a sandbox, and storing traces as deltas small enough to replay in a browser. [Specification](https://github.com/khush2802/targets/blob/main/algotrace-srs.md)
- **Foreman** turns a development task into a dependency graph of subtasks for AI agents, and accepts an agent's work only once it builds, passes tests and answers real HTTP requests inside a sandbox. [Specification](https://github.com/khush2802/targets/blob/main/foreman-srs.md)

**Backend structure.** Express services layered as routes → controllers → services → models, with validation and authentication: role-based access in [hireAI](https://github.com/khush2802/hireAI), and email-verified sign-up over Gmail OAuth2 in [perplexity](https://github.com/khush2802/perplexity). Both are authentication modules so far, not finished products.

**Go fundamentals** — structs, maps, interfaces, an HTTP client and a unit test — in [go-start](https://github.com/khush2802/go-start).

## How I work

Understand the problem → study the concept underneath → implement → test → find the limits → improve.

That's the loop I aim for. Not every repository here shows every step yet, which is why everything on this page says what's finished and what isn't.

**Current focus** — October 2026

| Status | Work |
| --- | --- |
| Finished | Hostel Adda · GTA VI recreation |
| In progress | UNIVERSE (repository analyser next) · hireAI and perplexity backends (authentication only so far) · Python and local LLMs · DSA in C++ · Go fundamentals |
| Specified, not started | AlgoTrace · Foreman |

## Stack

Only what appears in my public code. The last column says where.

| Area | Technologies | Where |
| --- | --- | --- |
| Languages | JavaScript, C++, TypeScript, Go (learning) | most repositories, [DSA](https://github.com/khush2802/DSA), [UNIVERSE](https://github.com/khush2802/UNIVERSE), [go-start](https://github.com/khush2802/go-start) |
| Frontend | React, Vite, Next.js, Tailwind CSS, GSAP, React Three Fiber, three.js, Sass | [GTA-5](https://github.com/khush2802/GTA-5), [UNIVERSE](https://github.com/khush2802/UNIVERSE), [OS](https://github.com/khush2802/OS) |
| Backend | Node.js, Express, REST APIs, Passport sessions, JWT, bcrypt, Joi, express-validator, Multer, Nodemailer | [Hostel-Adda](https://github.com/khush2802/Hostel-Adda), [hireAI](https://github.com/khush2802/hireAI), [perplexity](https://github.com/khush2802/perplexity) |
| Data and services | MongoDB with Mongoose (including GeoJSON), Cloudinary, ImageKit, Mapbox | [Hostel-Adda](https://github.com/khush2802/Hostel-Adda), [BE_PERFECTLY](https://github.com/khush2802/BE_PERFECTLY) |
| Deployment | Vercel, GitHub Pages, Render | [UNIVERSE](https://github.com/khush2802/UNIVERSE), [GTA-5](https://github.com/khush2802/GTA-5), [Hostel-Adda](https://github.com/khush2802/Hostel-Adda) |

**Learning:** Python with local LLMs — a first script that calls Qwen3 through Ollama's OpenAI-compatible API, in [MIK_genAI_py](https://github.com/khush2802/MIK_genAI_py). No public code yet for machine learning, computer vision or cloud infrastructure.

## Learning log

| Track | What's there |
| --- | --- |
| [DSA](https://github.com/khush2802/DSA) · C++ | Striver's A2Z sheet (sorting, recursion, linked lists) and LeetCode daily problems — [LeetCode profile](https://leetcode.com/u/khush2802/) |
| [BE_PERFECTLY](https://github.com/khush2802/BE_PERFECTLY) | Day-by-day Express and MongoDB drills: JWT auth, cookies, file uploads to ImageKit |
| [OS](https://github.com/khush2802/OS) | A macOS-style desktop in React: draggable, resizable windows and a terminal emulator |
| [landingPages](https://github.com/khush2802/landingPages) | Vanilla JavaScript DOM exercises: OTP timer, expense tracker, filters, local storage |

## Contact

I'm looking for my first full-time software engineering role. If you're building backend systems, developer tools or applied-AI products, I'd like to talk.

[LinkedIn](https://www.linkedin.com/in/khush-meena-65903834b/) · [Email](mailto:khush011235@gmail.com) · [LeetCode](https://leetcode.com/u/khush2802/)

<sub>Plain Markdown plus SVGs drawn by this repository's own script — no third-party stats services. <a href="https://github.com/khush2802/khush2802/blob/main/docs/MAINTENANCE.md">How it's built and maintained</a>.</sub>
