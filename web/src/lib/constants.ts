/** Folder accent tokens. Class strings are literal so Tailwind can see them. */
export const FOLDER_COLORS = [
  { id: 'slate', label: 'Slate', dot: 'bg-slate-400', text: 'text-slate-500' },
  { id: 'rose', label: 'Rose', dot: 'bg-rose-400', text: 'text-rose-500' },
  { id: 'amber', label: 'Amber', dot: 'bg-amber-400', text: 'text-amber-500' },
  { id: 'emerald', label: 'Emerald', dot: 'bg-emerald-400', text: 'text-emerald-500' },
  { id: 'sky', label: 'Sky', dot: 'bg-sky-400', text: 'text-sky-500' },
  { id: 'violet', label: 'Violet', dot: 'bg-violet-400', text: 'text-violet-500' },
] as const

export type FolderColorId = (typeof FOLDER_COLORS)[number]['id']

export const FOLDER_COLOR_IDS = FOLDER_COLORS.map((c) => c.id) as [
  FolderColorId,
  ...FolderColorId[],
]

export function folderColor(id: string) {
  return FOLDER_COLORS.find((c) => c.id === id) ?? FOLDER_COLORS[0]
}

export const LIMITS = {
  messageMaxChars: 32_000,
  titleMaxChars: 120,
  folderNameMaxChars: 60,
  systemPromptMaxChars: 8_000,
  /** Trailing messages sent to the model per request. */
  contextWindowMessages: 40,
} as const

export const ROUTES = {
  home: '/',
  login: '/login',
  register: '/register',
  chat: (id: string) => `/c/${id}`,
  share: (shareId: string) => `/share/${shareId}`,
} as const
