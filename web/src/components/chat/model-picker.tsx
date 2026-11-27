'use client'

import { Cpu } from 'lucide-react'

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useModels } from '@/hooks/use-models'
import type { ModelInfo } from '@/types/chat'

interface ModelPickerProps {
  value: string
  onChange: (model: string) => void
  disabled?: boolean
}

export function ModelPicker({ value, onChange, disabled }: ModelPickerProps) {
  const { data: models, isLoading } = useModels()

  if (isLoading) {
    return <Skeleton className="h-9 w-44" />
  }

  const available = models ?? []
  // The chat's saved model may no longer be installed on the host; keep it
  // selectable so the label does not silently go blank.
  const options: ModelInfo[] = available.some((model) => model.id === value)
    ? available
    : [{ id: value, label: value, provider: 'current' }, ...available]

  const grouped = options.reduce<Record<string, ModelInfo[]>>((accumulator, model) => {
    const list = accumulator[model.provider] ?? []
    list.push(model)
    accumulator[model.provider] = list
    return accumulator
  }, {})

  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger
        className="h-8 w-auto min-w-0 max-w-[8.5rem] gap-1.5 rounded-md border bg-background px-2.5 text-xs font-medium shadow-none transition-colors hover:bg-accent sm:min-w-[10rem] sm:max-w-[16rem] sm:px-3"
        aria-label="Model"
      >
        <Cpu className="hidden size-3.5 shrink-0 opacity-70 sm:block" />
        <SelectValue placeholder="Select a model" />
      </SelectTrigger>

      <SelectContent align="end">
        {Object.entries(grouped).map(([provider, entries]) => (
          <SelectGroup key={provider}>
            <SelectLabel className="capitalize">{provider}</SelectLabel>
            {entries.map((model) => (
              <SelectItem key={model.id} value={model.id} className="text-xs">
                {model.label}
              </SelectItem>
            ))}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  )
}
