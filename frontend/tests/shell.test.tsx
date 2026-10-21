import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MissionPanel } from "@/components/chat/mission-panel";
import { StepsRow } from "@/components/chat/steps";
import { AppShell } from "@/components/shell/app-shell";
import { stepsOf } from "@/lib/parts";
import routeMix from "./fixtures/route_mix.json";
import adHoc from "./fixtures/query_snapshot.json";
import { assistant, toolPart, user } from "./helpers";

const g3 = [
  user("What is the percentage of long haul flights out of Anchorage airport?"),
  assistant([
    toolPart("route_mix", "t1", "output-available", routeMix, { iata: "ANC" }),
    toolPart("suggest_followups", "t2", "output-available", { questions: ["A?", "B?"] }),
    { type: "text", text: "2.7% of passenger departures…" },
  ]),
];

describe("MissionPanel", () => {
  it("shows Progress, Evidence and a collapsed Trace for the latest answer", async () => {
    render(
      <MissionPanel messages={g3} status="ready" focusedId={null} onFocusLatest={() => {}} stepMs={() => 1234} onClose={() => {}} overlay={false} />,
    );
    const progress = screen.getByTestId("panel-progress");
    expect(progress).toHaveTextContent("route_mix");
    expect(progress).toHaveTextContent("1.2s");
    expect(within(progress).getByRole("img", { name: "Done" })).toBeInTheDocument();
    const evidence = screen.getByTestId("panel-evidence");
    expect(within(evidence).getByTestId("evidence-route_mix")).toBeInTheDocument();
    expect(evidence).toHaveTextContent("For: What is the percentage of long haul flights out of Anchorage airport?");
    expect(screen.queryByTestId("trace-list")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Trace/ }));
    expect(screen.getByTestId("trace-list")).toHaveTextContent("suggest_followups");
  });

  it("shows ad-hoc SQL in the Trace", async () => {
    const msgs = [user("How many flights left BOS for Europe last summer?"), assistant([toolPart("query_snapshot", "q", "output-available", adHoc, { sql: adHoc.data.sql })])];
    render(<MissionPanel messages={msgs} status="ready" focusedId={null} onFocusLatest={() => {}} stepMs={() => undefined} onClose={() => {}} overlay={false} />);
    await userEvent.click(screen.getByRole("button", { name: /Trace/ }));
    expect(screen.getByTestId("trace-list")).toHaveTextContent("SELECT dest_country");
  });

  it("shows a running step with a live mark while the answer streams", () => {
    const msgs = [user("q"), assistant([toolPart("route_mix", "t1", "input-available", undefined, { iata: "ANC" })])];
    render(<MissionPanel messages={msgs} status="streaming" focusedId={null} onFocusLatest={() => {}} stepMs={() => undefined} onClose={() => {}} overlay={false} />);
    expect(within(screen.getByTestId("panel-progress")).getByRole("img", { name: "Running" })).toBeInTheDocument();
    expect(screen.getByText("working")).toBeInTheDocument();
  });

  it("has an empty state before any question", () => {
    render(<MissionPanel messages={[]} status="ready" focusedId={null} onFocusLatest={() => {}} stepMs={() => undefined} onClose={() => {}} overlay={false} />);
    expect(screen.getByTestId("panel-evidence")).toHaveTextContent("Evidence from tool results appears here");
  });
});

describe("StepsRow", () => {
  it("collapses tool steps into one row that expands to the list", async () => {
    render(<StepsRow steps={stepsOf(g3[1])} stepMs={() => 800} elapsedMs={4100} />);
    const toggle = screen.getByRole("button", { name: /1 step · 4.1s/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(screen.getByText("route_mix")).toBeInTheDocument();
    expect(screen.getByText("iata=ANC")).toBeInTheDocument();
  });
});

describe("AppShell", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

  beforeEach(() => {
    let authed = false;
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/session" && (!init?.method || init.method === "GET")) return json({ authenticated: authed });
      if (url === "/api/session" && init?.method === "POST") {
        const { code } = JSON.parse(String(init.body));
        if (code !== "letmein") return json({ error: "bad_code", message: "That access code is not right." }, 401);
        authed = true;
        return json({ authenticated: true });
      }
      if (url === "/api/conversations") return json({ conversations: [{ id: "c1", title: "New England candidates", updated_at: new Date().toISOString() }] });
      return json({ error: "not_found", message: "nope" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.innerWidth = 1440;
  });
  afterEach(() => vi.unstubAllGlobals());

  it("gates the app behind the access code, then shows the welcome state and recent chats", async () => {
    render(<AppShell />);
    const input = await screen.findByLabelText("Access code");
    await userEvent.type(input, "wrong");
    fireEvent.submit(input.closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("isn't right");

    await userEvent.clear(input);
    await userEvent.type(input, "letmein");
    fireEvent.submit(input.closest("form")!);

    const welcome = await screen.findByTestId("welcome");
    expect(within(welcome).getByRole("heading", { name: "Where should the next terminal go?" })).toBeInTheDocument();
    expect(within(welcome).getAllByRole("button")).toHaveLength(4);
    await waitFor(() => expect(screen.getByTestId("recent-chats")).toHaveTextContent("New England candidates"));
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });

  it("reopens the conversation named in the URL after a reload, with its evidence", async () => {
    window.history.replaceState(null, "", "/?c=c1");
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/session") return json({ authenticated: true });
      if (url === "/api/conversations") return json({ conversations: [{ id: "c1", title: "Anchorage long-haul" }] });
      if (url === "/api/conversations/c1") return json({ id: "c1", title: "Anchorage long-haul", messages: g3 });
      return json({ error: "not_found", message: "nope" }, 404);
    });
    render(<AppShell />);
    expect(await screen.findByTestId("assistant-message")).toHaveTextContent("2.7% of passenger departures");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Anchorage long-haul");
    // Desktop: the Mission panel opens by itself for a chat with tool calls.
    expect(await screen.findByTestId("evidence-route_mix")).toBeInTheDocument();
    window.history.replaceState(null, "", "/");
  });
});
