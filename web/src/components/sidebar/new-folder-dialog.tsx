'use client'

import * as React from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCreateFolder } from '@/hooks/use-folders'
import { FOLDER_COLORS, LIMITS, type FolderColorId } from '@/lib/constants'
import { cn } from '@/lib/utils'

interface NewFolderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NewFolderDialog({ open, onOpenChange }: NewFolderDialogProps) {
  const createFolder = useCreateFolder()
  const [name, setName] = React.useState('')
  const [color, setColor] = React.useState<FolderColorId>('slate')

  // Reset on close so reopening never shows the previous attempt.
  React.useEffect(() => {
    if (!open) {
      setName('')
      setColor('slate')
    }
  }, [open])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return

    createFolder.mutate(
      { name: trimmed, color },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>New folder</DialogTitle>
            <DialogDescription>
              Group related conversations together.
            </DialogDescription>
          </DialogHeader>

          <div className="my-5 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="folder-name">Name</Label>
              <Input
                id="folder-name"
                autoFocus
                value={name}
                onChange={(event) =>
                  setName(event.target.value.slice(0, LIMITS.folderNameMaxChars))
                }
                placeholder="Research"
                required
              />
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Colour</legend>
              <div className="flex flex-wrap gap-2">
                {FOLDER_COLORS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setColor(option.id)}
                    aria-label={option.label}
                    aria-pressed={color === option.id}
                    className={cn(
                      'size-7 rounded-full ring-offset-2 ring-offset-background transition',
                      option.dot,
                      color === option.id && 'ring-2 ring-ring',
                    )}
                  />
                ))}
              </div>
            </fieldset>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || createFolder.isPending}
            >
              {createFolder.isPending ? 'Creating…' : 'Create folder'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
