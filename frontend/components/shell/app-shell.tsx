"use client";

import type { UIMessage } from "ai";
import { MoonIcon, PlusIcon, SunIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChatSession, Overlay } from "@/components/chat/chat-session";
import {
  ApiError,
  type ConversationSummary,
  deleteConversation,
  getConversation,
  listConversations,
  sessionStatus,
} from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { AccessScreen } from "./access-screen";
import { Rail } from "./rail";
import { type HistoryState, RecentChats } from "./recent-chats";

const RAIL_W = 76;
const RECENT_W = 272;
const PANEL_W = 400;
const MIN_CONVERSATION_W = 420; // UI-STYLE: the conversation keeps ≥ 400px (+ gutters); the panel gives way first.

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** The open conversation lives in the URL (?c=<id>) so a reload reopens it. */
function chatIdFromUrl(): string | null {
  try {
    return new URLSearchParams(window.location.search).get("c");
  } catch {
    return null;
  }
}
function setChatIdInUrl(id: string | null) {
  try {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("c", id);
    else url.searchParams.delete("c");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  } catch {
    /* non-browser */
  }
}

function useViewportWidth(): number {
  const [w, setW] = useState(1440);
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    on();
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return w;
}

type Auth = "checking" | "locked" | "ready" | "offline";

interface Active {
  id: string;
  title?: string;
  messages: UIMessage[];
}

