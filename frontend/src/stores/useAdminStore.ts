import { create } from 'zustand';
import { Employee, PolicyDocument } from '@/types';
import { useAuthStore } from './useAuthStore';
import { sanitizeText } from '@/lib/security';

interface AdminStoreState {
  employees: Employee[];
  policies: PolicyDocument[];
  
  // Employee CRUD
  addEmployee: (data: Omit<Employee, 'id' | 'createdAt'>) => Employee | null;
  updateEmployee: (id: string, patch: Partial<Omit<Employee, 'id' | 'createdAt'>>) => boolean;
  deleteEmployee: (id: string) => boolean;
  toggleEmployeeStatus: (id: string) => boolean;

  // Policy Documents CRUD
  addPolicy: (data: Omit<PolicyDocument, 'id' | 'updatedAt'>) => PolicyDocument | null;
  updatePolicy: (id: string, patch: Partial<Omit<PolicyDocument, 'id' | 'updatedAt'>>) => boolean;
  deletePolicy: (id: string) => boolean;
}

const INITIAL_EMPLOYEES: Employee[] = [
  {
    id: 'emp-101',
    name: 'Sarah Chen',
    email: 'sarah.chen@enterprise.internal',
    department: 'Financial Planning & Analysis',
    role: 'analyst',
    status: 'active',
    assignedWorkspaces: ['ws-fin-2024'],
    createdAt: '2026-08-14T09:00:00Z',
  },
  {
    id: 'emp-102',
    name: 'Marcus Vance',
    email: 'marcus.vance@enterprise.internal',
    department: 'Cloud Infrastructure & SRE',
    role: 'manager',
    status: 'active',
    assignedWorkspaces: ['ws-eng-arch'],
    createdAt: '2026-07-22T10:30:00Z',
  },
  {
    id: 'emp-103',
    name: 'Elena Rostova',
    email: 'elena.rostova@enterprise.internal',
    department: 'Legal & Global Compliance',
    role: 'compliance_officer',
    status: 'active',
    assignedWorkspaces: ['ws-legal-compliance', 'ws-fin-2024'],
    createdAt: '2026-09-01T11:15:00Z',
  },
  {
    id: 'emp-104',
    name: 'David Okafor',
    email: 'david.okafor@enterprise.internal',
    department: 'Product Security Operations',
    role: 'employee',
    status: 'suspended',
    assignedWorkspaces: ['ws-eng-arch'],
    createdAt: '2026-09-19T14:45:00Z',
  },
];

const INITIAL_POLICIES: PolicyDocument[] = [
  {
    id: 'pol-sec-01',
    title: 'POL-01: Zero-Trust Access & Secret Management',
    category: 'Information Security',
    version: 'v2.4',
    department: 'Information Security',
    summary: 'Governs multi-factor verification, API key lifecycle, and automated rotation schedules for production services.',
    content: 'All production endpoints, internal microservices, and databases must require hardware-backed FIDO2 MFA. Administrative credentials and passkeys must be rotated every 90 days. Static tokens in codebases are strictly prohibited and actively intercepted by CI audit scanners.',
    effectiveDate: '2026-01-01',
    status: 'published',
    updatedAt: '2026-10-15T12:00:00Z',
  },
  {
    id: 'pol-gdpr-02',
    title: 'POL-02: Global Data Retention & GDPR Article 30 Schedule',
    category: 'Data Privacy & GDPR',
    version: 'v3.1',
    department: 'Legal & Compliance',
    summary: 'Mandates specific retention timeframes, right-to-be-forgotten deletion workflows, and sub-processor audit logs.',
    content: 'User telemetry and query transcripts must be purged after 180 days unless held under litigation freeze. Personal identifiable information (PII) must be masked or tokenized prior to vector embedding generation. Data processing agreements must be reviewed on an annual basis.',
    effectiveDate: '2026-03-15',
    status: 'published',
    updatedAt: '2026-09-28T16:30:00Z',
  },
  {
    id: 'pol-fin-03',
    title: 'POL-03: Material Non-Public Information (MNPI) Handling',
    category: 'Financial & SEC',
    version: 'v1.8',
    department: 'Corporate Finance',
    summary: 'Strict handling standards for quarterly 10-Q draft reports, revenue forecasts, and earnings disclosures.',
    content: 'Unreleased financial metrics, preliminary Q3 performance figures, and audit workpapers may only be indexed in encrypted financial workspace partitions. Trading blackouts take effect 15 calendar days before fiscal quarter close until 48 hours after public disclosure.',
    effectiveDate: '2026-06-01',
    status: 'published',
    updatedAt: '2026-10-10T09:20:00Z',
  },
  {
    id: 'pol-hr-04',
    title: 'POL-04: Acceptable AI & Knowledge Intelligence Utilization',
    category: 'HR & Code of Conduct',
    version: 'v1.0',
    department: 'People Operations',
    summary: 'Guidelines on querying internal document vaults and prohibiting extraction of proprietary intellectual property.',
    content: 'Enterprise Query must be used exclusively for authorized business analysis. Employees are prohibited from injecting customer proprietary code or third-party NDA materials into unverified partitions.',
    effectiveDate: '2026-09-01',
    status: 'draft',
    updatedAt: '2026-10-20T14:10:00Z',
  },
];

