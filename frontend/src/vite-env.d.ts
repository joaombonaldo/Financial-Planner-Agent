/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the FastAPI backend. See `.env.example`. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
