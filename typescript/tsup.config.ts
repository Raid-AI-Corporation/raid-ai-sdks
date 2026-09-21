import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm", "cjs"],
  dts: true,
  // No source maps in the published build: they embed the original TypeScript
  // (sourcesContent), including internal comments, which we don't ship publicly.
  sourcemap: false,
  clean: true,
  treeshake: true,
  target: "es2021",
});
