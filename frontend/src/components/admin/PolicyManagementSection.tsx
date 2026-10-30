import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  Plus,
  Search,
  Edit2,
  Trash2,
  ExternalLink,
  ShieldCheck,
  Calendar,
  Layers,
  Eye,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { PolicyDocument, PolicyCategory } from '@/types';
import { useAdminStore } from '@/stores/useAdminStore';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

export const PolicyManagementSection: React.FC = () => {
  const { policies, addPolicy, updatePolicy, deletePolicy } = useAdminStore();

  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<'all' | PolicyCategory>('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<PolicyDocument | null>(null);
  const [viewingPolicy, setViewingPolicy] = useState<PolicyDocument | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Form State
  const [formTitle, setFormTitle] = useState('');
  const [formCategory, setFormCategory] = useState<PolicyCategory>('Information Security');
  const [formVersion, setFormVersion] = useState('v1.0');
  const [formDepartment, setFormDepartment] = useState('');
  const [formEffectiveDate, setFormEffectiveDate] = useState('2026-01-01');
  const [formStatus, setFormStatus] = useState<PolicyDocument['status']>('published');
  const [formSummary, setFormSummary] = useState('');
  const [formContent, setFormContent] = useState('');

  const filteredPolicies = policies.filter((pol) => {
    const matchesSearch =
      pol.title.toLowerCase().includes(search.toLowerCase()) ||
      pol.department.toLowerCase().includes(search.toLowerCase()) ||
      pol.summary.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || pol.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const handleOpenAdd = () => {
    setFormTitle('');
    setFormCategory('Information Security');
    setFormVersion('v1.0');
    setFormDepartment('Security & Compliance');
    setFormEffectiveDate(new Date().toISOString().split('T')[0]);
    setFormStatus('published');
    setFormSummary('');
    setFormContent('');
    setIsAddModalOpen(true);
  };

  const handleOpenEdit = (policy: PolicyDocument) => {
    setEditingPolicy(policy);
    setFormTitle(policy.title);
    setFormCategory(policy.category);
    setFormVersion(policy.version);
    setFormDepartment(policy.department);
    setFormEffectiveDate(policy.effectiveDate);
    setFormStatus(policy.status);
    setFormSummary(policy.summary);
    setFormContent(policy.content);
  };

  const handleSaveAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim() || !formContent.trim()) return;

    addPolicy({
      title: formTitle.trim(),
      category: formCategory,
      version: formVersion.trim() || 'v1.0',
      department: formDepartment.trim() || 'Corporate',
      effectiveDate: formEffectiveDate,
      status: formStatus,
      summary: formSummary.trim() || formContent.slice(0, 150) + '...',
      content: formContent.trim(),
    });

    setIsAddModalOpen(false);
  };

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPolicy || !formTitle.trim() || !formContent.trim()) return;

    updatePolicy(editingPolicy.id, {
      title: formTitle.trim(),
      category: formCategory,
      version: formVersion.trim(),
      department: formDepartment.trim(),
      effectiveDate: formEffectiveDate,
      status: formStatus,
      summary: formSummary.trim(),
      content: formContent.trim(),
    });

    setEditingPolicy(null);
  };

  const getCategoryColor = (cat: PolicyCategory) => {
    switch (cat) {
      case 'Information Security':
        return 'bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/30';
      case 'Data Privacy & GDPR':
        return 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border-emerald-500/30';
      case 'Financial & SEC':
        return 'bg-primary/15 text-primary border-primary/30';
      case 'HR & Code of Conduct':
        return 'bg-indigo-500/15 text-indigo-800 dark:text-indigo-300 border-indigo-500/30';
      default:
        return 'bg-surface-muted text-enterprise-muted border-surface-border';
    }
  };

  return (
    <div className="p-6 rounded-2xl border border-surface-border bg-surface-elevated space-y-5 shadow-subtle">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 pb-4 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-enterprise-text">Policy Documents Repository (CRUD)</h3>
            <p className="text-xs text-enterprise-muted mt-0.5">
              Author, revise, and catalog corporate compliance and operational policies for grounded queries.
            </p>
          </div>
        </div>

        <Button onClick={handleOpenAdd} size="sm" className="gap-2 font-semibold text-xs h-9">
          <Plus className="h-4 w-4" />
          <span>New Policy</span>
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-enterprise-dim" />
          <input
            type="text"
            placeholder="Search policy titles, summaries, departments..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-surface-muted border border-surface-border rounded-xl pl-9 pr-3 py-1.5 text-xs text-enterprise-text focus:outline-none focus:border-primary"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
          {(
            [
              'all',
              'Information Security',
              'Data Privacy & GDPR',
              'Financial & SEC',
              'HR & Code of Conduct',
            ] as const
          ).map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat as any)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-mono transition-all shrink-0 ${
                selectedCategory === cat
                  ? 'bg-neutral-900 text-white dark:bg-primary dark:text-white font-bold shadow-sm'
                  : 'text-enterprise-muted hover:text-enterprise-text bg-surface-muted/60'
              }`}
            >
              {cat === 'all' ? 'All Policies' : cat.split('&')[0]}
            </button>
          ))}
        </div>
      </div>

      {/* Policies List */}
      <div className="space-y-3">
        {filteredPolicies.map((pol) => (
          <div
            key={pol.id}
            className="p-4 rounded-xl border border-surface-border bg-surface hover:border-surface-border-hover transition-all shadow-subtle space-y-2.5"
          >
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2.5">
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold border ${getCategoryColor(pol.category)}`}>
                    {pol.category}
                  </span>
                  <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-surface-muted text-enterprise-text border border-surface-border/50">
                    {pol.version}
                  </span>
                  <span
                    className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded font-bold border ${
                      pol.status === 'published'
                        ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                        : pol.status === 'draft'
                        ? 'bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/30'
                        : 'bg-blue-500/20 text-blue-700 dark:text-blue-300 border-blue-500/30'
                    }`}
                  >
                    {pol.status.replace('_', ' ')}
                  </span>
                </div>

                <h4 className="text-sm font-semibold text-enterprise-text leading-snug">
                  {pol.title}
                </h4>
              </div>

              {/* Action Toolbar */}
              <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-start">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setViewingPolicy(pol)}
                  className="h-7 px-2 text-xs gap-1 text-enterprise-muted hover:text-enterprise-text"
                >
                  <Eye className="h-3.5 w-3.5" />
                  <span>View</span>
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleOpenEdit(pol)}
                  className="h-7 px-2 text-xs gap-1 text-enterprise-muted hover:text-enterprise-text"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                  <span>Edit</span>
                </Button>

                {deleteConfirmId === pol.id ? (
                  <div className="flex items-center gap-1 bg-rose-500/15 border border-rose-500/30 px-2 py-0.5 rounded-lg text-xs">
                    <span className="text-rose-700 dark:text-rose-300 text-[10px] font-bold">Delete?</span>
                    <button
                      onClick={() => {
                        deletePolicy(pol.id);
                        setDeleteConfirmId(null);
                      }}
                      className="text-rose-700 dark:text-rose-300 font-bold hover:underline px-1"
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setDeleteConfirmId(null)}
                      className="text-enterprise-muted px-1"
                    >
                      No
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeleteConfirmId(pol.id)}
                    className="p-1 rounded text-enterprise-dim hover:text-rose-600 transition-colors"
                    title="Delete policy"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>

            <p className="text-xs text-enterprise-muted leading-relaxed line-clamp-2">
              {pol.summary}
            </p>

            <div className="flex items-center gap-3 text-[11px] text-enterprise-dim font-mono pt-1 border-t border-surface-border/40">
              <span>Department: {pol.department}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                <span>Effective: {pol.effectiveDate}</span>
              </span>
            </div>
          </div>
        ))}

        {filteredPolicies.length === 0 && (
          <div className="py-8 text-center text-xs text-enterprise-muted">
            No policy documents found matching criteria.
          </div>
        )}
      </div>

      {/* View Policy Modal */}
      <Modal
        isOpen={Boolean(viewingPolicy)}
        onClose={() => setViewingPolicy(null)}
        title={viewingPolicy?.title || 'Policy Document'}
        description={`Effective Date: ${viewingPolicy?.effectiveDate} • Version ${viewingPolicy?.version}`}
      >
        {viewingPolicy && (
          <div className="space-y-4">
            <div className="p-3 rounded-xl bg-primary/10 border border-primary/20 text-xs text-enterprise-text leading-relaxed">
              <span className="font-semibold text-primary block mb-0.5">Policy Scope Summary:</span>
              <p>{viewingPolicy.summary}</p>
            </div>

            <div className="space-y-2">
              <span className="text-xs font-semibold text-enterprise-text block">Full Policy Text</span>
              <div className="p-4 rounded-xl border border-surface-border bg-surface-muted/40 text-xs font-mono text-enterprise-text leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap">
                {viewingPolicy.content}
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-surface-border text-xs text-enterprise-muted font-mono">
              <span>Department: {viewingPolicy.department}</span>
              <Button size="sm" variant="secondary" onClick={() => setViewingPolicy(null)}>
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Add Policy Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Add Corporate Policy Document"
        description="Index an official policy to ground enterprise organizational answers."
      >
        <form onSubmit={handleSaveAdd} className="space-y-3.5">
          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Policy Code & Title
            </label>
            <input
              type="text"
              required
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              placeholder="e.g. POL-05: Artificial Intelligence Use & Compliance"
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Category
              </label>
              <select
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value as PolicyCategory)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs text-enterprise-text focus:outline-none focus:border-primary"
              >
                <option value="Information Security" className="bg-surface-elevated text-enterprise-text">Information Security</option>
                <option value="Data Privacy & GDPR" className="bg-surface-elevated text-enterprise-text">Data Privacy & GDPR</option>
                <option value="Financial & SEC" className="bg-surface-elevated text-enterprise-text">Financial & SEC</option>
                <option value="HR & Code of Conduct" className="bg-surface-elevated text-enterprise-text">HR & Code of Conduct</option>
                <option value="Engineering & Operations" className="bg-surface-elevated text-enterprise-text">Engineering & Operations</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Version Tag
              </label>
              <input
                type="text"
                value={formVersion}
                onChange={(e) => setFormVersion(e.target.value)}
                placeholder="v1.0"
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs font-mono text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Governing Department
              </label>
              <input
                type="text"
                required
                value={formDepartment}
                onChange={(e) => setFormDepartment(e.target.value)}
                placeholder="e.g. Legal & Information Security"
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Effective Date
              </label>
              <input
                type="date"
                required
                value={formEffectiveDate}
                onChange={(e) => setFormEffectiveDate(e.target.value)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs font-mono text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Executive Summary
            </label>
            <input
              type="text"
              required
              value={formSummary}
              onChange={(e) => setFormSummary(e.target.value)}
              placeholder="High-level mandate and application boundary..."
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs text-enterprise-text focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Full Policy Clauses & Provisions
            </label>
            <textarea
              rows={4}
              required
              value={formContent}
              onChange={(e) => setFormContent(e.target.value)}
              placeholder="Write or paste official clauses..."
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs font-mono text-enterprise-text focus:outline-none focus:border-primary leading-relaxed resize-none"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-surface-border">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" className="font-semibold">
              Publish Policy
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Policy Modal */}
      <Modal
        isOpen={Boolean(editingPolicy)}
        onClose={() => setEditingPolicy(null)}
        title="Edit Policy Document"
        description="Update policy content, revision version, or classification status."
      >
        <form onSubmit={handleSaveEdit} className="space-y-3.5">
          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Policy Title
            </label>
            <input
              type="text"
              required
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Category
              </label>
              <select
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value as PolicyCategory)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs text-enterprise-text focus:outline-none focus:border-primary"
              >
                <option value="Information Security" className="bg-surface-elevated text-enterprise-text">Information Security</option>
                <option value="Data Privacy & GDPR" className="bg-surface-elevated text-enterprise-text">Data Privacy & GDPR</option>
                <option value="Financial & SEC" className="bg-surface-elevated text-enterprise-text">Financial & SEC</option>
                <option value="HR & Code of Conduct" className="bg-surface-elevated text-enterprise-text">HR & Code of Conduct</option>
                <option value="Engineering & Operations" className="bg-surface-elevated text-enterprise-text">Engineering & Operations</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Version Tag
              </label>
              <input
                type="text"
                value={formVersion}
                onChange={(e) => setFormVersion(e.target.value)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs font-mono text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Department
              </label>
              <input
                type="text"
                required
                value={formDepartment}
                onChange={(e) => setFormDepartment(e.target.value)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                Effective Date
              </label>
              <input
                type="date"
                required
                value={formEffectiveDate}
                onChange={(e) => setFormEffectiveDate(e.target.value)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs font-mono text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Executive Summary
            </label>
            <input
              type="text"
              required
              value={formSummary}
              onChange={(e) => setFormSummary(e.target.value)}
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs text-enterprise-text focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Full Policy Content
            </label>
            <textarea
              rows={4}
              required
              value={formContent}
              onChange={(e) => setFormContent(e.target.value)}
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-xs font-mono text-enterprise-text focus:outline-none focus:border-primary leading-relaxed resize-none"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-surface-border">
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditingPolicy(null)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" className="font-semibold">
              Save Policy Changes
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
