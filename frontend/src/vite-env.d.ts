/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ALLOW_ASOF?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
