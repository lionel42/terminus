import path from "node:path"
import { defineConfig } from "vitest/config"

// Unit tests of pure logic (no browser, no backend). The end-to-end tests
// in ./tests run with Playwright instead (`bun run test`).
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
})
