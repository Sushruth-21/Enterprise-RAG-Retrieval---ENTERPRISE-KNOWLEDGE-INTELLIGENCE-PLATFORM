import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  UserPlus,
  Search,
  Edit2,
  Trash2,
  ShieldCheck,
  Check,
  X,
  Mail,
  Building,
  UserCheck,
  UserX,
} from 'lucide-react';
import { Employee, EmployeeRole, EmployeeStatus } from '@/types';
import { useAdminStore } from '@/stores/useAdminStore';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { formatDate } from '@/lib/utils';

export const EmployeeManagementSection: React.FC = () => {
  const { employees, addEmployee, updateEmployee, deleteEmployee, toggleEmployeeStatus } =
    useAdminStore();

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | EmployeeRole>('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Form State
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formDepartment, setFormDepartment] = useState('');
  const [formRole, setFormRole] = useState<EmployeeRole>('employee');
  const [formStatus, setFormStatus] = useState<EmployeeStatus>('active');

  const filteredEmployees = employees.filter((emp) => {
    const matchesSearch =
      emp.name.toLowerCase().includes(search.toLowerCase()) ||
      emp.email.toLowerCase().includes(search.toLowerCase()) ||
      emp.department.toLowerCase().includes(search.toLowerCase());
    const matchesRole = roleFilter === 'all' || emp.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const handleOpenAdd = () => {
    setFormName('');
    setFormEmail('');
    setFormDepartment('Financial Planning & Analysis');
    setFormRole('employee');
    setFormStatus('active');
    setIsAddModalOpen(true);
  };

  const handleOpenEdit = (emp: Employee) => {
    setEditingEmployee(emp);
    setFormName(emp.name);
    setFormEmail(emp.email);
    setFormDepartment(emp.department);
    setFormRole(emp.role);
    setFormStatus(emp.status);
  };

  const handleSaveAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formEmail.trim()) return;

    addEmployee({
      name: formName.trim(),
      email: formEmail.trim(),
      department: formDepartment.trim() || 'General',
      role: formRole,
      status: formStatus,
      assignedWorkspaces: [],
    });

    setIsAddModalOpen(false);
  };

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingEmployee || !formName.trim() || !formEmail.trim()) return;

    updateEmployee(editingEmployee.id, {
      name: formName.trim(),
      email: formEmail.trim(),
      department: formDepartment.trim(),
      role: formRole,
      status: formStatus,
    });

    setEditingEmployee(null);
  };

  const getRoleBadge = (role: EmployeeRole) => {
    switch (role) {
      case 'manager':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-mono font-bold bg-amber-500/15 text-amber-800 dark:text-amber-300 border border-amber-500/30">
            Manager
          </span>
        );
      case 'compliance_officer':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-mono font-bold bg-rose-500/15 text-rose-800 dark:text-rose-300 border border-rose-500/30">
            Compliance
          </span>
        );
      case 'analyst':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-mono font-bold bg-primary/15 text-primary border border-primary/30">
            Analyst
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-mono font-medium bg-surface-muted text-enterprise-muted border border-surface-border">
            Employee
          </span>
        );
    }
  };

  return (
    <div className="p-6 rounded-2xl border border-surface-border bg-surface-elevated space-y-5 shadow-subtle">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 pb-4 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-enterprise-text">Employee Directory & RBAC</h3>
            <p className="text-xs text-enterprise-muted mt-0.5">
              Manage personnel records, organizational departments, and role-based access.
            </p>
          </div>
        </div>

        <Button onClick={handleOpenAdd} size="sm" className="gap-2 font-semibold text-xs h-9">
          <UserPlus className="h-4 w-4" />
          <span>Add Employee</span>
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-enterprise-dim" />
          <input
            type="text"
            placeholder="Search employees by name, email, department..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-surface-muted border border-surface-border rounded-xl pl-9 pr-3 py-1.5 text-xs text-enterprise-text focus:outline-none focus:border-primary"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
          {(['all', 'employee', 'analyst', 'manager', 'compliance_officer'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRoleFilter(r)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-mono capitalize transition-all shrink-0 ${
                roleFilter === r
                  ? 'bg-neutral-900 text-white dark:bg-primary dark:text-white font-bold shadow-sm'
                  : 'text-enterprise-muted hover:text-enterprise-text bg-surface-muted/60'
              }`}
            >
              {r.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Employee List */}
      <div className="divide-y divide-surface-border/70 border border-surface-border rounded-xl overflow-hidden bg-surface">
        {filteredEmployees.map((emp) => (
          <div
            key={emp.id}
            className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-muted/40 transition-colors"
          >
            <div className="flex items-start gap-3 min-w-0">
              <div
                className={`h-9 w-9 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                  emp.status === 'active'
                    ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30'
                }`}
              >
                {emp.name.charAt(0).toUpperCase()}
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm text-enterprise-text truncate">
                    {emp.name}
                  </span>
                  {getRoleBadge(emp.role)}
                  <button
                    onClick={() => toggleEmployeeStatus(emp.id)}
                    className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all border ${
                      emp.status === 'active'
                        ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/30'
                        : 'bg-rose-500/20 text-rose-700 dark:text-rose-300 border-rose-500/30 hover:bg-rose-500/30'
                    }`}
                    title="Click to toggle status"
                  >
                    {emp.status.toUpperCase()}
                  </button>
                </div>

                <div className="flex items-center gap-3 text-xs text-enterprise-muted mt-1 font-mono">
                  <span className="flex items-center gap-1">
                    <Mail className="h-3 w-3" />
                    <span>{emp.email}</span>
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Building className="h-3 w-3" />
                    <span>{emp.department}</span>
                  </span>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleOpenEdit(emp)}
                className="h-8 px-2 text-xs gap-1 text-enterprise-muted hover:text-enterprise-text"
              >
                <Edit2 className="h-3.5 w-3.5" />
                <span>Edit</span>
              </Button>

              {deleteConfirmId === emp.id ? (
                <div className="flex items-center gap-1.5 bg-rose-500/15 border border-rose-500/30 px-2 py-1 rounded-lg text-xs">
                  <span className="text-rose-700 dark:text-rose-300 font-semibold text-[11px]">Remove?</span>
                  <button
                    onClick={() => {
                      deleteEmployee(emp.id);
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
                  onClick={() => setDeleteConfirmId(emp.id)}
                  className="p-1.5 rounded-lg text-enterprise-dim hover:text-rose-600 transition-colors"
                  title="Delete employee"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>
        ))}

        {filteredEmployees.length === 0 && (
          <div className="py-8 text-center text-xs text-enterprise-muted">
            No employees found matching filter criteria.
          </div>
        )}
      </div>

      {/* Add Employee Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Add New Employee"
        description="Provision an employee record with access privileges."
      >
        <form onSubmit={handleSaveAdd} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Full Name
            </label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. Rachel Adams"
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Corporate Email Address
            </label>
            <input
              type="email"
              required
              value={formEmail}
              onChange={(e) => setFormEmail(e.target.value)}
              placeholder="e.g. rachel.adams@enterprise.internal"
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary font-mono"
            />
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
                placeholder="e.g. Financial Planning"
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                System Role
              </label>
              <select
                value={formRole}
                onChange={(e) => setFormRole(e.target.value as EmployeeRole)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
              >
                <option value="employee" className="bg-surface-elevated text-enterprise-text">Employee (Read-Only)</option>
                <option value="analyst" className="bg-surface-elevated text-enterprise-text">Analyst</option>
                <option value="manager" className="bg-surface-elevated text-enterprise-text">Department Manager</option>
                <option value="compliance_officer" className="bg-surface-elevated text-enterprise-text">Compliance Officer</option>
              </select>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-surface-border">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" className="font-semibold">
              Create Employee
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Employee Modal */}
      <Modal
        isOpen={Boolean(editingEmployee)}
        onClose={() => setEditingEmployee(null)}
        title="Edit Employee Information"
        description="Update role permissions and organizational assignments."
      >
        <form onSubmit={handleSaveEdit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Full Name
            </label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Email Address
            </label>
            <input
              type="email"
              required
              value={formEmail}
              onChange={(e) => setFormEmail(e.target.value)}
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary font-mono"
            />
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
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-enterprise-text mb-1">
                System Role
              </label>
              <select
                value={formRole}
                onChange={(e) => setFormRole(e.target.value as EmployeeRole)}
                className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary"
              >
                <option value="employee" className="bg-surface-elevated text-enterprise-text">Employee (Read-Only)</option>
                <option value="analyst" className="bg-surface-elevated text-enterprise-text">Analyst</option>
                <option value="manager" className="bg-surface-elevated text-enterprise-text">Department Manager</option>
                <option value="compliance_officer" className="bg-surface-elevated text-enterprise-text">Compliance Officer</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-enterprise-text mb-1">
              Account Status
            </label>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs font-medium text-enterprise-text cursor-pointer">
                <input
                  type="radio"
                  name="status"
                  checked={formStatus === 'active'}
                  onChange={() => setFormStatus('active')}
                  className="accent-primary"
                />
                <span>Active (Access Granted)</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-medium text-enterprise-text cursor-pointer">
                <input
                  type="radio"
                  name="status"
                  checked={formStatus === 'suspended'}
                  onChange={() => setFormStatus('suspended')}
                  className="accent-primary"
                />
                <span>Suspended (Access Revoked)</span>
              </label>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-surface-border">
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditingEmployee(null)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" className="font-semibold">
              Save Changes
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
