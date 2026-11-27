# JobTracker: Vite + React Career Workspace

A component-driven React application built with Vite and Lucide icons to help users manage job applications and search local or placeholder job postings.

## 📁 Project Structure & File Guide

```text
src/
├── components/                  # Reusable UI building blocks
│   ├── JobApplicationRow.jsx    # Renders an individual application row inside tables
│   ├── JobPostingCard.jsx       # Renders an individual explore card for available job listings
│   ├── Sidebar.jsx              # App navigation panel, workspace links, and login toggle
│   └── StatCard.jsx             # Renders metric cards (Total, In Progress, Offers, Rejected)
├── data/                        # Static and mock data files (easy to swap for APIs)
│   ├── applications.js          # Initial array of tracked user job applications
│   └── jobPostings.js           # Sample/explore job listings available to track
├── api.js                       # apiFetch(): shared helper for API requests that need login
├── App.css                      # Shared styling stylesheet for the app shell and components
├── App.jsx                      # Core layout wrapper, page state, router, and business logic
└── main.jsx                     # React entry point rendering App into the DOM
```

## Requests that need login

Use `apiFetch` from `src/api.js` for any backend request that needs a signed-in user:

```js
import { apiFetch } from "../api";

const response = await apiFetch("/api/profile");
const saved = await apiFetch("/api/profile", {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(profile),
});
```

- Paths must be relative and start with `/api/`. These requests go through the Vite proxy in development and the Vercel rewrite in production (see `documentation/decisions/authentication.md`), so the session cookie only goes to the configured backend.
- Cookies are always sent. POST, PUT, PATCH and DELETE requests also get the `X-CSRF-Token` header automatically.
- A `401` response signs the user out in the UI and opens the sign-in dialog. Pages that need login are listed in `PRIVATE_PAGES` in `App.jsx`. Opening one while signed out opens sign-in, and the user is taken there after signing in.

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.
Created with terminal line: npm create vite@latest my-react-app -- --template react

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.

## AI Usage Citation
OpenAI. "Vite + React Project Organization and Component Extraction." ChatGPT, conversational share link, OpenAI, 2026, https://chatgpt.com/share/6ad91d99-e174-83e8-8fc4-19355e77abe8.

The login-required requests and private pages (JH-014: `src/api.js`, the private page and session-expiry handling in `src/App.jsx`, the `apiFetch` changes in `src/components/ProfileForm.jsx`, the `notice` prop in `src/components/LoginForm.jsx`, the `.auth-notice` style in `src/App.css`, and the "Requests that need login" section of this README) were generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/72EBwcy2YAcYaw9JRGZS8Y](https://claude.ai/artifact/72EBwcy2YAcYaw9JRGZS8Y) documents the GenAI interaction that led to my code.

## How to Run

1. Start FastAPI on port `8000` using the [backend setup guide](../../backend/README.md#run-the-server). The Vite dev server proxies `/api/` requests to `http://127.0.0.1:8000`.
2. From `frontend/my-react-app/`, run `npm ci` and then `npm run dev`.
3. Open the URL Vite prints. It typically starts on `http://localhost:5173` and may select another port if that one is busy.
4. Add the exact browser origin, including its port, to `FRONTEND_ORIGINS` in `backend/.env` and restart FastAPI if the setting changed. This allows requests that require a trusted Origin.
