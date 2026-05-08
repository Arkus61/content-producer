# Content Producer SPA — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to execute this plan task-by-task.

**Goal:** Build a full-featured SPA for the Content Producer SaaS — expert management, AI content generation, social publishing, subscriptions.

**Architecture:** Next.js 14+ App Router, TypeScript, Mantine v7. Separated frontend (Vercel), API at `92.38.222.144:8000`.

**Tech Stack:** Next.js 14, React 19, TypeScript 5, Mantine v7, TanStack Query, Axios

**API Base:** `http://92.38.222.144:8000`

---

## Phase 1: Project Scaffold

### Task 1: Create Next.js project with Mantine
**Files:** Whole project

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
cd frontend
npm install @mantine/core @mantine/hooks @mantine/notifications @mantine/dates @mantine/form @mantine/modals @mantine/spotlight @mantine/charts @mantine/code-highlight
npm install @tabler/icons-react axios @tanstack/react-query recharts dayjs zustand
npm install -D postcss postcss-preset-mantine postcss-simple-vars
```
Verify: `npm run dev` opens on localhost:3000

### Task 2: Configure Mantine theme and PostCSS
**Files:** `postcss.config.mjs`, `src/app/globals.css`, `src/providers.tsx`

- PostCSS preset-mantine + simple-vars
- MantineProvider with custom theme (dark color scheme, purple primary)
- NotificationsProvider
- ModalsProvider

Verify: page renders with Mantine theme, no default Tailwind styles visible

### Task 3: Set up project structure
**Files:** create directories

```
src/
  app/                # App Router pages
  components/         # Shared components
    layout/           # AppShell, sidebar, header
    experts/          # Expert card, list, form
    content/          # Content generator, preview
    social/           # Publish/preview
    billing/          # Subscription cards
    admin/            # Audit, skills
  lib/                # Utilities
    api.ts            # Axios instance
    types.ts          # TypeScript interfaces
    auth.ts           # Token storage helpers
  stores/             # Zustand stores
    userStore.ts
  hooks/              # Custom hooks
```

---

## Phase 2: API Client & Types

### Task 4: Define TypeScript types
**Files:** `src/lib/types.ts`

Copy all Supabase DB schemas as TS interfaces:
```typescript
export interface UserProfile { id: string; email: string; full_name: string; role: 'operator' | 'admin';... }
export interface ExpertCard { id: string; name: string; nickname?: string; profession: string; expertise: string[]; uvp?: string;... }
export interface ContentItem { id: string; content_type: 'post' | 'video'; topic: string; platform: string;... }
export interface Subscription { id: string; tier: 'free' | 'pro' | 'enterprise'; status: string; expires_at?: string;... }
export interface InterviewSession { session_id: string; question: string; progress: { answered: number; total: number; percent: number }; }
export interface ContentV2Result { content_id: string; content: string; visual_brief?: string; score?: number; iterations?: number; task_id?: string; pipeline_log?: string[]; trace?: object; }
export interface PublishResult { platform: string; success: boolean; message_id?: string; post_url?: string; error?: string; }
export interface PreviewData { platform: string; rendered_text: string; truncated: boolean; char_count: number; estimated_read_time_sec: number; warnings: string[]; }
```

### Task 5: Create Axios instance
**Files:** `src/lib/api.ts`

```typescript
import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://92.38.222.144:8000';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('cp_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('cp_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);
```

### Task 6: Create auth helpers
**Files:** `src/lib/auth.ts`

```typescript
export const getToken = () => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('cp_token');
};

export const setToken = (token: string) => {
  localStorage.setItem('cp_token', token);
};

export const removeToken = () => {
  localStorage.removeItem('cp_token');
};

// Parse JWT payload without verification (for UI display only)
export const parseToken = (token: string): { sub: string; email: string; role: string } | null => {
  try {
    const payload = token.split('.')[1];
    return JSON.parse(atob(payload));
  } catch { return null; }
};
```

---

## Phase 3: Layout & Navigation

### Task 7: Build AppShell layout
**Files:** `src/components/layout/AppLayout.tsx`, `src/components/layout/Navbar.tsx`, `src/components/layout/Header.tsx`, `src/app/layout.tsx`

- AppShell from Mantine: navbar (collapsible) + header
- Navbar: logo "CP" + nav links (Dashboard, Experts, Content Studio, Social, Billing) + admin link if role=admin
- Header: breadcrumbs, search bar placeholder, user menu (avatar + dropdown: profile, settings, logout)
- Mobile: burger menu toggle

### Task 8: Implement auth flow — Login page
**Files:** `src/app/(auth)/login/page.tsx`, `src/app/(auth)/layout.tsx`

- Simple login form: email + password (Supabase auth)
- On submit: POST to Supabase auth endpoint → get JWT → store token → redirect to /
- Minimal design, centered card on gradient background
- Error handling: invalid credentials message

### Task 9: Auth middleware and route protection
**Files:** `src/middleware.ts`, `src/app/(app)/layout.tsx`, `src/app/(auth)/layout.tsx`

- Route groups: `(app)` for protected pages, `(auth)` for login
- Middleware checks token in cookie/localStorage, redirects to /login if missing
- App layout fetches `/api/auth/me` on mount → populates user store

### Task 10: Create user store
**Files:** `src/stores/userStore.ts`

```typescript
import { create } from 'zustand';
import { api } from '@/lib/api';
import type { UserProfile } from '@/lib/types';

