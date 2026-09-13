/** The one MSW server instance, started/reset/closed by `src/test/setup.ts`. */
import { setupServer } from "msw/node"

import { handlers } from "./handlers"

export const server = setupServer(...handlers)
