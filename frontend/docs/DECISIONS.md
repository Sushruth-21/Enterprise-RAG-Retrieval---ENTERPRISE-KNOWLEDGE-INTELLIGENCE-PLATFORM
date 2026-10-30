# Architecture & Technical Decisions (ADRs)

## ADR 001: Technology Stack Selection
- **Status**: Accepted
- **Decision**: React 18 + TypeScript + Vite, Tailwind CSS, `framer-motion`, Zustand, TanStack Query, Axios, React Router DOM v6, Lucide React.

## ADR 002: Visual Theme Evolution — Wrapped Paper & Burnt Orange
- **Status**: Accepted & Refined
- **Context**: User requested a realistic, warm, minimal stationery / craft paper theme with burnt orange and black ink accents.
- **Decision**:
  - Background: Warm wrapped parchment paper `#F4EFE6`.
  - Elevated surfaces: Clean paper cards `#FCFAF7` / `#FFFFFF` with craft fold borders `#E2D7C8`.
  - Accent: Burnt orange `#E05A2B` for primary interactive states.
  - Text & Elements: Deep black ink `#1C1917` for maximum contrast and readability.

## ADR 003: Pure Gemini / ChatGPT Conversational Hero
- **Status**: Accepted
- **Context**: Removed lower overview sections to maintain single-focus landing page.
- **Decision**:
  - Landing page consists solely of the centered query composer with direct document attachment (`Attach` button), workspace indicator, and prompt starter pills.

## ADR 004: Global Search & Dropdown Navigation
- **Status**: Accepted
- **Context**: Removed breadcrumbs to simplify the header into a clean search-first layout.
- **Decision**:
  - Top header features a global search bar in the center.
  - All workspace switching and feature tools (Documents, Canvas, Batch Suite, Settings) are placed in clean dropdown menus.

## ADR 005: FastAPI Endpoints Contract
- **Status**: Accepted
- **Context**: User specified exact backend URL (`http://localhost:8000`) and endpoint routes.
- **Decision**:
  - `POST /api/documents/upload`
  - `GET /api/documents`
  - `POST /api/chat`
  - `POST /api/batch`
  - `GET /api/chat/{conversation_id}/history`
  - `GET /api/health`
  - Fallback mock responses maintain full UI functionality when the backend is offline.
