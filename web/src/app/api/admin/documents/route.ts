import { NextResponse } from 'next/server'

import { LIMITS } from '@/lib/constants'
import { badRequest, requireAdmin, withErrorHandling } from '@/server/http'
import { getDocumentStats, uploadDocument } from '@/server/services/admin-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export const GET = withErrorHandling(async () => {
  const admin = await requireAdmin()
  return NextResponse.json({ data: await getDocumentStats(admin.id) })
})

/** One PDF as `multipart/form-data` field `file`, forwarded to the rag-service. */
export const POST = withErrorHandling(async (request: Request) => {
  const admin = await requireAdmin()
  let form: FormData
  try {
    form = await request.formData()
  } catch {
    throw badRequest('Send the PDF as multipart/form-data in a field named "file"')
  }
  const file = form.get('file')
  if (!(file instanceof File) || file.size === 0) {
    throw badRequest('Choose a PDF to upload')
  }
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) throw badRequest('Only PDF files can be indexed')
  if (file.size > LIMITS.uploadBytes) {
    throw badRequest(`The PDF is larger than ${LIMITS.uploadBytes / 1024 / 1024} MB`)
  }
  return NextResponse.json({ data: await uploadDocument(admin.id, file) })
})