export const useAdminStore = create<AdminStoreState>((set, get) => ({
  employees: INITIAL_EMPLOYEES,
  policies: INITIAL_POLICIES,

  // Employee CRUD
  addEmployee: (data) => {
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return null;
    }

    const newEmp: Employee = {
      id: `emp-${Date.now()}`,
      name: sanitizeText(data.name),
      email: sanitizeText(data.email).toLowerCase(),
      department: sanitizeText(data.department),
      role: data.role,
      status: data.status,
      assignedWorkspaces: data.assignedWorkspaces || [],
      createdAt: new Date().toISOString(),
    };

    set((state) => ({
      employees: [newEmp, ...state.employees],
    }));
    return newEmp;
  },

  updateEmployee: (id, patch) => {
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      employees: state.employees.map((emp) => {
        if (emp.id !== id) return emp;
        return {
          ...emp,
          name: patch.name !== undefined ? sanitizeText(patch.name) : emp.name,
          email: patch.email !== undefined ? sanitizeText(patch.email).toLowerCase() : emp.email,
          department: patch.department !== undefined ? sanitizeText(patch.department) : emp.department,
          role: patch.role !== undefined ? patch.role : emp.role,
          status: patch.status !== undefined ? patch.status : emp.status,
          assignedWorkspaces: patch.assignedWorkspaces !== undefined ? patch.assignedWorkspaces : emp.assignedWorkspaces,
        };
      }),
    }));
    return true;
  },

  deleteEmployee: (id) => {
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      employees: state.employees.filter((emp) => emp.id !== id),
    }));
    return true;
  },

  toggleEmployeeStatus: (id) => {
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      employees: state.employees.map((emp) =>
        emp.id === id
          ? { ...emp, status: emp.status === 'active' ? 'suspended' : 'active' }
          : emp
      ),
    }));
    return true;
  },

  // Policy Documents CRUD
  addPolicy: (data) => {
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return null;
    }

    const newPolicy: PolicyDocument = {
      id: `pol-${Date.now()}`,
      title: sanitizeText(data.title),
      category: data.category,
      version: sanitizeText(data.version || 'v1.0'),
      department: sanitizeText(data.department),
      summary: sanitizeText(data.summary),
      content: sanitizeText(data.content),
      effectiveDate: data.effectiveDate,
      status: data.status,
      updatedAt: new Date().toISOString(),
    };

    set((state) => ({
      policies: [newPolicy, ...state.policies],
    }));
    return newPolicy;
  },

  updatePolicy: (id, patch) => {
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      policies: state.policies.map((pol) => {
        if (pol.id !== id) return pol;
        return {
          ...pol,
          title: patch.title !== undefined ? sanitizeText(patch.title) : pol.title,
          category: patch.category !== undefined ? patch.category : pol.category,
          version: patch.version !== undefined ? sanitizeText(patch.version) : pol.version,
          department: patch.department !== undefined ? sanitizeText(patch.department) : pol.department,
          summary: patch.summary !== undefined ? sanitizeText(patch.summary) : pol.summary,
          content: patch.content !== undefined ? sanitizeText(patch.content) : pol.content,
          effectiveDate: patch.effectiveDate !== undefined ? patch.effectiveDate : pol.effectiveDate,
          status: patch.status !== undefined ? patch.status : pol.status,
          updatedAt: new Date().toISOString(),
        };
      }),
    }));
    return true;
  },

  deletePolicy: (id) => {
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      policies: state.policies.filter((pol) => pol.id !== id),
    }));
    return true;
  },
}));