interface UserState {
  user: UserProfile | null;
  loading: boolean;
  fetchMe: () => Promise<void>;
  clear: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  loading: true,
  fetchMe: async () => {
    try {
      const { data } = await api.get('/api/auth/me');
      set({ user: data, loading: false });
    } catch {
      set({ user: null, loading: false });
    }
  },
  clear: () => set({ user: null }),
}));
```

---

## Phase 4: Dashboard

### Task 11: Dashboard page
**Files:** `src/app/(app)/page.tsx`, `src/components/dashboard/StatsGrid.tsx`, `src/components/dashboard/RecentContent.tsx`

- Fetch: experts list + content list → compute stats
- StatsGrid: 3 cards (Experts count, Content generated, Published posts) — Mantine SimpleGrid + Paper
- Quick actions: 2 Buttons → "New Expert" (+Modal), "Generate Content" (→ /content-studio)
- RecentContent: Mantine Table with last 5 generated items (type, topic, platform, date)
- Use TanStack Query for data fetching

---

## Phase 5: Experts

### Task 12: Experts list page
**Files:** `src/app/(app)/experts/page.tsx`, `src/components/experts/ExpertTable.tsx`, `src/components/experts/CreateExpertModal.tsx`

- Table with columns: Name, Profession, Expertise (Tags), Actions (view, edit, delete)
- Filter: show "All" (admin) or "My experts" (operator)
- CreateExpertModal: form with Mantine useForm → POST /api/experts
- Search: text input filtering by name/profession

### Task 13: Expert detail page + content tab
**Files:** `src/app/(app)/experts/[id]/page.tsx`, `src/components/experts/ExpertProfile.tsx`, `src/components/experts/ExpertContentTab.tsx`

- Fetch: GET /api/experts/:id → display card with all fields
- Tabs (Mantine Tabs): Profile, Content, Memory, Compliance
- Content tab: list of generated items for this expert (GET /api/experts/:id/content) + "Generate new" button

### Task 14: Expert memory & reflections tab
**Files:** `src/components/experts/ExpertMemoryTab.tsx`

- Memory insights: GET /api/experts/:id/memory/insights → accordion with reflection data
- Gaps: GET /api/experts/:id/memory/gaps → list
- "Reflect now" button → POST /api/experts/:id/memory/reflect

---

## Phase 6: Interview Flow

### Task 15: Interview flow component
**Files:** `src/app/(app)/interview/page.tsx`, `src/components/interview/InterviewFlow.tsx`

- Step 1: Name input → POST /api/interview/start → get session_id + first question
- Step 2: Show question + text area → POST /api/interview/{id}/answer → next question
- Progress bar (answered / total)
- Finalize: POST /api/interview/{id}/finalize → show ExpertCard result + redirect to expert page

---

## Phase 7: Content Studio

### Task 16: Content generator page
**Files:** `src/app/(app)/content-studio/page.tsx`, `src/components/content/ContentForm.tsx`, `src/components/content/ContentResult.tsx`

- Expert selector (Select dropdown) → loads experts list
- Content type: SegmentedControl (Post / Video)
- Topic: TextInput
- Platform: Select (telegram/instagram/vk)
- Generate button → POST /api/experts/:id/content (v1) or /content/v2 (v2)
- Loading state: Progress bar or skeleton
- Result: rendered markdown + copy button + visual_brief (if v2)

### Task 17: Content plan page
**Files:** `src/app/(app)/content-plan/page.tsx`, `src/components/content/ContentPlan.tsx`

- Expert selector + days input → POST /api/experts/:id/plan
- Render plan as list of scheduled posts (date, topic, platform)

---

## Phase 8: Social Publishing

### Task 18: Publish page
**Files:** `src/app/(app)/social/page.tsx`, `src/components/social/PublishPanel.tsx`, `src/components/social/PublishedHistory.tsx`

- PublishPanel: text area (content from generated post), platform select, Preview button → POST /api/content/preview
- Preview rendered with platform mock rendering
- Publish button → POST /api/content/publish
- PublishedHistory: GET /api/content/published → table

---

## Phase 9: Billing

### Task 19: Billing page
**Files:** `src/app/(app)/billing/page.tsx`, `src/components/billing/SubscriptionCard.tsx`, `src/components/billing/TransactionHistory.tsx`

- Fetch: GET /api/subscriptions/current → display tier, status, expires
- Tier cards: Free (current), Pro (990₽/мес), Enterprise (4990₽/мес)
- Upgrade button → POST /api/subscriptions → redirect to Prodamus payment_url
- TransactionHistory: GET /api/payment/transactions → table

---

## Phase 10: Admin

### Task 20: Admin pages
**Files:** `src/app/(app)/admin/audit/page.tsx`, `src/app/(app)/admin/skills/page.tsx`

- Audit page: GET /api/audit → table with filters (table_name, action)
- Skills page: GET /api/skills → list of skills grouped by agent; GET /api/skills/:agent/:skill/evolution → modal with evolution log

---

## Phase 11: Polish & Deploy

### Task 21: Error boundaries, loading states, toasts
**Files:** various

- Error boundary component wrapping app
- TanStack Query default error handling → Mantine notifications
- Loading skeletons for every page
- 404 page

### Task 22: Deploy to Vercel
- vercel.json with rewrites to API
- Environment variables in Vercel dashboard
- Verify: production URL with all features working

---

## Verification Checklist

After all phases:
- [ ] Login → dashboard with stats
- [ ] Create expert → appears in list
- [ ] Start interview → answer questions → finalize → expert created
- [ ] Generate content (v1) → result displayed
- [ ] Generate content (v2) → pipeline log, score, visual_brief
- [ ] Preview social post → publish → appears in history
- [ ] Upgrade to Pro → redirect to Prodamus
- [ ] Admin: view audit log, skills evolution
- [ ] Mobile responsive: all pages usable on 375px width
