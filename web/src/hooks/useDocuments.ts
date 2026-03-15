'use client';

import { useCallback, useEffect, useState } from 'react';

import { deleteDocument, listDocuments, uploadDocument } from '@/lib/api';
import type { Document } from '@/types';

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listDocuments();
      setDocuments(res.documents ?? []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const upload = useCallback(
    async (file: File): Promise<boolean> => {
      setError(null);
      try {
        const doc = await uploadDocument(file);
        // Optimistically add with 'processing' status
        setDocuments((prev) => [doc, ...prev]);
        // Refresh after a short delay to get updated status
        setTimeout(refresh, 3000);
        return true;
      } catch (err) {
        setError((err as Error).message);
        return false;
      }
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string): Promise<boolean> => {
      setError(null);
      try {
        await deleteDocument(id);
        setDocuments((prev) => prev.filter((d) => d.id !== id));
        return true;
      } catch (err) {
        setError((err as Error).message);
        return false;
      }
    },
    [],
  );

  return { documents, loading, error, refresh, upload, remove };
}
