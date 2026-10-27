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
├── App.css                      # Shared styling stylesheet for the app shell and components
├── App.jsx                      # Core layout wrapper, page state, router, and business logic
└── main.jsx                     # React entry point rendering App into the DOM
```

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

## How to Run
1. Navigate to frontend -> my-react-app
2. npm install in terminal
3. npm run dev in terminal
4. Run site on http://localhost:5174/