export function AppShell() {
  const [auth, setAuth] = useState<Auth>("checking");
  const [history, setHistory] = useState<HistoryState>("loading");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [active, setActive] = useState<Active>(() => ({ id: newId(), messages: [] }));
  const [loadingChat, setLoadingChat] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const width = useViewportWidth();

  const [recentPinned, setRecentPinned] = useState(true); // the ≥1100px column
  const [drawer, setDrawer] = useState(false); // recent chats (<1100px) or the whole nav (<768px)
  const [panelOpen, setPanelOpenState] = useState(false);
  const [panelDismissed, setPanelDismissed] = useState(false);

  const phone = width < 768;
  const wide = width >= 1100;
  const recentVisible = wide && recentPinned;
  const panelInline =
    !phone && width - RAIL_W - (recentVisible ? RECENT_W : 0) - PANEL_W >= MIN_CONVERSATION_W;

  const setPanelOpen = useCallback(
    (open: boolean, byUser: boolean) => {
      if (byUser) {
        setPanelOpenState(open);
        if (!open) setPanelDismissed(true);
        return;
      }
      // Automatic open: desktop only (inline), and never after the user closed the panel.
      if (open && panelInline && !panelDismissed) setPanelOpenState(true);
    },
    [panelInline, panelDismissed],
  );

  const loadHistory = useCallback(async () => {
    setHistory("loading");
    try {
      setConversations(await listConversations());
      setHistory("ready");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setAuth("locked");
      else if (e instanceof ApiError && (e.status === 404 || e.status === 405)) setHistory("unavailable");
      else setHistory("error");
    }
  }, []);

  const checkSession = useCallback(async () => {
    setAuth("checking");
    try {
      setAuth((await sessionStatus()) ? "ready" : "locked");
    } catch (e) {
      // A server without the session route (no guards) is open; anything else is a connection problem.
      setAuth(e instanceof ApiError && (e.status === 404 || e.status === 405) ? "ready" : "offline");
    }
  }, []);

  useEffect(() => {
    // Initial session check against the server (an external system).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void checkSession();
  }, [checkSession]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (auth === "ready") void loadHistory();
  }, [auth, loadHistory]);

  const onUnauthorized = useCallback(() => setAuth("locked"), []);

  const onSaved = useCallback((s: ConversationSummary) => {
    setConversations((cs) => [s, ...cs.filter((c) => c.id !== s.id)]);
    setHistory((h) => (h === "loading" || h === "error" ? "ready" : h));
    setChatIdInUrl(s.id);
  }, []);

  const startNewChat = useCallback(() => {
    setActive({ id: newId(), messages: [] });
    setPanelOpenState(false);
    setDrawer(false);
    setChatIdInUrl(null);
  }, []);

  const openChat = useCallback(
    async (id: string) => {
      setDrawer(false);
      if (id === active.id) return;
      setLoadingChat(true);
      try {
        const c = await getConversation(id);
        setActive({ id: c.id, title: c.title, messages: c.messages });
        setChatIdInUrl(c.id);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) setAuth("locked");
        else if (e instanceof ApiError && e.status === 404) {
          setConversations((cs) => cs.filter((c) => c.id !== id));
          setChatIdInUrl(null);
        }
      } finally {
        setLoadingChat(false);
      }
    },
    [active.id],
  );

  // After a reload, reopen the conversation named in the URL once history is available.
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || history !== "ready") return;
    restored.current = true;
    const id = chatIdFromUrl();
    // Fetching the saved conversation is the external system this effect syncs with.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (id) void openChat(id);
  }, [history, openChat]);

  const removeChat = useCallback(
    async (id: string) => {
      const prev = conversations;
      setConversations((cs) => cs.filter((c) => c.id !== id));
      if (id === active.id) startNewChat();
      try {
        await deleteConversation(id);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return;
        if (e instanceof ApiError && e.status === 401) setAuth("locked");
        setConversations(prev);
      }
    },
    [conversations, active.id, startNewChat],
  );

  if (auth === "checking") {
    return <div className="min-h-dvh" aria-busy="true" aria-label="Loading" />;
  }
  if (auth === "locked") {
    return <AccessScreen onUnlocked={() => setAuth("ready")} />;
  }
  if (auth === "offline") {
    return (
      <main className="grid min-h-dvh place-items-center px-4">
        <div className="max-w-sm space-y-3 text-center">
          <h1 className="text-[20px] font-semibold">Can&apos;t reach the server</h1>
          <p className="text-[14px] text-[var(--ink-muted)]">The analyst service didn&apos;t answer. It may be starting up.</p>
          <button
            type="button"
            onClick={() => void checkSession()}
            className="h-10 rounded-[10px] bg-[var(--ink)] px-4 text-[13px] font-semibold text-[var(--ground)]"
          >
            Try again
          </button>
        </div>
      </main>
    );
  }

  const recent = (
    <RecentChats
      conversations={conversations}
      state={history}
      activeId={active.id}
      onSelect={(id) => void openChat(id)}
      onDelete={(id) => void removeChat(id)}
      onRetry={() => void loadHistory()}
    />
  );

  return (
    <div className="flex h-dvh w-full overflow-hidden">
      {!phone ? (
        <Rail
          onNewChat={startNewChat}
          onToggleRecent={() => (wide ? setRecentPinned((p) => !p) : setDrawer((d) => !d))}
          recentOpen={wide ? recentPinned : drawer}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
      ) : null}
      {recentVisible ? (
        <aside aria-label="Recent chats" className="w-[272px] shrink-0 border-r border-[var(--hairline)]">
          {recent}
        </aside>
      ) : null}

      <div className="relative flex min-w-0 flex-1" aria-busy={loadingChat || undefined}>
        <ChatSession
          key={active.id}
          id={active.id}
          title={active.title}
          initialMessages={active.messages}
          historyEnabled={history !== "unavailable"}
          panel={{ open: panelOpen, overlay: !panelInline, setOpen: setPanelOpen }}
          showMenuButton={phone}
          onOpenNav={() => setDrawer(true)}
          onSaved={onSaved}
          onUnauthorized={onUnauthorized}
        />
        {loadingChat ? <div className="absolute inset-0 z-10 bg-[color-mix(in_oklab,var(--ground)_55%,transparent)]" /> : null}
      </div>

      {drawer && !recentVisible ? (
        <Overlay onClose={() => setDrawer(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label={phone ? "Menu" : "Recent chats"}
            className="panel-in fixed inset-y-0 z-50 flex w-[300px] max-w-[86vw] flex-col border-r border-[var(--hairline)] bg-[var(--card-surface)] shadow-[var(--shadow-float)]"
            style={{ left: phone ? 0 : RAIL_W }}
          >
            {phone ? (
              <div className="space-y-1 border-b border-[var(--hairline)] p-3">
                <p className="px-3 pb-2 pt-1 text-[13px] font-semibold">Airport Investment Intelligence</p>
                <button
                  type="button"
                  onClick={startNewChat}
                  className="flex h-11 w-full items-center gap-3 rounded-[22px] px-3.5 text-[13px] hover:bg-[var(--tint-strong)]"
                >
                  <PlusIcon className="size-[18px]" /> New chat
                </button>
                <button
                  type="button"
                  onClick={toggleTheme}
                  className="flex h-11 w-full items-center gap-3 rounded-[22px] px-3.5 text-[13px] hover:bg-[var(--tint-strong)]"
                >
                  {theme === "dark" ? <SunIcon className="size-[18px]" /> : <MoonIcon className="size-[18px]" />}
                  {theme === "dark" ? "Light theme" : "Dark theme"}
                </button>
              </div>
            ) : null}
            <div className="min-h-0 flex-1">{recent}</div>
          </div>
        </Overlay>
      ) : null}
    </div>
  );
}
