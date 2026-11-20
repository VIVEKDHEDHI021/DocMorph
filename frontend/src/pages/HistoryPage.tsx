import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { DocumentCard } from '../components/DocumentCard';
import { NativeService } from '../services/nativeService';

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [searchQuery, setSearchQuery] = useState('');
  const [filterTab, setFilterTab] = useState<'all' | 'personalized' | 'uploaded'>('all');
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest' | 'name'>('newest');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadToast, setDownloadToast] = useState<string | null>(null);

  // Fetch all documents
  const {
    data: documentsData,
    isLoading,
  } = useQuery({
    queryKey: ['documents', user?.id],
    queryFn: () => api.documents.list(1, 200),
    enabled: !!user?.id,
    refetchInterval: 10000,
  });

  const documents = documentsData?.items || [];

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.documents.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', user?.id] });
      setDeletingId(null);
    },
    onError: (err: any) => {
      alert(`Delete failed: ${err.message}`);
      setDeletingId(null);
    },
  });

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Delete "${name}"?`)) {
      setDeletingId(id);
      deleteMutation.mutate(id);
    }
  };

  const handleDownload = async (id: string, name: string) => {
    setDownloadingId(id);
    try {
      const doc = documents.find((d) => d.id === id);
      const isPersonalized = doc?.has_personalized_output || doc?.status === 'completed';
      const cleanName = isPersonalized ? `DocMorph_Personalized_${name}` : name;
      await api.personalization.exportPdf(id, cleanName);
      setDownloadToast(`Saved to Downloads: ${cleanName}`);
      setTimeout(() => setDownloadToast(null), 4000);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const handlePickNewPdf = async () => {
    try {
      const picked = await NativeService.pickPdfFile();
      if (picked && picked.file) {
        window.dispatchEvent(new CustomEvent('docmorph:add-pdf', { detail: picked.file }));
        navigate('/');
      }
    } catch (err: any) {
      console.error('File pick error:', err);
    }
  };

  // Filter logic
  let filteredDocs = documents.filter((doc) => {
    const matchesSearch = doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;

    if (filterTab === 'personalized') {
      return doc.status === 'completed' || doc.has_personalized_output;
    }
    if (filterTab === 'uploaded') {
      return doc.status !== 'completed' && !doc.has_personalized_output;
    }
    return true;
  });

  // Sort logic
  filteredDocs = [...filteredDocs].sort((a, b) => {
    if (sortOrder === 'name') {
      return a.original_filename.localeCompare(b.original_filename);
    }
    const timeA = new Date(a.created_at).getTime();
    const timeB = new Date(b.created_at).getTime();
    return sortOrder === 'newest' ? timeB - timeA : timeA - timeB;
  });

  const totalCount = documents.length;
  const completedCount = documents.filter((d) => d.status === 'completed' || d.has_personalized_output).length;
  const uploadedCount = totalCount - completedCount;

  return (
    <div className="w-full max-w-xl mx-auto px-3 sm:px-4 pt-3 pb-36">
      {/* Top Header Row with Back Button */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={() => navigate('/')}
            className="w-8 h-8 rounded-full bg-surface-container hover:bg-surface-container-high flex items-center justify-center text-on-surface-variant transition-colors active:scale-95 shrink-0"
            title="Back to Home"
          >
            <span className="material-symbols-outlined text-[18px]">arrow_back</span>
          </button>
          <div className="min-w-0">
            <h1 className="text-base sm:text-lg font-bold text-on-surface tracking-tight truncate">
              Document History
            </h1>
            <p className="text-[11px] text-on-surface-variant truncate">
              {totalCount} total files • {completedCount} personalized
            </p>
          </div>
        </div>

        <button
          onClick={handlePickNewPdf}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-primary text-on-primary text-xs font-semibold shadow-xs hover:opacity-90 active:scale-95 transition-all shrink-0"
        >
          <span className="material-symbols-outlined text-[15px]">add</span>
          <span>Add PDF</span>
        </button>
      </div>

      {downloadToast && (
        <div className="mb-3 flex items-center gap-2 rounded-xl bg-secondary-fixed/90 p-2.5 text-on-secondary-fixed-variant border border-secondary/20 shadow-sm animate-fade-in">
          <span className="material-symbols-outlined text-[18px] text-secondary">check_circle</span>
          <span className="text-xs font-semibold flex-1 truncate">{downloadToast}</span>
        </div>
      )}

      {/* Search Input Bar */}
      <div className="mb-3 relative w-full">
        <span className="material-symbols-outlined pointer-events-none absolute left-3 top-2 text-[17px] text-outline">
          search
        </span>
        <input
          type="text"
          placeholder="Search by filename..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-xl bg-surface-container-lowest border border-outline-variant/60 py-2 pl-9 pr-8 text-xs text-on-surface placeholder-outline focus:border-primary focus:outline-none transition-colors shadow-xs"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-2.5 top-2 text-outline hover:text-on-surface text-[14px]"
          >
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        )}
      </div>

      {/* Filter Tabs and Sort Control */}
      <div className="mb-3 flex items-center justify-between gap-2">
        {/* Status Filters */}
        <div className="flex items-center gap-1 bg-surface-container-low p-1 rounded-full text-[11px] font-medium">
          <button
            onClick={() => setFilterTab('all')}
            className={`px-2.5 py-1 rounded-full transition-colors ${
              filterTab === 'all'
                ? 'bg-surface-container-lowest text-primary font-bold shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            All ({totalCount})
          </button>
          <button
            onClick={() => setFilterTab('personalized')}
            className={`px-2.5 py-1 rounded-full transition-colors ${
              filterTab === 'personalized'
                ? 'bg-surface-container-lowest text-secondary font-bold shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            Done ({completedCount})
          </button>
          <button
            onClick={() => setFilterTab('uploaded')}
            className={`px-2.5 py-1 rounded-full transition-colors ${
              filterTab === 'uploaded'
                ? 'bg-surface-container-lowest text-primary font-bold shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            Pending ({uploadedCount})
          </button>
        </div>

        {/* Sort Selector */}
        <div className="flex items-center gap-1 shrink-0">
          <span className="material-symbols-outlined text-[16px] text-outline">sort</span>
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as any)}
            className="bg-surface-container-low text-on-surface border-none text-[11px] font-medium rounded-lg px-2 py-1 outline-none cursor-pointer"
          >
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="name">Name (A-Z)</option>
          </select>
        </div>
      </div>

      {/* Documents List */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center rounded-xl bg-surface-container-lowest py-16 border border-outline-variant/50">
          <span className="material-symbols-outlined text-[28px] text-primary animate-spin">progress_activity</span>
          <p className="mt-2 text-xs text-on-surface-variant">Loading document history...</p>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl bg-surface-container-lowest py-12 px-4 text-center border border-outline-variant/50">
          <div className="w-12 h-12 rounded-full bg-surface-container-high/60 flex items-center justify-center mb-2 text-outline">
            <span className="material-symbols-outlined text-[26px]">folder_off</span>
          </div>
          <p className="text-xs font-semibold text-on-surface">
            {searchQuery
              ? `No documents matching "${searchQuery}"`
              : filterTab !== 'all'
              ? `No ${filterTab} documents found`
              : 'No documents in history'}
          </p>
          <p className="text-[11px] text-outline mt-1 max-w-xs">
            {searchQuery
              ? 'Try searching with a different filename or clear the filter.'
              : 'Import and personalize assignments to view them here anytime.'}
          </p>
          <button
            onClick={handlePickNewPdf}
            className="mt-4 px-4 py-2 rounded-full bg-primary text-on-primary text-xs font-semibold shadow-xs hover:opacity-90 active:scale-95 transition-all"
          >
            Select PDF Document
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredDocs.map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              onOpen={(id) => navigate(`/workspace/${id}`)}
              onDelete={handleDelete}
              onDownload={handleDownload}
              isDeleting={deletingId === doc.id}
              isDownloading={downloadingId === doc.id}
            />
          ))}
        </div>
      )}
    </div>
  );
};
