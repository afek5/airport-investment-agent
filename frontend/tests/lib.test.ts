import { describe, expect, it } from "vitest";
import { chatErrorMessage, messageFromBody } from "@/lib/api";
import { fmtNum, fmtPct, fmtSigned, fmtValue } from "@/lib/format";
import { answerTextsOf, evidenceOf, followupsOf, lowestConfidence, parseOutput, stepsOf, titleFrom } from "@/lib/parts";
import routeMix from "./fixtures/route_mix.json";
import unmet from "./fixtures/unmet_demand.json";
import { assistant, toolPart, user } from "./helpers";

describe("format", () => {
  it("formats tool values without re-rounding them", () => {
    expect(fmtNum(4717.5)).toBe("4,717.5");
    expect(fmtNum(24765642)).toBe("24,765,642");
    expect(fmtPct(2.7)).toBe("2.7%");
    expect(fmtValue(3.12, "% / yr")).toBe("3.1%/yr");
    expect(fmtValue(23, "min")).toBe("23 min");
    expect(fmtValue(null, "min")).toBe("—");
    expect(fmtSigned(-0.1, (v) => fmtPct(v))).toBe("−0.1%");
  });
});

describe("parts", () => {
  const msg = assistant([
    toolPart("route_mix", "t1", "output-available", routeMix, { iata: "ANC" }),
    toolPart("unmet_demand", "t2", "output-available", JSON.stringify(unmet), { iata: "SFO" }),
    toolPart("live_delays", "t3", "input-available", undefined, { iatas: ["SFO"] }),
    toolPart("suggest_followups", "t4", "output-available", { questions: ["What about cargo?", "Compare with SEA"] }),
    { type: "text", text: "Answer" },
  ]);

  it("shows only the final message: text before the last tool call is dropped, so no answer shows twice", () => {
    const twice = assistant([
      toolPart("rank_airports", "r1", "output-available", {}, {}),
      { type: "text", text: "**Answer** draft before the follow-ups" },
      toolPart("suggest_followups", "f1", "output-available", { questions: ["Q?"] }),
      { type: "text", text: "**Answer** final" },
    ]);
    expect(answerTextsOf(twice).map((t) => t.text)).toEqual(["**Answer** final"]);
    expect(answerTextsOf(msg).map((t) => t.text)).toEqual(["Answer"]);
    expect(answerTextsOf(assistant([{ type: "text", text: "Which Springfield?" }])).map((t) => t.text)).toEqual([
      "Which Springfield?",
    ]);
  });

  it("lists tool steps in order, without the follow-ups tool", () => {
    expect(stepsOf(msg).map((s) => [s.name, s.state])).toEqual([
      ["route_mix", "done"],
      ["unmet_demand", "done"],
      ["live_delays", "running"],
    ]);
  });

  it("collects Evidence from finished envelopes, parsing JSON strings", () => {
    expect(evidenceOf(msg).map((e) => e.name)).toEqual(["route_mix", "unmet_demand"]);
    expect(parseOutput("not json")).toBe("not json");
  });

  it("takes the lowest Data Confidence across envelopes", () => {
    expect(lowestConfidence(evidenceOf(msg))).toBe("Medium"); // route_mix High + unmet_demand Medium
    expect(lowestConfidence([])).toBeNull();
  });

  it("reads follow-ups from the output, or the input while streaming", () => {
    expect(followupsOf(msg)).toEqual(["What about cargo?", "Compare with SEA"]);
    const streaming = assistant([toolPart("suggest_followups", "x", "input-available", undefined, { questions: ["A?", "B?"] })]);
    expect(followupsOf(streaming)).toEqual(["A?", "B?"]);
  });

  it("titles a chat from its first question", () => {
    expect(titleFrom([user("What is the unmet flight demand in SFO airport and why?")])).toBe(
      "What is the unmet flight demand in SFO airport and why?",
    );
    expect(titleFrom([user("x".repeat(100))])).toHaveLength(62);
    expect(titleFrom([])).toBe("New chat");
  });
});

describe("api errors", () => {
  it("prefers the friendly message from the guard's JSON body", () => {
    expect(messageFromBody('{"error":"rate_limited","message":"You have reached the demo limit."}', "x")).toBe(
      "You have reached the demo limit.",
    );
    expect(messageFromBody('{"detail":"Not found"}', "x")).toBe("Not found");
    expect(messageFromBody("", "fallback")).toBe("fallback");
  });

  it("maps chat failures to a readable line", () => {
    const e = (statusCode: number, responseBody = "") => Object.assign(new Error(responseBody), { statusCode, responseBody });
    expect(chatErrorMessage(e(413))).toMatch(/2,000 characters/);
    expect(chatErrorMessage(e(429, '{"error":"rate_limited","message":"Try later."}'))).toBe("Try later.");
    expect(chatErrorMessage(e(500, "Internal Server Error"))).toMatch(/failed to answer/);
  });
});
