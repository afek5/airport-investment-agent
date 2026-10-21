import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

// Manrope's `liga` draws "(c)" as © (seen in the G3 answer's "(c) Cargo-inclusive" row) and "->" as an arrow.
it("turns off common ligatures on body so literal answer text is drawn as written", () => {
  const css = readFileSync(join(__dirname, "../app/globals.css"), "utf8");
  const body = css.match(/^body\s*\{([^}]*)\}/m)?.[1] ?? "";
  expect(body).toMatch(/font-variant-ligatures:\s*no-common-ligatures/);
});
